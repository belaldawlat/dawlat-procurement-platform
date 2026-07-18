"""Immutable results produced by workflow state transitions."""

from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field as dataclass_field,
)
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.workflow_models import (
    StepStatus,
    WorkflowInstance,
    WorkflowStatus,
)


def _utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TransitionViolation:
    """A deterministic reason why a transition was rejected."""

    code: str
    message: str
    field: str = ""
    current_state: str = ""
    requested_state: str = ""
    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Normalise and redact transition violation data."""

        object.__setattr__(
            self,
            "code",
            str(self.code or "").strip(),
        )
        object.__setattr__(
            self,
            "message",
            str(self.message or "").strip(),
        )
        object.__setattr__(
            self,
            "field",
            str(self.field or "").strip(),
        )
        object.__setattr__(
            self,
            "current_state",
            str(self.current_state or "").strip(),
        )
        object.__setattr__(
            self,
            "requested_state",
            str(self.requested_state or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        payload = asdict(self)
        payload["metadata"] = redact_mapping(self.metadata)
        return payload


@dataclass(frozen=True)
class WorkflowTransitionResult:
    """Result of a workflow-level state transition."""

    accepted: bool
    previous_status: WorkflowStatus
    requested_status: WorkflowStatus
    instance: WorkflowInstance
    reason: str = ""
    actor_id: str = ""
    occurred_at: str = dataclass_field(
        default_factory=_utc_timestamp
    )
    violations: tuple[TransitionViolation, ...] = ()

    @property
    def changed(self) -> bool:
        """Return whether the workflow state actually changed."""

        return (
            self.accepted
            and self.previous_status
            is not self.requested_status
        )

    @property
    def violation_count(self) -> int:
        """Return the number of transition violations."""

        return len(self.violations)

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "accepted": self.accepted,
            "changed": self.changed,
            "previous_status": self.previous_status.value,
            "requested_status": self.requested_status.value,
            "reason": self.reason,
            "actor_id": self.actor_id,
            "occurred_at": self.occurred_at,
            "instance_id": self.instance.instance_id,
            "violations": [
                violation.as_dict()
                for violation in self.violations
            ],
        }


@dataclass(frozen=True)
class StepTransitionResult:
    """Result of a workflow-step state transition."""

    accepted: bool
    step_id: str
    previous_status: StepStatus
    requested_status: StepStatus
    reason: str = ""
    actor_id: str = ""
    occurred_at: str = dataclass_field(
        default_factory=_utc_timestamp
    )
    violations: tuple[TransitionViolation, ...] = ()

    @property
    def changed(self) -> bool:
        """Return whether the step state actually changed."""

        return (
            self.accepted
            and self.previous_status
            is not self.requested_status
        )

    @property
    def violation_count(self) -> int:
        """Return the number of transition violations."""

        return len(self.violations)

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "accepted": self.accepted,
            "changed": self.changed,
            "step_id": self.step_id,
            "previous_status": self.previous_status.value,
            "requested_status": self.requested_status.value,
            "reason": self.reason,
            "actor_id": self.actor_id,
            "occurred_at": self.occurred_at,
            "violations": [
                violation.as_dict()
                for violation in self.violations
            ],
        }