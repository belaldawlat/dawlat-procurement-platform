"""Result models for enterprise workflow intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_models import (
    EnterpriseWorkflow,
    EnterpriseWorkflowStage,
    EnterpriseWorkflowTask,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class EnterpriseWorkflowIssueSeverity(str, Enum):
    """Severity levels for workflow findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class EnterpriseWorkflowIssue:
    """One workflow validation or runtime issue."""

    code: str
    message: str
    severity: EnterpriseWorkflowIssueSeverity
    blocking: bool = False
    entity_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("Workflow issue code is required.")
        if not str(self.message or "").strip():
            raise ValueError("Workflow issue message is required.")

        object.__setattr__(self, "code", str(self.code).strip())
        object.__setattr__(self, "message", str(self.message).strip())
        object.__setattr__(
            self,
            "entity_id",
            str(self.entity_id or "").strip(),
        )
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "blocking": self.blocking,
            "entity_id": self.entity_id,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowTaskResult:
    """Execution result for one workflow task."""

    task: EnterpriseWorkflowTask
    successful: bool
    output: dict[str, Any]
    error: str = ""
    duration_ms: float = 0.0
    started_at: str = dataclass_field(default_factory=utc_timestamp)
    completed_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("Workflow task duration cannot be negative.")

        object.__setattr__(self, "output", redact_mapping(self.output))
        object.__setattr__(self, "error", str(self.error or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "task": self.task.as_dict(),
            "successful": self.successful,
            "output": redact_mapping(self.output),
            "error": self.error,
            "duration_ms": self.duration_ms,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowStageResult:
    """Execution result for one workflow stage."""

    stage: EnterpriseWorkflowStage
    successful: bool
    task_results: tuple[EnterpriseWorkflowTaskResult, ...]
    issues: tuple[EnterpriseWorkflowIssue, ...] = ()
    duration_ms: float = 0.0
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("Workflow stage duration cannot be negative.")

        object.__setattr__(self, "task_results", tuple(self.task_results))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "stage": self.stage.as_dict(),
            "successful": self.successful,
            "task_results": [
                item.as_dict()
                for item in self.task_results
            ],
            "issues": [item.as_dict() for item in self.issues],
            "duration_ms": self.duration_ms,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowResult:
    """Top-level enterprise workflow result."""

    workflow: EnterpriseWorkflow
    successful: bool
    stage_results: tuple[EnterpriseWorkflowStageResult, ...]
    issues: tuple[EnterpriseWorkflowIssue, ...] = ()
    duration_ms: float = 0.0
    policy_id: str = ""
    policy_version: str = ""
    started_at: str = dataclass_field(default_factory=utc_timestamp)
    completed_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("Workflow duration cannot be negative.")

        object.__setattr__(self, "stage_results", tuple(self.stage_results))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(
            self,
            "policy_id",
            str(self.policy_id or "").strip(),
        )
        object.__setattr__(
            self,
            "policy_version",
            str(self.policy_version or "").strip(),
        )
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def blocking_issues(self) -> tuple[EnterpriseWorkflowIssue, ...]:
        """Return all blocking workflow issues."""

        return tuple(issue for issue in self.issues if issue.blocking)

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "workflow": self.workflow.as_dict(),
            "successful": self.successful,
            "stage_result_count": len(self.stage_results),
            "blocking_issue_count": len(self.blocking_issues),
            "stage_results": [
                item.as_dict()
                for item in self.stage_results
            ],
            "issues": [item.as_dict() for item in self.issues],
            "duration_ms": self.duration_ms,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": redact_mapping(self.metadata),
        }