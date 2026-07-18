"""Core immutable workflow orchestration models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def _utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class WorkflowStatus(str, Enum):
    """Lifecycle states for a workflow instance."""

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class StepStatus(str, Enum):
    """Lifecycle states for an individual workflow step."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class StepType(str, Enum):
    """Supported workflow step classifications."""

    ACTION = "action"
    DECISION = "decision"
    APPROVAL = "approval"
    WAIT = "wait"
    NOTIFICATION = "notification"
    INTEGRATION = "integration"
    COMPENSATION = "compensation"


class FailureStrategy(str, Enum):
    """Permitted failure strategies for workflow steps."""

    FAIL_WORKFLOW = "fail_workflow"
    RETRY = "retry"
    PAUSE = "pause"
    SKIP = "skip"
    COMPENSATE = "compensate"


@dataclass(frozen=True)
class WorkflowStepDefinition:
    """Immutable definition of a workflow step."""

    step_id: str
    name: str
    step_type: StepType = StepType.ACTION
    description: str = ""
    dependencies: tuple[str, ...] = ()
    required_roles: tuple[str, ...] = ()
    failure_strategy: FailureStrategy = (
        FailureStrategy.FAIL_WORKFLOW
    )
    maximum_attempts: int = 1
    timeout_seconds: float | None = None
    compensation_step_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalise definition values."""

        object.__setattr__(
            self,
            "step_id",
            str(self.step_id or "").strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name or "").strip(),
        )
        object.__setattr__(
            self,
            "description",
            str(self.description or "").strip(),
        )
        object.__setattr__(
            self,
            "dependencies",
            tuple(
                str(value).strip()
                for value in self.dependencies
                if str(value).strip()
            ),
        )
        object.__setattr__(
            self,
            "required_roles",
            tuple(
                str(value).strip()
                for value in self.required_roles
                if str(value).strip()
            ),
        )
        object.__setattr__(
            self,
            "compensation_step_id",
            str(
                self.compensation_step_id or ""
            ).strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        payload = asdict(self)
        payload["step_type"] = self.step_type.value
        payload["failure_strategy"] = (
            self.failure_strategy.value
        )
        payload["metadata"] = redact_mapping(self.metadata)
        return payload


@dataclass(frozen=True)
class WorkflowDefinition:
    """Immutable versioned workflow definition."""

    workflow_id: str
    name: str
    version: str
    steps: tuple[WorkflowStepDefinition, ...]
    description: str = ""
    initial_step_id: str = ""
    terminal_step_ids: tuple[str, ...] = ()
    enabled: bool = True
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalise immutable workflow fields."""

        object.__setattr__(
            self,
            "workflow_id",
            str(self.workflow_id or "").strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name or "").strip(),
        )
        object.__setattr__(
            self,
            "version",
            str(self.version or "").strip(),
        )
        object.__setattr__(
            self,
            "description",
            str(self.description or "").strip(),
        )
        object.__setattr__(
            self,
            "steps",
            tuple(self.steps),
        )
        object.__setattr__(
            self,
            "initial_step_id",
            str(self.initial_step_id or "").strip(),
        )
        object.__setattr__(
            self,
            "terminal_step_ids",
            tuple(
                str(value).strip()
                for value in self.terminal_step_ids
                if str(value).strip()
            ),
        )
        object.__setattr__(
            self,
            "tags",
            tuple(
                sorted(
                    {
                        str(value).strip()
                        for value in self.tags
                        if str(value).strip()
                    }
                )
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def registry_key(self) -> str:
        """Return the stable registry key."""

        return f"{self.workflow_id}:{self.version}"

    @property
    def step_ids(self) -> tuple[str, ...]:
        """Return step identifiers in definition order."""

        return tuple(step.step_id for step in self.steps)

    def get_step(
        self,
        step_id: str,
    ) -> WorkflowStepDefinition | None:
        """Return a workflow step by identifier."""

        cleaned_step_id = str(step_id or "").strip()

        for step in self.steps:
            if step.step_id == cleaned_step_id:
                return step

        return None

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "initial_step_id": self.initial_step_id,
            "terminal_step_ids": list(
                self.terminal_step_ids
            ),
            "enabled": self.enabled,
            "tags": list(self.tags),
            "metadata": redact_mapping(self.metadata),
            "steps": [
                step.as_dict()
                for step in self.steps
            ],
        }


@dataclass(frozen=True)
class WorkflowTransition:
    """Immutable workflow transition record."""

    from_status: WorkflowStatus
    to_status: WorkflowStatus
    reason: str = ""
    actor_id: str = ""
    occurred_at: str = field(default_factory=_utc_timestamp)


@dataclass(frozen=True)
class WorkflowInstance:
    """Immutable runtime snapshot of a workflow."""

    workflow_id: str
    workflow_version: str
    instance_id: str = field(
        default_factory=lambda: uuid4().hex
    )
    status: WorkflowStatus = WorkflowStatus.CREATED
    current_step_id: str = ""
    completed_step_ids: tuple[str, ...] = ()
    failed_step_ids: tuple[str, ...] = ()
    transitions: tuple[WorkflowTransition, ...] = ()
    created_at: str = field(default_factory=_utc_timestamp)
    updated_at: str = field(default_factory=_utc_timestamp)
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalise runtime instance data."""

        object.__setattr__(
            self,
            "workflow_id",
            str(self.workflow_id or "").strip(),
        )
        object.__setattr__(
            self,
            "workflow_version",
            str(self.workflow_version or "").strip(),
        )
        object.__setattr__(
            self,
            "instance_id",
            str(self.instance_id or uuid4().hex).strip(),
        )
        object.__setattr__(
            self,
            "current_step_id",
            str(self.current_step_id or "").strip(),
        )
        object.__setattr__(
            self,
            "completed_step_ids",
            tuple(self.completed_step_ids),
        )
        object.__setattr__(
            self,
            "failed_step_ids",
            tuple(self.failed_step_ids),
        )
        object.__setattr__(
            self,
            "transitions",
            tuple(self.transitions),
        )
        object.__setattr__(
            self,
            "data",
            redact_mapping(self.data),
        )