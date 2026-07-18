"""Enterprise exception hierarchy for the Dawlat platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


class ErrorCategory(str, Enum):
    """High-level enterprise error categories."""

    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORISATION = "authorisation"
    SECURITY = "security"
    CONFIGURATION = "configuration"
    DATABASE = "database"
    NETWORK = "network"
    EXTERNAL_SERVICE = "external_service"
    BUSINESS_RULE = "business_rule"
    CONCURRENCY = "concurrency"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    DATA_INTEGRITY = "data_integrity"
    INTERNAL = "internal"


class ErrorSeverity(str, Enum):
    """Operational severity assigned to enterprise errors."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FailureDisposition(str, Enum):
    """Expected handling strategy for a failure."""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    FAIL_CLOSED = "fail_closed"
    RECOVERABLE = "recoverable"
    FATAL = "fatal"


@dataclass(frozen=True)
class ErrorDescriptor:
    """Immutable, serialisable enterprise error description."""

    error_id: str
    code: str
    category: ErrorCategory
    severity: ErrorSeverity
    disposition: FailureDisposition
    safe_message: str
    technical_message: str
    retryable: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def safe_payload(self) -> dict[str, Any]:
        """Return a user-safe representation without secrets."""

        return {
            "error_id": self.error_id,
            "code": self.code,
            "category": self.category.value,
            "severity": self.severity.value,
            "disposition": self.disposition.value,
            "message": self.safe_message,
            "retryable": self.retryable,
            "metadata": redact_mapping(self.metadata),
        }

    def diagnostic_payload(self) -> dict[str, Any]:
        """Return a redacted diagnostic representation."""

        return {
            **self.safe_payload(),
            "technical_message": self.technical_message,
        }


class DawlatPlatformError(Exception):
    """Base exception for controlled enterprise failures."""

    default_code = "DAWLAT_INTERNAL_ERROR"
    default_category = ErrorCategory.INTERNAL
    default_severity = ErrorSeverity.HIGH
    default_disposition = FailureDisposition.NON_RETRYABLE
    default_safe_message = (
        "The platform could not complete the requested operation."
    )

    def __init__(
        self,
        technical_message: str = "",
        *,
        safe_message: str | None = None,
        code: str | None = None,
        category: ErrorCategory | None = None,
        severity: ErrorSeverity | None = None,
        disposition: FailureDisposition | None = None,
        retryable: bool | None = None,
        metadata: dict[str, Any] | None = None,
        error_id: str | None = None,
    ) -> None:
        resolved_disposition = (
            disposition or self.default_disposition
        )

        resolved_retryable = (
            retryable
            if retryable is not None
            else resolved_disposition
            is FailureDisposition.RETRYABLE
        )

        self.descriptor = ErrorDescriptor(
            error_id=str(error_id or uuid4().hex),
            code=str(code or self.default_code),
            category=category or self.default_category,
            severity=severity or self.default_severity,
            disposition=resolved_disposition,
            safe_message=str(
                safe_message or self.default_safe_message
            ),
            technical_message=str(
                technical_message
                or self.default_safe_message
            ),
            retryable=resolved_retryable,
            metadata=redact_mapping(metadata or {}),
        )

        super().__init__(self.descriptor.technical_message)

    @property
    def error_id(self) -> str:
        """Return the correlation-safe error identifier."""

        return self.descriptor.error_id

    @property
    def code(self) -> str:
        """Return the stable enterprise error code."""

        return self.descriptor.code

    @property
    def category(self) -> ErrorCategory:
        """Return the error category."""

        return self.descriptor.category

    @property
    def severity(self) -> ErrorSeverity:
        """Return the error severity."""

        return self.descriptor.severity

    @property
    def disposition(self) -> FailureDisposition:
        """Return the expected handling disposition."""

        return self.descriptor.disposition

    @property
    def retryable(self) -> bool:
        """Return whether retry is allowed."""

        return self.descriptor.retryable

    @property
    def safe_message(self) -> str:
        """Return the message safe to expose to users."""

        return self.descriptor.safe_message

    def safe_payload(self) -> dict[str, Any]:
        """Return a safe external representation."""

        return self.descriptor.safe_payload()

    def diagnostic_payload(self) -> dict[str, Any]:
        """Return a redacted diagnostic representation."""

        return self.descriptor.diagnostic_payload()


class ValidationError(DawlatPlatformError):
    """Raised when supplied input fails validation."""

    default_code = "DAWLAT_VALIDATION_ERROR"
    default_category = ErrorCategory.VALIDATION
    default_severity = ErrorSeverity.LOW
    default_disposition = FailureDisposition.NON_RETRYABLE
    default_safe_message = "The supplied information is invalid."


class AuthenticationError(DawlatPlatformError):
    """Raised when identity verification fails."""

    default_code = "DAWLAT_AUTHENTICATION_FAILED"
    default_category = ErrorCategory.AUTHENTICATION
    default_severity = ErrorSeverity.HIGH
    default_disposition = FailureDisposition.FAIL_CLOSED
    default_safe_message = "Authentication was unsuccessful."


class AuthorisationError(DawlatPlatformError):
    """Raised when access permission is denied."""

    default_code = "DAWLAT_ACCESS_DENIED"
    default_category = ErrorCategory.AUTHORISATION
    default_severity = ErrorSeverity.HIGH
    default_disposition = FailureDisposition.FAIL_CLOSED
    default_safe_message = (
        "You are not authorised to perform this operation."
    )


class SecurityViolationError(DawlatPlatformError):
    """Raised when a security control detects unsafe activity."""

    default_code = "DAWLAT_SECURITY_VIOLATION"
    default_category = ErrorCategory.SECURITY
    default_severity = ErrorSeverity.CRITICAL
    default_disposition = FailureDisposition.FAIL_CLOSED
    default_safe_message = (
        "The operation was blocked by a security control."
    )


class ConfigurationError(DawlatPlatformError):
    """Raised when platform configuration is invalid."""

    default_code = "DAWLAT_CONFIGURATION_ERROR"
    default_category = ErrorCategory.CONFIGURATION
    default_severity = ErrorSeverity.CRITICAL
    default_disposition = FailureDisposition.FATAL
    default_safe_message = (
        "The platform configuration is incomplete or unsafe."
    )


class DatabaseError(DawlatPlatformError):
    """Raised for controlled database failures."""

    default_code = "DAWLAT_DATABASE_ERROR"
    default_category = ErrorCategory.DATABASE
    default_severity = ErrorSeverity.HIGH
    default_disposition = FailureDisposition.RETRYABLE
    default_safe_message = (
        "A data service is temporarily unavailable."
    )


class ExternalServiceError(DawlatPlatformError):
    """Raised when an external dependency fails."""

    default_code = "DAWLAT_EXTERNAL_SERVICE_ERROR"
    default_category = ErrorCategory.EXTERNAL_SERVICE
    default_severity = ErrorSeverity.MEDIUM
    default_disposition = FailureDisposition.RETRYABLE
    default_safe_message = (
        "An external service is temporarily unavailable."
    )


class NetworkError(DawlatPlatformError):
    """Raised for recoverable network failures."""

    default_code = "DAWLAT_NETWORK_ERROR"
    default_category = ErrorCategory.NETWORK
    default_severity = ErrorSeverity.MEDIUM
    default_disposition = FailureDisposition.RETRYABLE
    default_safe_message = (
        "The network operation could not be completed."
    )


class OperationTimeoutError(DawlatPlatformError):
    """Raised when an operation exceeds its time limit."""

    default_code = "DAWLAT_OPERATION_TIMEOUT"
    default_category = ErrorCategory.TIMEOUT
    default_severity = ErrorSeverity.MEDIUM
    default_disposition = FailureDisposition.RETRYABLE
    default_safe_message = "The operation timed out."


class BusinessRuleError(DawlatPlatformError):
    """Raised when an enterprise business rule blocks an action."""

    default_code = "DAWLAT_BUSINESS_RULE_BLOCKED"
    default_category = ErrorCategory.BUSINESS_RULE
    default_severity = ErrorSeverity.MEDIUM
    default_disposition = FailureDisposition.NON_RETRYABLE
    default_safe_message = (
        "The operation is not permitted by the current business rules."
    )


class DataIntegrityError(DawlatPlatformError):
    """Raised when data consistency or integrity is compromised."""

    default_code = "DAWLAT_DATA_INTEGRITY_ERROR"
    default_category = ErrorCategory.DATA_INTEGRITY
    default_severity = ErrorSeverity.CRITICAL
    default_disposition = FailureDisposition.FAIL_CLOSED
    default_safe_message = (
        "The operation was stopped to protect data integrity."
    )


class ConcurrencyError(DawlatPlatformError):
    """Raised when concurrent modification is detected."""

    default_code = "DAWLAT_CONCURRENCY_ERROR"
    default_category = ErrorCategory.CONCURRENCY
    default_severity = ErrorSeverity.MEDIUM
    default_disposition = FailureDisposition.RETRYABLE
    default_safe_message = (
        "The record changed during the operation. Please try again."
    )


class ResourceUnavailableError(DawlatPlatformError):
    """Raised when a required resource is unavailable."""

    default_code = "DAWLAT_RESOURCE_UNAVAILABLE"
    default_category = ErrorCategory.RESOURCE
    default_severity = ErrorSeverity.MEDIUM
    default_disposition = FailureDisposition.RETRYABLE
    default_safe_message = (
        "A required platform resource is unavailable."
    )


class CircuitOpenError(DawlatPlatformError):
    """Raised when a circuit breaker blocks an operation."""

    default_code = "DAWLAT_CIRCUIT_OPEN"
    default_category = ErrorCategory.EXTERNAL_SERVICE
    default_severity = ErrorSeverity.HIGH
    default_disposition = FailureDisposition.RECOVERABLE
    default_safe_message = (
        "The service is temporarily protected from further requests."
    )


class RecoveryFailedError(DawlatPlatformError):
    """Raised when a recovery strategy cannot restore operation."""

    default_code = "DAWLAT_RECOVERY_FAILED"
    default_category = ErrorCategory.INTERNAL
    default_severity = ErrorSeverity.HIGH
    default_disposition = FailureDisposition.FATAL
    default_safe_message = (
        "The platform could not safely recover from the failure."
    )


def normalise_exception(
    error: Exception,
) -> DawlatPlatformError:
    """Convert any exception into a controlled enterprise error."""

    if isinstance(error, DawlatPlatformError):
        return error

    if isinstance(error, TimeoutError):
        return OperationTimeoutError(
            technical_message=str(error) or "Operation timed out."
        )

    if isinstance(error, ConnectionError):
        return NetworkError(
            technical_message=str(error) or "Connection failed."
        )

    if isinstance(error, ValueError):
        return ValidationError(
            technical_message=str(error) or "Invalid value."
        )

    if isinstance(error, PermissionError):
        return AuthorisationError(
            technical_message=str(error) or "Permission denied."
        )

    return DawlatPlatformError(
        technical_message=(
            str(error) or error.__class__.__name__
        ),
        metadata={
            "original_exception_type": (
                error.__class__.__name__
            ),
        },
    )