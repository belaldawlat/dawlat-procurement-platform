"""Immutable domain models for enterprise workflow intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class EnterpriseWorkflowStatus(str, Enum):
    """Lifecycle states for an enterprise workflow."""

    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class EnterpriseWorkflowStageStatus(str, Enum):
    """Lifecycle states for one workflow stage."""

    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class EnterpriseWorkflowTaskStatus(str, Enum):
    """Lifecycle states for one workflow task."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class EnterpriseWorkflowPriority(str, Enum):
    """Priority bands for workflows, stages and tasks."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EnterpriseWorkflowApprovalMode(str, Enum):
    """Approval modes supported by enterprise workflows."""

    NONE = "none"
    SINGLE = "single"
    UNANIMOUS = "unanimous"
    QUORUM = "quorum"


@dataclass(frozen=True)
class EnterpriseWorkflowTask:
    """One executable unit inside a workflow stage."""

    name: str
    handler_id: str
    task_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    description: str = ""
    status: EnterpriseWorkflowTaskStatus = (
        EnterpriseWorkflowTaskStatus.PENDING
    )
    priority: EnterpriseWorkflowPriority = (
        EnterpriseWorkflowPriority.NORMAL
    )
    depends_on: tuple[str, ...] = ()
    payload: dict[str, Any] = dataclass_field(default_factory=dict)
    timeout_seconds: int = 300
    maximum_attempts: int = 3
    requires_approval: bool = False
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.task_id or "").strip():
            raise ValueError("Workflow task ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Workflow task name is required.")
        if not str(self.handler_id or "").strip():
            raise ValueError("Workflow task handler ID is required.")
        if self.timeout_seconds < 1:
            raise ValueError("Workflow task timeout must be at least 1.")
        if self.maximum_attempts < 1:
            raise ValueError("Workflow task attempts must be at least 1.")

        cleaned_dependencies = tuple(
            str(item).strip()
            for item in self.depends_on
            if str(item).strip()
        )

        if self.task_id in cleaned_dependencies:
            raise ValueError("A workflow task cannot depend on itself.")
        if len(cleaned_dependencies) != len(set(cleaned_dependencies)):
            raise ValueError("Workflow task dependencies must be unique.")

        object.__setattr__(self, "task_id", str(self.task_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "handler_id", str(self.handler_id).strip())
        object.__setattr__(
            self,
            "description",
            str(self.description or "").strip(),
        )
        object.__setattr__(self, "depends_on", cleaned_dependencies)
        object.__setattr__(self, "payload", redact_mapping(self.payload))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def is_terminal(self) -> bool:
        """Return whether the task has reached a terminal state."""

        return self.status in {
            EnterpriseWorkflowTaskStatus.SUCCEEDED,
            EnterpriseWorkflowTaskStatus.FAILED,
            EnterpriseWorkflowTaskStatus.SKIPPED,
            EnterpriseWorkflowTaskStatus.CANCELLED,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "handler_id": self.handler_id,
            "status": self.status.value,
            "priority": self.priority.value,
            "depends_on": list(self.depends_on),
            "payload": redact_mapping(self.payload),
            "timeout_seconds": self.timeout_seconds,
            "maximum_attempts": self.maximum_attempts,
            "requires_approval": self.requires_approval,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowStage:
    """One governed stage inside an enterprise workflow."""

    name: str
    tasks: tuple[EnterpriseWorkflowTask, ...]
    stage_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    description: str = ""
    status: EnterpriseWorkflowStageStatus = (
        EnterpriseWorkflowStageStatus.PENDING
    )
    priority: EnterpriseWorkflowPriority = (
        EnterpriseWorkflowPriority.NORMAL
    )
    depends_on: tuple[str, ...] = ()
    approval_mode: EnterpriseWorkflowApprovalMode = (
        EnterpriseWorkflowApprovalMode.NONE
    )
    required_approvals: int = 0
    approver_roles: tuple[str, ...] = ()
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.stage_id or "").strip():
            raise ValueError("Workflow stage ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Workflow stage name is required.")
        if not self.tasks:
            raise ValueError("Workflow stage requires at least one task.")

        task_ids = [task.task_id for task in self.tasks]

        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Workflow task IDs must be unique within a stage.")

        known_task_ids = set(task_ids)

        for task in self.tasks:
            missing = set(task.depends_on) - known_task_ids
            if missing:
                raise ValueError(
                    "Workflow task dependencies must reference tasks "
                    "inside the same stage."
                )

        cleaned_dependencies = tuple(
            str(item).strip()
            for item in self.depends_on
            if str(item).strip()
        )
        cleaned_roles = tuple(
            str(item).strip()
            for item in self.approver_roles
            if str(item).strip()
        )

        if self.stage_id in cleaned_dependencies:
            raise ValueError("A workflow stage cannot depend on itself.")
        if len(cleaned_dependencies) != len(set(cleaned_dependencies)):
            raise ValueError("Workflow stage dependencies must be unique.")
        if len(cleaned_roles) != len(set(cleaned_roles)):
            raise ValueError("Workflow approver roles must be unique.")
        if self.required_approvals < 0:
            raise ValueError("Required approvals cannot be negative.")
        if (
            self.approval_mode is EnterpriseWorkflowApprovalMode.NONE
            and self.required_approvals != 0
        ):
            raise ValueError(
                "Approval count must be zero when approval mode is none."
            )
        if (
            self.approval_mode is not EnterpriseWorkflowApprovalMode.NONE
            and self.required_approvals < 1
        ):
            raise ValueError(
                "Approval mode requires at least one approval."
            )

        object.__setattr__(self, "stage_id", str(self.stage_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(
            self,
            "description",
            str(self.description or "").strip(),
        )
        object.__setattr__(self, "tasks", tuple(self.tasks))
        object.__setattr__(self, "depends_on", cleaned_dependencies)
        object.__setattr__(self, "approver_roles", cleaned_roles)
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def progress_percentage(self) -> float:
        """Return stage completion percentage."""

        complete = sum(
            1
            for task in self.tasks
            if task.status
            in {
                EnterpriseWorkflowTaskStatus.SUCCEEDED,
                EnterpriseWorkflowTaskStatus.SKIPPED,
            }
        )

        return round((complete / len(self.tasks)) * 100.0, 2)

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "depends_on": list(self.depends_on),
            "approval_mode": self.approval_mode.value,
            "required_approvals": self.required_approvals,
            "approver_roles": list(self.approver_roles),
            "progress_percentage": self.progress_percentage,
            "tasks": [task.as_dict() for task in self.tasks],
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflow:
    """Top-level enterprise workflow instance."""

    case_id: str
    name: str
    stages: tuple[EnterpriseWorkflowStage, ...]
    workflow_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    template_id: str = ""
    template_version: str = ""
    status: EnterpriseWorkflowStatus = EnterpriseWorkflowStatus.DRAFT
    priority: EnterpriseWorkflowPriority = (
        EnterpriseWorkflowPriority.NORMAL
    )
    correlation_id: str = ""
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.workflow_id or "").strip():
            raise ValueError("Workflow ID is required.")
        if not str(self.case_id or "").strip():
            raise ValueError("Workflow case ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Workflow name is required.")
        if not self.stages:
            raise ValueError("Workflow requires at least one stage.")

        stage_ids = [stage.stage_id for stage in self.stages]

        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("Workflow stage IDs must be unique.")

        known_stage_ids = set(stage_ids)

        for stage in self.stages:
            missing = set(stage.depends_on) - known_stage_ids
            if missing:
                raise ValueError(
                    "Workflow stage dependencies must reference stages "
                    "inside the same workflow."
                )

        object.__setattr__(self, "workflow_id", str(self.workflow_id).strip())
        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(
            self,
            "template_id",
            str(self.template_id or "").strip(),
        )
        object.__setattr__(
            self,
            "template_version",
            str(self.template_version or "").strip(),
        )
        object.__setattr__(
            self,
            "correlation_id",
            str(self.correlation_id or "").strip(),
        )
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def progress_percentage(self) -> float:
        """Return workflow completion percentage."""

        completed = sum(
            1
            for stage in self.stages
            if stage.status
            in {
                EnterpriseWorkflowStageStatus.COMPLETED,
                EnterpriseWorkflowStageStatus.SKIPPED,
            }
        )

        return round((completed / len(self.stages)) * 100.0, 2)

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "workflow_id": self.workflow_id,
            "case_id": self.case_id,
            "name": self.name,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "status": self.status.value,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at,
            "progress_percentage": self.progress_percentage,
            "stages": [stage.as_dict() for stage in self.stages],
            "metadata": redact_mapping(self.metadata),
        }