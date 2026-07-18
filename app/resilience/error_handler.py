"""Centralised enterprise error handling and safe error responses."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from app.observability.logging_config import get_logger
from app.resilience.exceptions import (
    DawlatPlatformError,
    ErrorSeverity,
    FailureDisposition,
    normalise_exception,
)
from app.resilience.resilience_context import (
    ResilienceContext,
    get_resilience_context,
)


ResultType = TypeVar("ResultType")


@dataclass(frozen=True)
class ErrorResponse:
    """Safe structured error response."""

    success: bool
    error_id: str
    code: str
    message: str
    category: str
    severity: str
    retryable: bool
    timestamp: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return the response as a serialisable dictionary."""

        return {
            "success": self.success,
            "error": {
                "error_id": self.error_id,
                "code": self.code,
                "message": self.message,
                "category": self.category,
                "severity": self.severity,
                "retryable": self.retryable,
                "timestamp": self.timestamp,
                "metadata": self.metadata,
            },
        }


@dataclass(frozen=True)
class ErrorHandlingResult:
    """Combined handled error result."""

    error: DawlatPlatformError
    response: ErrorResponse
    should_alert: bool
    should_retry: bool
    should_fail_closed: bool


class EnterpriseErrorHandler:
    """Normalise, log and classify application failures."""

    def __init__(self) -> None:
        self._logger = get_logger("resilience.error_handler")

    def handle(
        self,
        error: Exception,
        *,
        context: ResilienceContext | None = None,
        operation_name: str = "",
        include_traceback: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ErrorHandlingResult:
        """Handle an exception using safe enterprise controls."""

        normalised = normalise_exception(error)
        active_context = context or get_resilience_context()

        combined_metadata = {
            **normalised.descriptor.metadata,
            **(metadata or {}),
        }

        operation = (
            str(operation_name or "").strip()
            or active_context.operation_name
        )

        log_payload: dict[str, Any] = {
            "operation_name": operation,
            "operation_id": active_context.operation_id,
            "request_id": active_context.request_id,
            "correlation_id": active_context.correlation_id,
            "actor_id": active_context.actor_id,
            "dependency_name": (
                active_context.dependency_name
            ),
            "error": normalised.diagnostic_payload(),
            "metadata": combined_metadata,
        }

        if include_traceback:
            log_payload["traceback"] = (
                "".join(
                    traceback.format_exception(
                        type(error),
                        error,
                        error.__traceback__,
                    )
                )
            )

        self._write_log(
            normalised,
            log_payload,
        )

        response = ErrorResponse(
            success=False,
            error_id=normalised.error_id,
            code=normalised.code,
            message=normalised.safe_message,
            category=normalised.category.value,
            severity=normalised.severity.value,
            retryable=normalised.retryable,
            timestamp=datetime.now(
                timezone.utc
            ).isoformat(),
            metadata={
                "operation_name": operation,
                "correlation_id": (
                    active_context.correlation_id
                ),
            },
        )

        return ErrorHandlingResult(
            error=normalised,
            response=response,
            should_alert=self._should_alert(
                normalised
            ),
            should_retry=self._should_retry(
                normalised
            ),
            should_fail_closed=(
                normalised.disposition
                is FailureDisposition.FAIL_CLOSED
            ),
        )

    def execute(
        self,
        operation: Callable[[], ResultType],
        *,
        operation_name: str,
        context: ResilienceContext | None = None,
    ) -> ResultType | ErrorResponse:
        """Execute an operation and return a safe response on failure."""

        if not callable(operation):
            raise TypeError("Operation must be callable.")

        try:
            return operation()
        except Exception as error:
            result = self.handle(
                error,
                context=context,
                operation_name=operation_name,
            )
            return result.response

    def raise_normalised(
        self,
        error: Exception,
        *,
        context: ResilienceContext | None = None,
        operation_name: str = "",
    ) -> None:
        """Handle and raise a controlled enterprise exception."""

        result = self.handle(
            error,
            context=context,
            operation_name=operation_name,
        )

        raise result.error from error

    def _write_log(
        self,
        error: DawlatPlatformError,
        payload: dict[str, Any],
    ) -> None:
        """Write an appropriate severity log."""

        message = "Enterprise operation failed."

        if error.severity is ErrorSeverity.CRITICAL:
            self._logger.critical(
                message,
                extra=payload,
            )
            return

        if error.severity is ErrorSeverity.HIGH:
            self._logger.error(
                message,
                extra=payload,
            )
            return

        if error.severity is ErrorSeverity.MEDIUM:
            self._logger.warning(
                message,
                extra=payload,
            )
            return

        self._logger.info(
            message,
            extra=payload,
        )

    @staticmethod
    def _should_alert(
        error: DawlatPlatformError,
    ) -> bool:
        """Return whether operations teams should be alerted."""

        return error.severity in {
            ErrorSeverity.HIGH,
            ErrorSeverity.CRITICAL,
        }

    @staticmethod
    def _should_retry(
        error: DawlatPlatformError,
    ) -> bool:
        """Return whether automated retry is appropriate."""

        if not error.retryable:
            return False

        return error.disposition in {
            FailureDisposition.RETRYABLE,
            FailureDisposition.RECOVERABLE,
        }


_default_error_handler = EnterpriseErrorHandler()


def get_error_handler() -> EnterpriseErrorHandler:
    """Return the shared enterprise error handler."""

    return _default_error_handler


def handle_exception(
    error: Exception,
    *,
    context: ResilienceContext | None = None,
    operation_name: str = "",
    include_traceback: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ErrorHandlingResult:
    """Handle an exception with the shared handler."""

    return get_error_handler().handle(
        error,
        context=context,
        operation_name=operation_name,
        include_traceback=include_traceback,
        metadata=metadata,
    )


def safe_execute(
    operation: Callable[[], ResultType],
    *,
    operation_name: str,
    context: ResilienceContext | None = None,
) -> ResultType | ErrorResponse:
    """Execute an operation with safe error conversion."""

    return get_error_handler().execute(
        operation,
        operation_name=operation_name,
        context=context,
    )