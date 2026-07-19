"""Results produced by the enterprise procurement scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_scheduler_models import SchedulerTask


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DispatchAssignment:
    task_id: str
    resource_id: str
    queue_position: int
    scheduling_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "resource_id": self.resource_id,
            "queue_position": self.queue_position,
            "scheduling_score": self.scheduling_score,
        }


@dataclass(frozen=True)
class EnterpriseSchedulerResult:
    dispatched_tasks: tuple[SchedulerTask, ...]
    pending_tasks: tuple[SchedulerTask, ...]
    blocked_tasks: tuple[SchedulerTask, ...]
    assignments: tuple[DispatchAssignment, ...]
    evaluated_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dispatched_tasks", tuple(self.dispatched_tasks))
        object.__setattr__(self, "pending_tasks", tuple(self.pending_tasks))
        object.__setattr__(self, "blocked_tasks", tuple(self.blocked_tasks))
        object.__setattr__(self, "assignments", tuple(self.assignments))
        object.__setattr__(self, "policy_id", str(self.policy_id or "").strip())
        object.__setattr__(self, "policy_version", str(self.policy_version or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def dispatched_count(self) -> int:
        return len(self.dispatched_tasks)

    @property
    def pending_count(self) -> int:
        return len(self.pending_tasks)

    @property
    def blocked_count(self) -> int:
        return len(self.blocked_tasks)

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "dispatched_count": self.dispatched_count,
            "pending_count": self.pending_count,
            "blocked_count": self.blocked_count,
            "metadata": redact_mapping(self.metadata),
            "dispatched_tasks": [task.as_dict() for task in self.dispatched_tasks],
            "pending_tasks": [task.as_dict() for task in self.pending_tasks],
            "blocked_tasks": [task.as_dict() for task in self.blocked_tasks],
            "assignments": [assignment.as_dict() for assignment in self.assignments],
        }