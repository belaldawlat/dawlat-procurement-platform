"""Enterprise retry policies with bounded exponential backoff."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from app.observability.logging_config import get_logger
from app.resilience.exceptions import (
    DawlatPlatformError,
    FailureDisposition,
    normalise_exception,
)
from app.resilience.resilience_context import (
    ResilienceContext,
    create_resilience_context,
)


ResultType = TypeVar("ResultType")


@dataclass(frozen=True)
class RetryPolicy:
    """Immutable retry configuration."""

    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    maximum_delay_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    jitter_ratio: float = 0.10

    def __post_init__(self) -> None:
        """Validate retry policy values."""

        if self.max_attempts < 1:
            raise ValueError("Maximum attempts must be at least 1.")

        if self.initial_delay_seconds < 0:
            raise ValueError(
                "Initial retry delay cannot be negative."
            )

        if self.maximum_delay_seconds < 0:
            raise ValueError(
                "Maximum retry delay cannot be negative."
            )

        if (
            self.maximum_delay_seconds
            < self.initial_delay_seconds
        ):
            raise ValueError(
                "Maximum retry delay cannot be smaller than "
                "the initial retry delay."
            )

        if self.backoff_multiplier < 1:
            raise ValueError(
                "Backoff multiplier must be at least 1."
            )

        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError(
                "Jitter ratio must be between 0 and 1."
            )

    def delay_for_attempt(
        self,
        attempt_number: int,
        *,
        random_value: float | None = None,
    ) -> float:
        """Calculate a bounded delay before the next attempt."""

        if attempt_number < 1:
            raise ValueError(
                "Attempt number must be at least 1."
            )

        exponential_delay = (
            self.initial_delay_seconds
            * (
                self.backoff_multiplier
                ** max(0, attempt_number - 1)
            )
        )

        bounded_delay = min(
            exponential_delay,
            self.maximum_delay_seconds,
        )

        if bounded_delay == 0 or self.jitter_ratio == 0:
            return round(bounded_delay, 6)

        resolved_random = (
            random.random()
            if random_value is None
            else max(0.0, min(1.0, random_value))
        )

        jitter_range = bounded_delay * self.jitter_ratio
        jitter = (
            resolved_random * 2.0 - 1.0
        ) * jitter_range

        return round(
            max(
                0.0,
                min(
                    self.maximum_delay_seconds,
                    bounded_delay + jitter,
                ),
            ),
            6,
        )


@dataclass(frozen=True)
class RetryAttempt:
    """Immutable retry attempt record."""

    operation_name: str
    attempt_number: int
    successful: bool
    delay_before_attempt_seconds: float
    error_code: str = ""
    error_id: str = ""


@dataclass(frozen=True)
class RetryResult(Generic[ResultType]):
    """Result returned by a retry execution."""

    value: ResultType
    attempts: tuple[RetryAttempt, ...]


class RetryExhaustedError(DawlatPlatformError):
    """Raised when retryable attempts are exhausted."""

    default_code = "DAWLAT_RETRY_EXHAUSTED"
    default_safe_message = (
        "The operation could not be completed after several attempts."
    )
    default_disposition = FailureDisposition.NON_RETRYABLE


class RetryExecutor:
    """Execute approved operations using a bounded retry policy."""

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        *,
        sleep_function: Callable[[float], None] = time.sleep,
    ) -> None:
        self._policy = policy or RetryPolicy()
        self._sleep_function = sleep_function
        self._logger = get_logger("resilience.retry")

    @property
    def policy(self) -> RetryPolicy:
        """Return the active retry policy."""

        return self._policy

    def execute(
        self,
        operation: Callable[[], ResultType],
        *,
        operation_name: str,
        context: ResilienceContext | None = None,
        retry_filter: Callable[
            [DawlatPlatformError],
            bool,
        ]
        | None = None,
    ) -> RetryResult[ResultType]:
        """Execute an operation and retry only approved failures."""

        if not callable(operation):
            raise TypeError("Operation must be callable.")

        resolved_name = str(operation_name or "").strip()

        if not resolved_name:
            raise ValueError("Operation name is required.")

        active_context = (
            context
            or create_resilience_context(resolved_name)
        )

        attempts: list[RetryAttempt] = []
        last_error: DawlatPlatformError | None = None

        for attempt_number in range(
            1,
            self._policy.max_attempts + 1,
        ):
            delay_seconds = 0.0

            if attempt_number > 1:
                delay_seconds = self._policy.delay_for_attempt(
                    attempt_number - 1
                )

                self._logger.warning(
                    "Retrying operation.",
                    extra={
                        "operation_name": resolved_name,
                        "attempt_number": attempt_number,
                        "delay_seconds": delay_seconds,
                        "operation_id": (
                            active_context.operation_id
                        ),
                    },
                )

                self._sleep_function(delay_seconds)

            try:
                value = operation()

                attempts.append(
                    RetryAttempt(
                        operation_name=resolved_name,
                        attempt_number=attempt_number,
                        successful=True,
                        delay_before_attempt_seconds=(
                            delay_seconds
                        ),
                    )
                )

                return RetryResult(
                    value=value,
                    attempts=tuple(attempts),
                )

            except Exception as error:
                normalised_error = normalise_exception(error)
                last_error = normalised_error

                attempts.append(
                    RetryAttempt(
                        operation_name=resolved_name,
                        attempt_number=attempt_number,
                        successful=False,
                        delay_before_attempt_seconds=(
                            delay_seconds
                        ),
                        error_code=normalised_error.code,
                        error_id=normalised_error.error_id,
                    )
                )

                should_retry = self._should_retry(
                    normalised_error,
                    retry_filter=retry_filter,
                )

                self._logger.error(
                    "Operation attempt failed.",
                    extra={
                        "operation_name": resolved_name,
                        "attempt_number": attempt_number,
                        "maximum_attempts": (
                            self._policy.max_attempts
                        ),
                        "retry_allowed": should_retry,
                        "error": (
                            normalised_error
                            .diagnostic_payload()
                        ),
                    },
                )

                if not should_retry:
                    raise normalised_error from error

                if (
                    attempt_number
                    >= self._policy.max_attempts
                ):
                    break

                active_context = (
                    active_context.next_attempt()
                )

        if last_error is None:
            raise RetryExhaustedError(
                technical_message=(
                    "Retry execution ended without a result."
                ),
                metadata={
                    "operation_name": resolved_name,
                },
            )

        raise RetryExhaustedError(
            technical_message=(
                f"Operation {resolved_name!r} exhausted "
                f"{self._policy.max_attempts} attempts. "
                f"Last error: {last_error.code}."
            ),
            metadata={
                "operation_name": resolved_name,
                "attempt_count": len(attempts),
                "last_error_code": last_error.code,
                "last_error_id": last_error.error_id,
            },
        ) from last_error

    @staticmethod
    def _should_retry(
        error: DawlatPlatformError,
        *,
        retry_filter: Callable[
            [DawlatPlatformError],
            bool,
        ]
        | None,
    ) -> bool:
        """Return whether an error is approved for retry."""

        if error.disposition in {
            FailureDisposition.FAIL_CLOSED,
            FailureDisposition.FATAL,
            FailureDisposition.NON_RETRYABLE,
        }:
            return False

        if not error.retryable:
            return False

        if retry_filter is None:
            return True

        return bool(retry_filter(error))


_default_retry_executor = RetryExecutor()


def get_retry_executor() -> RetryExecutor:
    """Return the shared retry executor."""

    return _default_retry_executor


def retry_operation(
    operation: Callable[[], ResultType],
    *,
    operation_name: str,
    policy: RetryPolicy | None = None,
    context: ResilienceContext | None = None,
    retry_filter: Callable[
        [DawlatPlatformError],
        bool,
    ]
    | None = None,
) -> RetryResult[ResultType]:
    """Execute an operation using an optional retry policy."""

    executor = (
        RetryExecutor(policy)
        if policy is not None
        else get_retry_executor()
    )

    return executor.execute(
        operation,
        operation_name=operation_name,
        context=context,
        retry_filter=retry_filter,
    )