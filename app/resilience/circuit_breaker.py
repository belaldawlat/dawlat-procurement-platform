"""Circuit-breaker protection for unstable dependencies."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Generic, TypeVar

from app.observability.logging_config import get_logger
from app.resilience.exceptions import (
    CircuitOpenError,
    DawlatPlatformError,
    FailureDisposition,
    normalise_exception,
)


ResultType = TypeVar("ResultType")


class CircuitState(str, Enum):
    """Supported circuit-breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitBreakerPolicy:
    """Immutable circuit-breaker configuration."""

    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_success_threshold: int = 1

    def __post_init__(self) -> None:
        """Validate policy values."""

        if self.failure_threshold < 1:
            raise ValueError(
                "Failure threshold must be at least 1."
            )

        if self.recovery_timeout_seconds < 0:
            raise ValueError(
                "Recovery timeout cannot be negative."
            )

        if self.half_open_success_threshold < 1:
            raise ValueError(
                "Half-open success threshold must be at least 1."
            )


@dataclass(frozen=True)
class CircuitBreakerSnapshot:
    """Immutable circuit-breaker state snapshot."""

    name: str
    state: CircuitState
    failure_count: int
    half_open_success_count: int
    opened_at_monotonic: float | None
    policy: CircuitBreakerPolicy


class CircuitBreaker(Generic[ResultType]):
    """Protect a dependency from cascading repeated failures."""

    def __init__(
        self,
        name: str,
        policy: CircuitBreakerPolicy | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        cleaned_name = str(name or "").strip()

        if not cleaned_name:
            raise ValueError(
                "Circuit-breaker name is required."
            )

        self._name = cleaned_name
        self._policy = policy or CircuitBreakerPolicy()
        self._clock = clock

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_success_count = 0
        self._opened_at: float | None = None

        self._lock = threading.RLock()
        self._logger = get_logger(
            f"resilience.circuit.{cleaned_name}"
        )

    @property
    def name(self) -> str:
        """Return the circuit name."""

        return self._name

    @property
    def policy(self) -> CircuitBreakerPolicy:
        """Return the active circuit policy."""

        return self._policy

    def snapshot(self) -> CircuitBreakerSnapshot:
        """Return a thread-safe state snapshot."""

        with self._lock:
            self._refresh_state_if_ready()

            return CircuitBreakerSnapshot(
                name=self._name,
                state=self._state,
                failure_count=self._failure_count,
                half_open_success_count=(
                    self._half_open_success_count
                ),
                opened_at_monotonic=self._opened_at,
                policy=self._policy,
            )

    def execute(
        self,
        operation: Callable[[], ResultType],
    ) -> ResultType:
        """Execute an operation when the circuit permits it."""

        if not callable(operation):
            raise TypeError("Operation must be callable.")

        with self._lock:
            self._refresh_state_if_ready()

            if self._state is CircuitState.OPEN:
                raise CircuitOpenError(
                    technical_message=(
                        f"Circuit {self._name!r} is open."
                    ),
                    metadata={
                        "circuit_name": self._name,
                        "failure_count": (
                            self._failure_count
                        ),
                    },
                )

        try:
            result = operation()
        except Exception as error:
            normalised_error = normalise_exception(error)
            self._record_failure(normalised_error)
            raise normalised_error from error

        self._record_success()
        return result

    def allow_request(self) -> bool:
        """Return whether the circuit currently allows a request."""

        with self._lock:
            self._refresh_state_if_ready()

            return self._state in {
                CircuitState.CLOSED,
                CircuitState.HALF_OPEN,
            }

    def reset(self) -> None:
        """Manually return the circuit to its closed state."""

        with self._lock:
            self._transition_to_closed(
                reason="manual_reset"
            )

    def force_open(self) -> None:
        """Manually open the circuit."""

        with self._lock:
            self._transition_to_open(
                reason="manual_open"
            )

    def _record_success(self) -> None:
        """Record a successful protected operation."""

        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._half_open_success_count += 1

                if (
                    self._half_open_success_count
                    >= self._policy
                    .half_open_success_threshold
                ):
                    self._transition_to_closed(
                        reason="half_open_recovery"
                    )

                return

            if self._state is CircuitState.CLOSED:
                self._failure_count = 0

    def _record_failure(
        self,
        error: DawlatPlatformError,
    ) -> None:
        """Record a dependency failure."""

        with self._lock:
            if not self._counts_as_circuit_failure(error):
                self._logger.info(
                    "Failure excluded from circuit count.",
                    extra={
                        "circuit_name": self._name,
                        "error_code": error.code,
                        "disposition": (
                            error.disposition.value
                        ),
                    },
                )
                return

            if self._state is CircuitState.HALF_OPEN:
                self._failure_count += 1
                self._transition_to_open(
                    reason="half_open_failure"
                )
                return

            self._failure_count += 1

            self._logger.warning(
                "Circuit failure recorded.",
                extra={
                    "circuit_name": self._name,
                    "failure_count": self._failure_count,
                    "failure_threshold": (
                        self._policy.failure_threshold
                    ),
                    "error_code": error.code,
                    "error_id": error.error_id,
                },
            )

            if (
                self._failure_count
                >= self._policy.failure_threshold
            ):
                self._transition_to_open(
                    reason="failure_threshold_reached"
                )

    @staticmethod
    def _counts_as_circuit_failure(
        error: DawlatPlatformError,
    ) -> bool:
        """Return whether an error should affect the circuit."""

        if error.disposition in {
            FailureDisposition.FAIL_CLOSED,
            FailureDisposition.FATAL,
        }:
            return True

        return bool(error.retryable)

    def _refresh_state_if_ready(self) -> None:
        """Move an open circuit into half-open when eligible."""

        if self._state is not CircuitState.OPEN:
            return

        if self._opened_at is None:
            return

        elapsed = self._clock() - self._opened_at

        if (
            elapsed
            >= self._policy.recovery_timeout_seconds
        ):
            self._transition_to_half_open(
                reason="recovery_timeout_elapsed"
            )

    def _transition_to_open(
        self,
        *,
        reason: str,
    ) -> None:
        """Transition the circuit into the open state."""

        self._state = CircuitState.OPEN
        self._opened_at = self._clock()
        self._half_open_success_count = 0

        self._logger.error(
            "Circuit opened.",
            extra={
                "circuit_name": self._name,
                "reason": reason,
                "failure_count": self._failure_count,
            },
        )

    def _transition_to_half_open(
        self,
        *,
        reason: str,
    ) -> None:
        """Transition the circuit into the half-open state."""

        self._state = CircuitState.HALF_OPEN
        self._half_open_success_count = 0

        self._logger.warning(
            "Circuit entered half-open state.",
            extra={
                "circuit_name": self._name,
                "reason": reason,
            },
        )

    def _transition_to_closed(
        self,
        *,
        reason: str,
    ) -> None:
        """Transition the circuit into the closed state."""

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_success_count = 0
        self._opened_at = None

        self._logger.info(
            "Circuit closed.",
            extra={
                "circuit_name": self._name,
                "reason": reason,
            },
        )


class CircuitBreakerRegistry:
    """Thread-safe registry of named circuit breakers."""

    def __init__(self) -> None:
        self._circuits: dict[
            str,
            CircuitBreaker[object],
        ] = {}
        self._lock = threading.RLock()

    def get_or_create(
        self,
        name: str,
        policy: CircuitBreakerPolicy | None = None,
    ) -> CircuitBreaker[object]:
        """Return an existing circuit or create a new one."""

        cleaned_name = str(name or "").strip()

        if not cleaned_name:
            raise ValueError(
                "Circuit-breaker name is required."
            )

        with self._lock:
            existing = self._circuits.get(cleaned_name)

            if existing is not None:
                if (
                    policy is not None
                    and existing.policy != policy
                ):
                    raise ValueError(
                        "A circuit with this name already "
                        "exists with a different policy."
                    )

                return existing

            circuit: CircuitBreaker[object] = (
                CircuitBreaker(
                    cleaned_name,
                    policy,
                )
            )

            self._circuits[cleaned_name] = circuit
            return circuit

    def snapshots(
        self,
    ) -> tuple[CircuitBreakerSnapshot, ...]:
        """Return deterministic snapshots for all circuits."""

        with self._lock:
            return tuple(
                self._circuits[name].snapshot()
                for name in sorted(self._circuits)
            )

    def reset_all(self) -> None:
        """Reset every registered circuit."""

        with self._lock:
            for circuit in self._circuits.values():
                circuit.reset()

    def clear(self) -> None:
        """Remove all registered circuits."""

        with self._lock:
            self._circuits.clear()


_circuit_breaker_registry = CircuitBreakerRegistry()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Return the shared circuit-breaker registry."""

    return _circuit_breaker_registry