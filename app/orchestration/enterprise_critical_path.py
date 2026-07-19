"""Critical Path Method implementation for enterprise planning."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from app.orchestration.enterprise_dependency_resolver import (
    EnterpriseDependencyResolver,
)
from app.orchestration.enterprise_planning_models import (
    EnterpriseGoal,
)
from app.orchestration.enterprise_planning_result import (
    EnterpriseGoalSchedule,
)


@dataclass(frozen=True)
class EnterpriseCriticalPathResult:
    """Calculated critical-path output."""

    total_duration_hours: float
    critical_path_goal_ids: tuple[str, ...]
    schedules: tuple[EnterpriseGoalSchedule, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable critical-path payload."""

        return {
            "total_duration_hours": self.total_duration_hours,
            "critical_path_goal_ids": list(
                self.critical_path_goal_ids
            ),
            "schedules": [
                schedule.as_dict()
                for schedule in self.schedules
            ],
        }


class EnterpriseCriticalPath:
    """Calculate earliest/latest timings and critical goals."""

    def __init__(
        self,
        dependency_resolver: EnterpriseDependencyResolver | None = None,
    ) -> None:
        self._dependency_resolver = (
            dependency_resolver
            or EnterpriseDependencyResolver()
        )

    def calculate(
        self,
        goals: Iterable[EnterpriseGoal],
        *,
        tolerance_hours: float = 0.01,
        maximum_dependency_depth: int | None = None,
    ) -> EnterpriseCriticalPathResult:
        """Calculate a deterministic critical-path schedule."""

        goal_tuple = tuple(goals)

        if tolerance_hours < 0:
            raise ValueError(
                "Critical path tolerance cannot be negative."
            )

        if not goal_tuple:
            return EnterpriseCriticalPathResult(
                total_duration_hours=0.0,
                critical_path_goal_ids=(),
                schedules=(),
            )

        resolution = self._dependency_resolver.require_valid(
            goal_tuple,
            maximum_depth=maximum_dependency_depth,
        )
        goal_map = {
            goal.goal_id: goal
            for goal in goal_tuple
        }
        children: dict[str, list[str]] = defaultdict(list)

        for goal in goal_tuple:
            for dependency_id in goal.depends_on:
                children[dependency_id].append(goal.goal_id)

        earliest_start: dict[str, float] = {}
        earliest_finish: dict[str, float] = {}

        for goal_id in resolution.ordered_goal_ids:
            goal = goal_map[goal_id]
            parent_finishes = [
                earliest_finish[parent_id]
                for parent_id in goal.depends_on
            ]

            start = max(parent_finishes, default=0.0)
            finish = start + goal.estimated_duration_hours

            earliest_start[goal_id] = round(start, 6)
            earliest_finish[goal_id] = round(finish, 6)

        total_duration = max(
            earliest_finish.values(),
            default=0.0,
        )

        latest_finish: dict[str, float] = {}
        latest_start: dict[str, float] = {}

        for goal_id in reversed(resolution.ordered_goal_ids):
            goal = goal_map[goal_id]
            child_ids = children.get(goal_id, [])

            finish = (
                min(
                    latest_start[child_id]
                    for child_id in child_ids
                )
                if child_ids
                else total_duration
            )
            start = finish - goal.estimated_duration_hours

            latest_finish[goal_id] = round(finish, 6)
            latest_start[goal_id] = round(start, 6)

        schedules: list[EnterpriseGoalSchedule] = []

        for sequence, goal_id in enumerate(
            resolution.ordered_goal_ids,
            start=1,
        ):
            total_float = round(
                latest_start[goal_id]
                - earliest_start[goal_id],
                6,
            )
            critical = abs(total_float) <= tolerance_hours

            schedules.append(
                EnterpriseGoalSchedule(
                    goal_id=goal_id,
                    sequence=sequence,
                    earliest_start_hour=earliest_start[goal_id],
                    earliest_finish_hour=earliest_finish[goal_id],
                    latest_start_hour=latest_start[goal_id],
                    latest_finish_hour=latest_finish[goal_id],
                    total_float_hours=total_float,
                    critical=critical,
                )
            )

        critical_goal_ids = tuple(
            schedule.goal_id
            for schedule in schedules
            if schedule.critical
        )

        return EnterpriseCriticalPathResult(
            total_duration_hours=round(
                total_duration,
                6,
            ),
            critical_path_goal_ids=critical_goal_ids,
            schedules=tuple(schedules),
        )