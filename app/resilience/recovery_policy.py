"""Recovery policies for controlled enterprise failure handling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Generic, TypeVar

from app.observability.logging_config import get_logger
from app.resilience.exceptions import (
    DawlatPlatformError,
    FailureDisposition,
    RecoveryFailedError,
    normalise_exception,
)
from app.resilience.resilience_context import (
    ResilienceContext,
    create_resilience_context,
)


ResultType = TypeVar("ResultType")


class RecoveryAction(str, Enum):
    """Supported recovery actions."""

    RERAISE = "reraise"
    FALLBACK = "fallback"
    DEFAULT_VALUE = "default_value"
    IGNORE = "ignore"
    FAIL_CLOSED = "fail_closed"


@dataclass(frozen=True)
class RecoveryPolicy:
    """Immutable enterprise recovery policy."""

    action: RecoveryAction = RecoveryAction.RERAISE
    allow_retryable_errors: bool = True
    allow_non_retryable_errors: bool = False
    allow_fail_closed_errors: bool = False
    allow_fatal_errors: bool = False

    def permits(
        self,
        error: DawlatPlatformError,
    ) -> bool:
        """Return whether this policy permits recovery."""

        if error.disposition is FailureDisposition.RETRYABLE:
            return self.allow_retryable_errors

        if error.disposition is FailureDisposition.RECOVERABLE:
            return True

        if error.disposition is FailureDisposition.NON_RETRYABLE:
            return self.allow_non_retryable_errors

        if error.disposition is FailureDisposition.FAIL_CLOSED:
            return self.allow_fail_closed_errors

        if error.disposition is FailureDisposition.FATAL:
            return self.allow_fatal_errors

        return False


@dataclass(frozen=True)
class RecoveryResult(Generic[ResultType]):
    """Structured result of a recovery operation."""

    value: ResultType
    recovered: bool
    action: RecoveryAction
    original_error_code: str = ""
    original_error_id: str = ""


class RecoveryExecutor:
    """Execute operations using a controlled recovery policy."""

    def __init__(
        self,
        policy: RecoveryPolicy | None = None,
    ) -> None:
        self._policy = policy or RecoveryPolicy()
        self._logger = get_logger("resilience.recovery")

    @property
    def policy(self) -> RecoveryPolicy:
        """Return the active recovery policy."""

        return self._policy

    def execute(
        self,
        operation: Callable[[], ResultType],
        *,
        operation_name: str,
        context: ResilienceContext | None = None,
        fallback: Callable[
            [DawlatPlatformError],
            ResultType,
        ]
        | None = None,
        default_value: ResultType | None = None,
    ) -> RecoveryResult[ResultType]:
        """Execute an operation and apply the configured recovery action."""

        if not callable(operation):
            raise TypeError("Operation must be callable.")

        resolved_name = str(operation_name or "").strip()

        if not resolved_name:
            raise ValueError("Operation name is required.")

        active_context = (
            context
            or create_resilience_context(resolved_name)
        )

        try:
            value = operation()

            return RecoveryResult(
                value=value,
                recovered=False,
                action=RecoveryAction.RERAISE,
            )

        except Exception as error:
            normalised_error = normalise_exception(error)

            self._logger.error(
                "Operation failed before recovery.",
                extra={
                    "operation_name": resolved_name,
                    "operation_id": (
                        active_context.operation_id
                    ),
                    "error": (
                        normalised_error
                        .diagnostic_payload()
                    ),
                    "recovery_action": (
                        self._policy.action.value
                    ),
                },
            )

            if not self._policy.permits(normalised_error):
                raise normalised_error from error

            return self._recover(
                error=normalised_error,
                operation_name=resolved_name,
                fallback=fallback,
                default_value=default_value,
            )

    def _recover(
        self,
        *,
        error: DawlatPlatformError,
        operation_name: str,
        fallback: Callable[
            [DawlatPlatformError],
            ResultType,
        ]
        | None,
        default_value: ResultType | None,
    ) -> RecoveryResult[ResultType]:
        """Apply the configured recovery action."""

        action = self._policy.action

        if action is RecoveryAction.RERAISE:
            raise error

        if action is RecoveryAction.FAIL_CLOSED:
            raise error

        if action is RecoveryAction.FALLBACK:
            if fallback is None:
                raise RecoveryFailedError(
                    technical_message=(
                        "Fallback recovery was requested but "
                        "no fallback function was provided."
                    ),
                    metadata={
                        "operation_name": operation_name,
                        "original_error_code": error.code,
                        "original_error_id": error.error_id,
                    },
                ) from error

            try:
                value = fallback(error)
            except Exception as fallback_error:
                normalised_fallback_error = (
                    normalise_exception(fallback_error)
                )

                self._logger.critical(
                    "Fallback recovery failed.",
                    extra={
                        "operation_name": operation_name,
                        "original_error_code": error.code,
                        "fallback_error": (
                            normalised_fallback_error
                            .diagnostic_payload()
                        ),
                    },
                )

                raise RecoveryFailedError(
                    technical_message=(
                        f"Fallback recovery failed for "
                        f"{operation_name!r}."
                    ),
                    metadata={
                        "operation_name": operation_name,
                        "original_error_code": error.code,
                        "fallback_error_code": (
                            normalised_fallback_error.code
                        ),
                        "fallback_error_id": (
                            normalised_fallback_error.error_id
                        ),
                    },
                ) from fallback_error

            self._log_recovery(
                operation_name=operation_name,
                error=error,
                action=action,
            )

            return RecoveryResult(
                value=value,
                recovered=True,
                action=action,
                original_error_code=error.code,
                original_error_id=error.error_id,
            )

        if action is RecoveryAction.DEFAULT_VALUE:
            self._log_recovery(
                operation_name=operation_name,
                error=error,
                action=action,
            )

            return RecoveryResult(
                value=default_value,  # type: ignore[arg-type]
                recovered=True,
                action=action,
                original_error_code=error.code,
                original_error_id=error.error_id,
            )

        if action is RecoveryAction.IGNORE:
            self._log_recovery(
                operation_name=operation_name,
                error=error,
                action=action,
            )

            return RecoveryResult(
                value=None,  # type: ignore[arg-type]
                recovered=True,
                action=action,
                original_error_code=error.code,
                original_error_id=error.error_id,
            )

        raise RecoveryFailedError(
            technical_message=(
                f"Unsupported recovery action: {action!r}."
            ),
            metadata={
                "operation_name": operation_name,
                "original_error_code": error.code,
            },
        ) from error

    def _log_recovery(
        self,
        *,
        operation_name: str,
        error: DawlatPlatformError,
        action: RecoveryAction,
    ) -> None:
        """Log a successful controlled recovery."""

        self._logger.warning(
            "Operation recovered.",
            extra={
                "operation_name": operation_name,
                "recovery_action": action.value,
                "original_error_code": error.code,
                "original_error_id": error.error_id,
            },
        )


def recover_with_fallback(
    operation: Callable[[], ResultType],
    *,
    operation_name: str,
    fallback: Callable[
        [DawlatPlatformError],
        ResultType,
    ],
    context: ResilienceContext | None = None,
) -> RecoveryResult[ResultType]:
    """Execute an operation using fallback recovery."""

    executor = RecoveryExecutor(
        RecoveryPolicy(
            action=RecoveryAction.FALLBACK,
        )
    )

    return executor.execute(
        operation,
        operation_name=operation_name,
        context=context,
        fallback=fallback,
    )


def recover_with_default(
    operation: Callable[[], ResultType],
    *,
    operation_name: str,
    default_value: ResultType,
    context: ResilienceContext | None = None,
) -> RecoveryResult[ResultType]:
    """Execute an operation using a default recovery value."""

    executor = RecoveryExecutor(
        RecoveryPolicy(
            action=RecoveryAction.DEFAULT_VALUE,
        )
    )

    return executor.execute(
        operation,
        operation_name=operation_name,
        context=context,
        default_value=default_value,
    )