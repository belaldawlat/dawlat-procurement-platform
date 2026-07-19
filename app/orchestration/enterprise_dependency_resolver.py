"""Dependency resolution for enterprise planning intelligence."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from app.orchestration.enterprise_planning_models import (
    EnterpriseGoal,
)


@dataclass(frozen=True)
class EnterpriseDependencyResolution:
    """Result of dependency validation and ordering."""

    ordered_goal_ids: tuple[str, ...]
    dependency_depth: int
    has_cycle: bool
    cycle_goal_ids: tuple[str, ...]
    missing_dependency_ids: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Return whether dependencies are complete and acyclic."""

        return (
            not self.has_cycle
            and not self.missing_dependency_ids
        )

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable resolution payload."""

        return {
            "ordered_goal_ids": list(self.ordered_goal_ids),
            "dependency_depth": self.dependency_depth,
            "has_cycle": self.has_cycle,
            "cycle_goal_ids": list(self.cycle_goal_ids),
            "missing_dependency_ids": list(
                self.missing_dependency_ids
            ),
            "valid": self.valid,
        }


class EnterpriseDependencyResolver:
    """Validate goal dependencies and produce topological order."""

    def resolve(
        self,
        goals: Iterable[EnterpriseGoal],
    ) -> EnterpriseDependencyResolution:
        """Resolve dependencies using deterministic Kahn ordering."""

        goal_tuple = tuple(goals)

        if not goal_tuple:
            return EnterpriseDependencyResolution(
                ordered_goal_ids=(),
                dependency_depth=0,
                has_cycle=False,
                cycle_goal_ids=(),
                missing_dependency_ids=(),
            )

        goal_map: dict[str, EnterpriseGoal] = {}

        for goal in goal_tuple:
            if goal.goal_id in goal_map:
                raise ValueError(
                    f"Duplicate goal ID: {goal.goal_id!r}."
                )
            goal_map[goal.goal_id] = goal

        known_ids = set(goal_map)
        missing_dependency_ids = tuple(
            sorted(
                {
                    dependency_id
                    for goal in goal_tuple
                    for dependency_id in goal.depends_on
                    if dependency_id not in known_ids
                }
            )
        )

        indegree = {
            goal_id: 0
            for goal_id in known_ids
        }
        children: dict[str, list[str]] = defaultdict(list)

        for goal in goal_tuple:
            for dependency_id in goal.depends_on:
                if dependency_id not in known_ids:
                    continue

                indegree[goal.goal_id] += 1
                children[dependency_id].append(goal.goal_id)

        queue = deque(
            sorted(
                goal_id
                for goal_id, degree in indegree.items()
                if degree == 0
            )
        )
        ordered: list[str] = []

        while queue:
            current = queue.popleft()
            ordered.append(current)

            for child_id in sorted(children.get(current, [])):
                indegree[child_id] -= 1

                if indegree[child_id] == 0:
                    queue.append(child_id)

        has_cycle = len(ordered) != len(known_ids)
        cycle_goal_ids = tuple(
            sorted(
                goal_id
                for goal_id, degree in indegree.items()
                if degree > 0
            )
        )

        dependency_depth = self._calculate_depth(
            ordered_goal_ids=tuple(ordered),
            goal_map=goal_map,
        )

        return EnterpriseDependencyResolution(
            ordered_goal_ids=tuple(ordered),
            dependency_depth=dependency_depth,
            has_cycle=has_cycle,
            cycle_goal_ids=cycle_goal_ids,
            missing_dependency_ids=missing_dependency_ids,
        )

    def require_valid(
        self,
        goals: Iterable[EnterpriseGoal],
        *,
        maximum_depth: int | None = None,
    ) -> EnterpriseDependencyResolution:
        """Resolve dependencies or raise a clear validation error."""

        resolution = self.resolve(goals)

        if resolution.missing_dependency_ids:
            raise ValueError(
                "Missing dependency goal IDs: "
                + ", ".join(resolution.missing_dependency_ids)
            )

        if resolution.has_cycle:
            raise ValueError(
                "Goal dependency cycle detected involving: "
                + ", ".join(resolution.cycle_goal_ids)
            )

        if (
            maximum_depth is not None
            and resolution.dependency_depth > maximum_depth
        ):
            raise ValueError(
                "Goal dependency depth exceeds the configured maximum."
            )

        return resolution

    @staticmethod
    def _calculate_depth(
        *,
        ordered_goal_ids: tuple[str, ...],
        goal_map: dict[str, EnterpriseGoal],
    ) -> int:
        if not ordered_goal_ids:
            return 0

        depths: dict[str, int] = {}

        for goal_id in ordered_goal_ids:
            goal = goal_map[goal_id]
            known_parent_depths = [
                depths[parent_id]
                for parent_id in goal.depends_on
                if parent_id in depths
            ]

            depths[goal_id] = (
                0
                if not known_parent_depths
                else 1 + max(known_parent_depths)
            )

        return max(depths.values(), default=0)