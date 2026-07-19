"""Results produced by enterprise planning intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_planning_models import (
    EnterprisePlan,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class EnterprisePlanningIssueSeverity(str, Enum):
    """Severity assigned to planning findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class EnterprisePlanningIssue:
    """One validation, capacity or scheduling issue."""

    code: str
    message: str
    severity: EnterprisePlanningIssueSeverity
    blocking: bool = False
    entity_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("Planning issue code is required.")
        if not str(self.message or "").strip():
            raise ValueError("Planning issue message is required.")

        object.__setattr__(
            self,
            "code",
            str(self.code).strip(),
        )
        object.__setattr__(
            self,
            "message",
            str(self.message).strip(),
        )
        object.__setattr__(
            self,
            "entity_id",
            str(self.entity_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

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
class EnterpriseGoalSchedule:
    """Calculated schedule for one enterprise goal."""

    goal_id: str
    sequence: int
    earliest_start_hour: float
    earliest_finish_hour: float
    latest_start_hour: float
    latest_finish_hour: float
    total_float_hours: float
    critical: bool
    assigned_resource_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.goal_id or "").strip():
            raise ValueError("Scheduled goal ID is required.")
        if self.sequence < 1:
            raise ValueError("Goal schedule sequence must be at least 1.")
        if self.earliest_start_hour < 0:
            raise ValueError("Earliest start cannot be negative.")
        if self.earliest_finish_hour < self.earliest_start_hour:
            raise ValueError(
                "Earliest finish cannot be before earliest start."
            )
        if self.latest_start_hour < 0:
            raise ValueError("Latest start cannot be negative.")
        if self.latest_finish_hour < self.latest_start_hour:
            raise ValueError(
                "Latest finish cannot be before latest start."
            )

        object.__setattr__(
            self,
            "goal_id",
            str(self.goal_id).strip(),
        )
        object.__setattr__(
            self,
            "assigned_resource_ids",
            tuple(self.assigned_resource_ids),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "goal_id": self.goal_id,
            "sequence": self.sequence,
            "earliest_start_hour": self.earliest_start_hour,
            "earliest_finish_hour": self.earliest_finish_hour,
            "latest_start_hour": self.latest_start_hour,
            "latest_finish_hour": self.latest_finish_hour,
            "total_float_hours": self.total_float_hours,
            "critical": self.critical,
            "assigned_resource_ids": list(
                self.assigned_resource_ids
            ),
        }


@dataclass(frozen=True)
class EnterprisePlanningResult:
    """Immutable result of planning analysis."""

    plan: EnterprisePlan
    valid: bool
    feasible: bool
    total_duration_hours: float
    critical_path_goal_ids: tuple[str, ...]
    schedules: tuple[EnterpriseGoalSchedule, ...]
    issues: tuple[EnterprisePlanningIssue, ...]
    evaluated_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.total_duration_hours < 0:
            raise ValueError(
                "Total plan duration cannot be negative."
            )

        object.__setattr__(
            self,
            "critical_path_goal_ids",
            tuple(self.critical_path_goal_ids),
        )
        object.__setattr__(
            self,
            "schedules",
            tuple(self.schedules),
        )
        object.__setattr__(
            self,
            "issues",
            tuple(self.issues),
        )
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
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def blocking_issues(
        self,
    ) -> tuple[EnterprisePlanningIssue, ...]:
        """Return all blocking issues."""

        return tuple(
            issue
            for issue in self.issues
            if issue.blocking
        )

    @property
    def critical_issues(
        self,
    ) -> tuple[EnterprisePlanningIssue, ...]:
        """Return all critical issues."""

        return tuple(
            issue
            for issue in self.issues
            if issue.severity
            is EnterprisePlanningIssueSeverity.CRITICAL
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "plan": self.plan.as_dict(),
            "valid": self.valid,
            "feasible": self.feasible,
            "total_duration_hours": self.total_duration_hours,
            "critical_path_goal_ids": list(
                self.critical_path_goal_ids
            ),
            "schedules": [
                schedule.as_dict()
                for schedule in self.schedules
            ],
            "issues": [
                issue.as_dict()
                for issue in self.issues
            ],
            "blocking_issue_count": len(self.blocking_issues),
            "critical_issue_count": len(self.critical_issues),
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "metadata": redact_mapping(self.metadata),
        }