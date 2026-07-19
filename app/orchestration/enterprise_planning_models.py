"""Immutable models for enterprise planning intelligence."""

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


class EnterprisePlanStatus(str, Enum):
    """Lifecycle states for an enterprise plan."""

    DRAFT = "draft"
    VALIDATED = "validated"
    APPROVED = "approved"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EnterprisePlanPriority(str, Enum):
    """Priority bands for plans, goals and milestones."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EnterprisePlanDomain(str, Enum):
    """Supported planning domains."""

    PROCUREMENT = "procurement"
    SUPPLIER = "supplier"
    SHIPMENT = "shipment"
    INVENTORY = "inventory"
    FINANCIAL = "financial"
    RISK = "risk"
    COMPLIANCE = "compliance"
    OPPORTUNITY = "opportunity"
    TECHNOLOGY = "technology"
    OPERATIONS = "operations"


class EnterpriseGoalStatus(str, Enum):
    """Lifecycle states for enterprise goals."""

    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EnterpriseMilestoneStatus(str, Enum):
    """Lifecycle states for enterprise milestones."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    MISSED = "missed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class EnterprisePlanningResource:
    """Capacity available to execute a plan."""

    resource_id: str
    name: str
    capacity_units: float
    available_units: float
    cost_per_unit: float = 0.0
    capabilities: tuple[str, ...] = ()
    enabled: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.resource_id or "").strip():
            raise ValueError("Planning resource ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Planning resource name is required.")
        if self.capacity_units < 0:
            raise ValueError("Resource capacity cannot be negative.")
        if self.available_units < 0:
            raise ValueError("Available resource capacity cannot be negative.")
        if self.available_units > self.capacity_units:
            raise ValueError(
                "Available resource capacity cannot exceed total capacity."
            )
        if self.cost_per_unit < 0:
            raise ValueError("Resource cost per unit cannot be negative.")

        object.__setattr__(
            self,
            "resource_id",
            str(self.resource_id).strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name).strip(),
        )
        object.__setattr__(
            self,
            "capabilities",
            tuple(str(item).strip() for item in self.capabilities if str(item).strip()),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def utilisation_rate(self) -> float:
        """Return current utilisation as a percentage."""

        if self.capacity_units == 0:
            return 0.0

        used_units = self.capacity_units - self.available_units
        return round((used_units / self.capacity_units) * 100.0, 2)


@dataclass(frozen=True)
class EnterpriseGoal:
    """One goal in an enterprise plan."""

    name: str
    domain: EnterprisePlanDomain
    estimated_duration_hours: float
    required_capacity_units: float
    goal_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    description: str = ""
    priority: EnterprisePlanPriority = EnterprisePlanPriority.NORMAL
    status: EnterpriseGoalStatus = EnterpriseGoalStatus.PENDING
    depends_on: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    planned_start_at: str = ""
    planned_end_at: str = ""
    progress_percentage: float = 0.0
    owner_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.goal_id or "").strip():
            raise ValueError("Enterprise goal ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise goal name is required.")
        if self.estimated_duration_hours <= 0:
            raise ValueError("Goal duration must be greater than zero.")
        if self.required_capacity_units < 0:
            raise ValueError("Required capacity cannot be negative.")
        if not 0 <= self.progress_percentage <= 100:
            raise ValueError("Goal progress must be between 0 and 100.")
        if self.goal_id in self.depends_on:
            raise ValueError("A goal cannot depend on itself.")

        cleaned_dependencies = tuple(
            str(item).strip()
            for item in self.depends_on
            if str(item).strip()
        )

        if len(cleaned_dependencies) != len(set(cleaned_dependencies)):
            raise ValueError("Goal dependencies must be unique.")

        object.__setattr__(
            self,
            "goal_id",
            str(self.goal_id).strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name).strip(),
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
            "required_capabilities",
            tuple(
                str(item).strip()
                for item in self.required_capabilities
                if str(item).strip()
            ),
        )
        object.__setattr__(
            self,
            "planned_start_at",
            str(self.planned_start_at or "").strip(),
        )
        object.__setattr__(
            self,
            "planned_end_at",
            str(self.planned_end_at or "").strip(),
        )
        object.__setattr__(
            self,
            "owner_id",
            str(self.owner_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def is_terminal(self) -> bool:
        """Return whether the goal has reached a terminal state."""

        return self.status in {
            EnterpriseGoalStatus.COMPLETED,
            EnterpriseGoalStatus.FAILED,
            EnterpriseGoalStatus.CANCELLED,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "goal_id": self.goal_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "estimated_duration_hours": self.estimated_duration_hours,
            "required_capacity_units": self.required_capacity_units,
            "depends_on": list(self.depends_on),
            "required_capabilities": list(self.required_capabilities),
            "planned_start_at": self.planned_start_at,
            "planned_end_at": self.planned_end_at,
            "progress_percentage": self.progress_percentage,
            "owner_id": self.owner_id,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseMilestone:
    """A measurable checkpoint inside an enterprise plan."""

    name: str
    target_at: str
    milestone_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    goal_ids: tuple[str, ...] = ()
    status: EnterpriseMilestoneStatus = EnterpriseMilestoneStatus.PENDING
    completion_percentage: float = 0.0
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.milestone_id or "").strip():
            raise ValueError("Milestone ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Milestone name is required.")
        if not str(self.target_at or "").strip():
            raise ValueError("Milestone target date is required.")
        if not 0 <= self.completion_percentage <= 100:
            raise ValueError(
                "Milestone completion must be between 0 and 100."
            )

        cleaned_goal_ids = tuple(
            str(item).strip()
            for item in self.goal_ids
            if str(item).strip()
        )

        if len(cleaned_goal_ids) != len(set(cleaned_goal_ids)):
            raise ValueError("Milestone goal IDs must be unique.")

        object.__setattr__(
            self,
            "milestone_id",
            str(self.milestone_id).strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name).strip(),
        )
        object.__setattr__(
            self,
            "target_at",
            str(self.target_at).strip(),
        )
        object.__setattr__(
            self,
            "goal_ids",
            cleaned_goal_ids,
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "milestone_id": self.milestone_id,
            "name": self.name,
            "target_at": self.target_at,
            "goal_ids": list(self.goal_ids),
            "status": self.status.value,
            "completion_percentage": self.completion_percentage,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterprisePlan:
    """Top-level enterprise plan."""

    name: str
    goals: tuple[EnterpriseGoal, ...]
    plan_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    description: str = ""
    status: EnterprisePlanStatus = EnterprisePlanStatus.DRAFT
    priority: EnterprisePlanPriority = EnterprisePlanPriority.NORMAL
    milestones: tuple[EnterpriseMilestone, ...] = ()
    resources: tuple[EnterprisePlanningResource, ...] = ()
    version: str = "1.0.0"
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    owner_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.plan_id or "").strip():
            raise ValueError("Enterprise plan ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise plan name is required.")
        if not self.goals:
            raise ValueError("Enterprise plan requires at least one goal.")

        goal_ids = [goal.goal_id for goal in self.goals]

        if len(goal_ids) != len(set(goal_ids)):
            raise ValueError("Enterprise plan goal IDs must be unique.")

        milestone_ids = [
            milestone.milestone_id
            for milestone in self.milestones
        ]

        if len(milestone_ids) != len(set(milestone_ids)):
            raise ValueError("Enterprise plan milestone IDs must be unique.")

        resource_ids = [
            resource.resource_id
            for resource in self.resources
        ]

        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("Enterprise plan resource IDs must be unique.")

        known_goal_ids = set(goal_ids)

        for goal in self.goals:
            missing = set(goal.depends_on) - known_goal_ids
            if missing:
                raise ValueError(
                    "Goal dependencies must reference goals in the same plan."
                )

        for milestone in self.milestones:
            missing = set(milestone.goal_ids) - known_goal_ids
            if missing:
                raise ValueError(
                    "Milestone goal IDs must reference goals in the same plan."
                )

        object.__setattr__(
            self,
            "plan_id",
            str(self.plan_id).strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name).strip(),
        )
        object.__setattr__(
            self,
            "description",
            str(self.description or "").strip(),
        )
        object.__setattr__(
            self,
            "goals",
            tuple(self.goals),
        )
        object.__setattr__(
            self,
            "milestones",
            tuple(self.milestones),
        )
        object.__setattr__(
            self,
            "resources",
            tuple(self.resources),
        )
        object.__setattr__(
            self,
            "version",
            str(self.version or "1.0.0").strip(),
        )
        object.__setattr__(
            self,
            "owner_id",
            str(self.owner_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def progress_percentage(self) -> float:
        """Return mean progress across all goals."""

        return round(
            sum(goal.progress_percentage for goal in self.goals)
            / len(self.goals),
            2,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "version": self.version,
            "created_at": self.created_at,
            "owner_id": self.owner_id,
            "progress_percentage": self.progress_percentage,
            "goals": [goal.as_dict() for goal in self.goals],
            "milestones": [
                milestone.as_dict()
                for milestone in self.milestones
            ],
            "resources": [
                resource.__dict__
                | {
                    "capabilities": list(resource.capabilities),
                    "metadata": redact_mapping(resource.metadata),
                    "utilisation_rate": resource.utilisation_rate,
                }
                for resource in self.resources
            ],
            "metadata": redact_mapping(self.metadata),
        }