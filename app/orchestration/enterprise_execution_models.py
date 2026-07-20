"""Immutable models for enterprise execution intelligence."""

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


class EnterpriseExecutionStatus(str, Enum):
    """Lifecycle states for an enterprise execution."""

    CREATED = "created"
    VALIDATED = "validated"
    APPROVED = "approved"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EnterpriseExecutionStepStatus(str, Enum):
    """Lifecycle states for one execution step."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    COMPENSATED = "compensated"
    CANCELLED = "cancelled"


class EnterpriseExecutionPriority(str, Enum):
    """Priority bands for execution work."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EnterpriseExecutionMode(str, Enum):
    """Execution behaviour mode."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONTROLLED = "controlled"


class EnterpriseExecutionSideEffect(str, Enum):
    """Side-effect classifications used for governance."""

    NONE = "none"
    INTERNAL = "internal"
    EXTERNAL = "external"
    FINANCIAL = "financial"
    LEGAL = "legal"
    LOGISTICS = "logistics"


@dataclass(frozen=True)
class EnterpriseExecutionStep:
    """One deterministic unit of enterprise execution."""

    name: str
    handler_id: str
    step_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    description: str = ""
    status: EnterpriseExecutionStepStatus = (
        EnterpriseExecutionStepStatus.PENDING
    )
    priority: EnterpriseExecutionPriority = (
        EnterpriseExecutionPriority.NORMAL
    )
    depends_on: tuple[str, ...] = ()
    payload: dict[str, Any] = dataclass_field(default_factory=dict)
    maximum_attempts: int = 3
    attempts: int = 0
    timeout_seconds: int = 300
    side_effect: EnterpriseExecutionSideEffect = (
        EnterpriseExecutionSideEffect.NONE
    )
    requires_human_approval: bool = False
    compensation_handler_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.step_id or "").strip():
            raise ValueError("Enterprise execution step ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise execution step name is required.")
        if not str(self.handler_id or "").strip():
            raise ValueError(
                "Enterprise execution step handler ID is required."
            )
        if self.maximum_attempts < 1:
            raise ValueError("Maximum step attempts must be at least 1.")
        if self.attempts < 0:
            raise ValueError("Step attempts cannot be negative.")
        if self.attempts > self.maximum_attempts:
            raise ValueError(
                "Step attempts cannot exceed maximum attempts."
            )
        if self.timeout_seconds < 1:
            raise ValueError("Step timeout must be at least one second.")
        if self.step_id in self.depends_on:
            raise ValueError(
                "An enterprise execution step cannot depend on itself."
            )

        cleaned_dependencies = tuple(
            str(item).strip()
            for item in self.depends_on
            if str(item).strip()
        )

        if len(cleaned_dependencies) != len(set(cleaned_dependencies)):
            raise ValueError("Execution step dependencies must be unique.")

        object.__setattr__(
            self,
            "step_id",
            str(self.step_id).strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name).strip(),
        )
        object.__setattr__(
            self,
            "handler_id",
            str(self.handler_id).strip(),
        )
        object.__setattr__(
            self,
            "description",
            str(self.description or "").strip(),
        )
        object.__setattr__(
            self,
            "depends_on",
            cleaned_dependencies,
        )
        object.__setattr__(
            self,
            "payload",
            redact_mapping(self.payload),
        )
        object.__setattr__(
            self,
            "compensation_handler_id",
            str(self.compensation_handler_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def is_terminal(self) -> bool:
        """Return whether this step has reached a terminal state."""

        return self.status in {
            EnterpriseExecutionStepStatus.SUCCEEDED,
            EnterpriseExecutionStepStatus.FAILED,
            EnterpriseExecutionStepStatus.SKIPPED,
            EnterpriseExecutionStepStatus.COMPENSATED,
            EnterpriseExecutionStepStatus.CANCELLED,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "handler_id": self.handler_id,
            "status": self.status.value,
            "priority": self.priority.value,
            "depends_on": list(self.depends_on),
            "payload": redact_mapping(self.payload),
            "maximum_attempts": self.maximum_attempts,
            "attempts": self.attempts,
            "timeout_seconds": self.timeout_seconds,
            "side_effect": self.side_effect.value,
            "requires_human_approval": self.requires_human_approval,
            "compensation_handler_id": self.compensation_handler_id,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseExecution:
    """Top-level enterprise execution definition."""

    case_id: str
    name: str
    steps: tuple[EnterpriseExecutionStep, ...]
    execution_id: str = dataclass_field(
        default_factory=lambda: uuid4().hex
    )
    status: EnterpriseExecutionStatus = (
        EnterpriseExecutionStatus.CREATED
    )
    mode: EnterpriseExecutionMode = EnterpriseExecutionMode.CONTROLLED
    priority: EnterpriseExecutionPriority = (
        EnterpriseExecutionPriority.NORMAL
    )
    correlation_id: str = ""
    decision_id: str = ""
    plan_id: str = ""
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.execution_id or "").strip():
            raise ValueError("Enterprise execution ID is required.")
        if not str(self.case_id or "").strip():
            raise ValueError("Enterprise execution case ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise execution name is required.")
        if not self.steps:
            raise ValueError(
                "Enterprise execution requires at least one step."
            )

        step_ids = [step.step_id for step in self.steps]

        if len(step_ids) != len(set(step_ids)):
            raise ValueError(
                "Enterprise execution step IDs must be unique."
            )

        known_step_ids = set(step_ids)

        for step in self.steps:
            missing = set(step.depends_on) - known_step_ids

            if missing:
                raise ValueError(
                    "Execution step dependencies must reference steps "
                    "inside the same execution."
                )

        object.__setattr__(
            self,
            "execution_id",
            str(self.execution_id).strip(),
        )
        object.__setattr__(
            self,
            "case_id",
            str(self.case_id).strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name).strip(),
        )
        object.__setattr__(
            self,
            "steps",
            tuple(self.steps),
        )
        object.__setattr__(
            self,
            "correlation_id",
            str(self.correlation_id or "").strip(),
        )
        object.__setattr__(
            self,
            "decision_id",
            str(self.decision_id or "").strip(),
        )
        object.__setattr__(
            self,
            "plan_id",
            str(self.plan_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def progress_percentage(self) -> float:
        """Return completion percentage across execution steps."""

        completed = sum(
            1
            for step in self.steps
            if step.status
            in {
                EnterpriseExecutionStepStatus.SUCCEEDED,
                EnterpriseExecutionStepStatus.SKIPPED,
                EnterpriseExecutionStepStatus.COMPENSATED,
            }
        )

        return round((completed / len(self.steps)) * 100.0, 2)

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "execution_id": self.execution_id,
            "case_id": self.case_id,
            "name": self.name,
            "status": self.status.value,
            "mode": self.mode.value,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "decision_id": self.decision_id,
            "plan_id": self.plan_id,
            "created_at": self.created_at,
            "progress_percentage": self.progress_percentage,
            "steps": [step.as_dict() for step in self.steps],
            "metadata": redact_mapping(self.metadata),
        }