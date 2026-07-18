"""Enterprise workflow orchestration exceptions."""

from __future__ import annotations

from app.resilience.exceptions import (
    BusinessRuleError,
    DataIntegrityError,
    DawlatPlatformError,
    ErrorCategory,
    ErrorSeverity,
    FailureDisposition,
    ValidationError,
)


class WorkflowError(DawlatPlatformError):
    """Base exception for workflow orchestration failures."""

    default_code = "DAWLAT_WORKFLOW_ERROR"
    default_category = ErrorCategory.BUSINESS_RULE
    default_severity = ErrorSeverity.HIGH
    default_disposition = FailureDisposition.NON_RETRYABLE
    default_safe_message = (
        "The workflow operation could not be completed."
    )


class WorkflowValidationError(ValidationError):
    """Raised when a workflow definition is invalid."""

    default_code = "DAWLAT_WORKFLOW_VALIDATION_ERROR"
    default_safe_message = (
        "The workflow definition is invalid."
    )


class WorkflowRegistrationError(WorkflowError):
    """Raised when workflow registration fails."""

    default_code = "DAWLAT_WORKFLOW_REGISTRATION_ERROR"
    default_safe_message = (
        "The workflow could not be registered."
    )


class WorkflowNotFoundError(WorkflowError):
    """Raised when a requested workflow does not exist."""

    default_code = "DAWLAT_WORKFLOW_NOT_FOUND"
    default_safe_message = (
        "The requested workflow was not found."
    )


class DuplicateWorkflowError(WorkflowRegistrationError):
    """Raised when a workflow identifier is already registered."""

    default_code = "DAWLAT_DUPLICATE_WORKFLOW"
    default_safe_message = (
        "A workflow with this identifier already exists."
    )


class WorkflowStateError(BusinessRuleError):
    """Raised when a workflow state transition is invalid."""

    default_code = "DAWLAT_WORKFLOW_STATE_ERROR"
    default_safe_message = (
        "The requested workflow state change is not permitted."
    )


class WorkflowIntegrityError(DataIntegrityError):
    """Raised when workflow integrity is compromised."""

    default_code = "DAWLAT_WORKFLOW_INTEGRITY_ERROR"
    default_safe_message = (
        "The workflow was stopped to protect process integrity."
    )