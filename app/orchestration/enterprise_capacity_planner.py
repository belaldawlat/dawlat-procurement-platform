"""Capacity planning for enterprise planning intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.orchestration.enterprise_planning_models import (
    EnterpriseGoal,
    EnterprisePlanningResource,
)
from app.orchestration.enterprise_planning_policy import EnterprisePlanningPolicy
from app.orchestration.enterprise_planning_result import (
    EnterpriseGoalSchedule,
    EnterprisePlanningIssue,
    EnterprisePlanningIssueSeverity,
)


@dataclass(frozen=True)
class EnterpriseCapacityAllocation:
    goal_id: str
    resource_id: str
    allocated_units: float
    estimated_cost: float

    def __post_init__(self) -> None:
        if not str(self.goal_id or "").strip():
            raise ValueError("Capacity allocation goal ID is required.")
        if not str(self.resource_id or "").strip():
            raise ValueError("Capacity allocation resource ID is required.")
        if self.allocated_units < 0:
            raise ValueError("Allocated capacity cannot be negative.")
        if self.estimated_cost < 0:
            raise ValueError("Estimated allocation cost cannot be negative.")

        object.__setattr__(self, "goal_id", str(self.goal_id).strip())
        object.__setattr__(self, "resource_id", str(self.resource_id).strip())

    def as_dict(self) -> dict[str, object]:
        return {
            "goal_id": self.goal_id,
            "resource_id": self.resource_id,
            "allocated_units": self.allocated_units,
            "estimated_cost": self.estimated_cost,
        }


@dataclass(frozen=True)
class EnterpriseCapacityPlan:
    feasible: bool
    allocations: tuple[EnterpriseCapacityAllocation, ...]
    schedules: tuple[EnterpriseGoalSchedule, ...]
    issues: tuple[EnterprisePlanningIssue, ...]
    total_estimated_cost: float

    def __post_init__(self) -> None:
        if self.total_estimated_cost < 0:
            raise ValueError("Total estimated cost cannot be negative.")
        object.__setattr__(self, "allocations", tuple(self.allocations))
        object.__setattr__(self, "schedules", tuple(self.schedules))
        object.__setattr__(self, "issues", tuple(self.issues))

    def as_dict(self) -> dict[str, object]:
        return {
            "feasible": self.feasible,
            "total_estimated_cost": self.total_estimated_cost,
            "allocations": [item.as_dict() for item in self.allocations],
            "schedules": [item.as_dict() for item in self.schedules],
            "issues": [item.as_dict() for item in self.issues],
        }


class EnterpriseCapacityPlanner:
    def allocate(
        self,
        *,
        goals: Iterable[EnterpriseGoal],
        resources: Iterable[EnterprisePlanningResource],
        schedules: Iterable[EnterpriseGoalSchedule],
        policy: EnterprisePlanningPolicy,
    ) -> EnterpriseCapacityPlan:
        goal_tuple = tuple(goals)
        resource_tuple = tuple(resources)
        schedule_tuple = tuple(schedules)

        remaining_capacity = {
            resource.resource_id: (
                resource.available_units
                * policy.usable_resource_percentage
                / 100.0
            )
            for resource in resource_tuple
            if resource.enabled
        }
        schedule_map = {item.goal_id: item for item in schedule_tuple}

        allocations: list[EnterpriseCapacityAllocation] = []
        issues: list[EnterprisePlanningIssue] = []
        updated_schedules: list[EnterpriseGoalSchedule] = []
        total_cost = 0.0

        ordered_goals = sorted(
            goal_tuple,
            key=lambda goal: (
                schedule_map.get(goal.goal_id).sequence
                if goal.goal_id in schedule_map
                else 10**9,
                -self._priority_rank(goal.priority.value),
                goal.goal_id,
            ),
        )

        for goal in ordered_goals:
            schedule = schedule_map.get(goal.goal_id)

            if schedule is None:
                issues.append(
                    EnterprisePlanningIssue(
                        code="MISSING_GOAL_SCHEDULE",
                        message=f"Goal {goal.goal_id!r} has no calculated schedule.",
                        severity=EnterprisePlanningIssueSeverity.ERROR,
                        blocking=True,
                        entity_id=goal.goal_id,
                    )
                )
                continue

            required_units = goal.required_capacity_units
            assigned_resource_ids: list[str] = []

            if required_units == 0:
                updated_schedules.append(schedule)
                continue

            eligible_resources = [
                resource
                for resource in resource_tuple
                if (
                    resource.enabled
                    and self._supports_goal(resource, goal)
                    and remaining_capacity.get(resource.resource_id, 0.0) > 0
                )
            ]
            eligible_resources.sort(
                key=lambda resource: (
                    resource.cost_per_unit,
                    -remaining_capacity[resource.resource_id],
                    resource.resource_id,
                )
            )

            unallocated_units = required_units

            for resource in eligible_resources:
                if unallocated_units <= 0:
                    break

                resource_id = resource.resource_id
                available_units = remaining_capacity[resource_id]
                allocated_units = min(available_units, unallocated_units)

                if allocated_units <= 0:
                    continue

                cost = allocated_units * resource.cost_per_unit
                allocations.append(
                    EnterpriseCapacityAllocation(
                        goal_id=goal.goal_id,
                        resource_id=resource_id,
                        allocated_units=round(allocated_units, 6),
                        estimated_cost=round(cost, 6),
                    )
                )
                remaining_capacity[resource_id] = round(
                    available_units - allocated_units,
                    6,
                )
                unallocated_units = round(
                    unallocated_units - allocated_units,
                    6,
                )
                total_cost += cost
                assigned_resource_ids.append(resource_id)

            if unallocated_units > 0:
                severity = (
                    EnterprisePlanningIssueSeverity.CRITICAL
                    if policy.require_resource_feasibility
                    else EnterprisePlanningIssueSeverity.WARNING
                )
                issues.append(
                    EnterprisePlanningIssue(
                        code="INSUFFICIENT_RESOURCE_CAPACITY",
                        message=(
                            f"Goal {goal.goal_id!r} is short by "
                            f"{unallocated_units:.2f} capacity units."
                        ),
                        severity=severity,
                        blocking=policy.require_resource_feasibility,
                        entity_id=goal.goal_id,
                        metadata={
                            "required_units": required_units,
                            "unallocated_units": unallocated_units,
                        },
                    )
                )

            updated_schedules.append(
                EnterpriseGoalSchedule(
                    goal_id=schedule.goal_id,
                    sequence=schedule.sequence,
                    earliest_start_hour=schedule.earliest_start_hour,
                    earliest_finish_hour=schedule.earliest_finish_hour,
                    latest_start_hour=schedule.latest_start_hour,
                    latest_finish_hour=schedule.latest_finish_hour,
                    total_float_hours=schedule.total_float_hours,
                    critical=schedule.critical,
                    assigned_resource_ids=tuple(sorted(set(assigned_resource_ids))),
                )
            )

        return EnterpriseCapacityPlan(
            feasible=not any(issue.blocking for issue in issues),
            allocations=tuple(allocations),
            schedules=tuple(sorted(updated_schedules, key=lambda item: item.sequence)),
            issues=tuple(issues),
            total_estimated_cost=round(total_cost, 6),
        )

    @staticmethod
    def _supports_goal(
        resource: EnterprisePlanningResource,
        goal: EnterpriseGoal,
    ) -> bool:
        if not goal.required_capabilities:
            return True
        return set(goal.required_capabilities).issubset(
            set(resource.capabilities)
        )

    @staticmethod
    def _priority_rank(priority_value: str) -> int:
        return {
            "critical": 4,
            "high": 3,
            "normal": 2,
            "low": 1,
        }[priority_value]