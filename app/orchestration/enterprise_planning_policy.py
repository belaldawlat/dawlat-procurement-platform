"""Policy controls for enterprise planning intelligence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterprisePlanningPolicy:
    """Immutable planning thresholds and safety controls."""

    policy_id: str
    name: str
    version: str = "1.0.0"
    maximum_plan_goals: int = 500
    maximum_dependency_depth: int = 100
    maximum_plan_duration_hours: float = 100_000.0
    maximum_resource_utilisation: float = 90.0
    minimum_capacity_buffer_percentage: float = 10.0
    critical_path_tolerance_hours: float = 0.01
    require_acyclic_dependencies: bool = True
    require_resource_feasibility: bool = True
    require_milestone_goal_links: bool = True
    fail_closed_on_validation_error: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Enterprise planning policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise planning policy name is required.")
        if not str(self.version or "").strip():
            raise ValueError(
                "Enterprise planning policy version is required."
            )
        if self.maximum_plan_goals < 1:
            raise ValueError("Maximum plan goals must be at least 1.")
        if self.maximum_dependency_depth < 1:
            raise ValueError(
                "Maximum dependency depth must be at least 1."
            )
        if self.maximum_plan_duration_hours <= 0:
            raise ValueError(
                "Maximum plan duration must be greater than zero."
            )
        if not 0 < self.maximum_resource_utilisation <= 100:
            raise ValueError(
                "Maximum resource utilisation must be greater than 0 "
                "and no more than 100."
            )
        if not 0 <= self.minimum_capacity_buffer_percentage < 100:
            raise ValueError(
                "Minimum capacity buffer percentage must be between "
                "0 and less than 100."
            )
        if self.critical_path_tolerance_hours < 0:
            raise ValueError(
                "Critical path tolerance cannot be negative."
            )

        object.__setattr__(
            self,
            "policy_id",
            str(self.policy_id).strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name).strip(),
        )
        object.__setattr__(
            self,
            "version",
            str(self.version).strip(),
        )

    @property
    def usable_resource_percentage(self) -> float:
        """Return capacity percentage available after policy buffers."""

        return min(
            self.maximum_resource_utilisation,
            100.0 - self.minimum_capacity_buffer_percentage,
        )