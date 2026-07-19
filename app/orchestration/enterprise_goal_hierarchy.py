"""Goal hierarchy services for enterprise planning intelligence."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from app.orchestration.enterprise_planning_models import (
    EnterpriseGoal,
)


@dataclass(frozen=True)
class EnterpriseGoalHierarchyNode:
    """One goal and its hierarchy relationships."""

    goal: EnterpriseGoal
    parent_goal_ids: tuple[str, ...]
    child_goal_ids: tuple[str, ...]
    depth: int

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable hierarchy node."""

        return {
            "goal": self.goal.as_dict(),
            "parent_goal_ids": list(self.parent_goal_ids),
            "child_goal_ids": list(self.child_goal_ids),
            "depth": self.depth,
        }


class EnterpriseGoalHierarchy:
    """Build and query deterministic goal hierarchies."""

    def build(
        self,
        goals: Iterable[EnterpriseGoal],
    ) -> tuple[EnterpriseGoalHierarchyNode, ...]:
        """Build hierarchy nodes from goal dependencies."""

        goal_tuple = tuple(goals)

        if not goal_tuple:
            return ()

        goal_map = self._build_goal_map(goal_tuple)
        parent_map: dict[str, tuple[str, ...]] = {
            goal.goal_id: tuple(goal.depends_on)
            for goal in goal_tuple
        }
        child_map: dict[str, list[str]] = defaultdict(list)

        for goal in goal_tuple:
            for parent_id in goal.depends_on:
                if parent_id not in goal_map:
                    raise ValueError(
                        f"Unknown parent goal ID: {parent_id!r}."
                    )
                child_map[parent_id].append(goal.goal_id)

        depth_cache: dict[str, int] = {}

        def resolve_depth(
            goal_id: str,
            trail: tuple[str, ...] = (),
        ) -> int:
            if goal_id in depth_cache:
                return depth_cache[goal_id]

            if goal_id in trail:
                cycle = " -> ".join(trail + (goal_id,))
                raise ValueError(
                    f"Goal hierarchy contains a cycle: {cycle}."
                )

            parents = parent_map[goal_id]

            if not parents:
                depth = 0
            else:
                depth = 1 + max(
                    resolve_depth(
                        parent_id,
                        trail + (goal_id,),
                    )
                    for parent_id in parents
                )

            depth_cache[goal_id] = depth
            return depth

        nodes = [
            EnterpriseGoalHierarchyNode(
                goal=goal,
                parent_goal_ids=tuple(
                    sorted(parent_map[goal.goal_id])
                ),
                child_goal_ids=tuple(
                    sorted(child_map.get(goal.goal_id, []))
                ),
                depth=resolve_depth(goal.goal_id),
            )
            for goal in goal_tuple
        ]

        return tuple(
            sorted(
                nodes,
                key=lambda node: (
                    node.depth,
                    node.goal.priority.value,
                    node.goal.goal_id,
                ),
            )
        )

    def roots(
        self,
        goals: Iterable[EnterpriseGoal],
    ) -> tuple[EnterpriseGoal, ...]:
        """Return goals with no dependencies."""

        return tuple(
            sorted(
                (
                    goal
                    for goal in goals
                    if not goal.depends_on
                ),
                key=lambda goal: goal.goal_id,
            )
        )

    def leaves(
        self,
        goals: Iterable[EnterpriseGoal],
    ) -> tuple[EnterpriseGoal, ...]:
        """Return goals that have no dependants."""

        goal_tuple = tuple(goals)
        referenced = {
            dependency_id
            for goal in goal_tuple
            for dependency_id in goal.depends_on
        }

        return tuple(
            sorted(
                (
                    goal
                    for goal in goal_tuple
                    if goal.goal_id not in referenced
                ),
                key=lambda goal: goal.goal_id,
            )
        )

    def ancestors(
        self,
        goal_id: str,
        goals: Iterable[EnterpriseGoal],
    ) -> tuple[EnterpriseGoal, ...]:
        """Return all transitive dependencies of one goal."""

        goal_tuple = tuple(goals)
        goal_map = self._build_goal_map(goal_tuple)
        cleaned_id = str(goal_id or "").strip()

        if cleaned_id not in goal_map:
            raise ValueError(
                f"Unknown goal ID: {cleaned_id!r}."
            )

        visited: set[str] = set()
        stack = list(goal_map[cleaned_id].depends_on)

        while stack:
            current = stack.pop()

            if current in visited:
                continue

            if current not in goal_map:
                raise ValueError(
                    f"Unknown dependency goal ID: {current!r}."
                )

            visited.add(current)
            stack.extend(goal_map[current].depends_on)

        return tuple(
            sorted(
                (goal_map[item] for item in visited),
                key=lambda goal: goal.goal_id,
            )
        )

    def descendants(
        self,
        goal_id: str,
        goals: Iterable[EnterpriseGoal],
    ) -> tuple[EnterpriseGoal, ...]:
        """Return all goals transitively dependent on one goal."""

        goal_tuple = tuple(goals)
        goal_map = self._build_goal_map(goal_tuple)
        cleaned_id = str(goal_id or "").strip()

        if cleaned_id not in goal_map:
            raise ValueError(
                f"Unknown goal ID: {cleaned_id!r}."
            )

        child_map: dict[str, list[str]] = defaultdict(list)

        for goal in goal_tuple:
            for parent_id in goal.depends_on:
                child_map[parent_id].append(goal.goal_id)

        visited: set[str] = set()
        stack = list(child_map.get(cleaned_id, []))

        while stack:
            current = stack.pop()

            if current in visited:
                continue

            visited.add(current)
            stack.extend(child_map.get(current, []))

        return tuple(
            sorted(
                (goal_map[item] for item in visited),
                key=lambda goal: goal.goal_id,
            )
        )

    @staticmethod
    def _build_goal_map(
        goals: tuple[EnterpriseGoal, ...],
    ) -> dict[str, EnterpriseGoal]:
        goal_map: dict[str, EnterpriseGoal] = {}

        for goal in goals:
            if goal.goal_id in goal_map:
                raise ValueError(
                    f"Duplicate goal ID: {goal.goal_id!r}."
                )

            goal_map[goal.goal_id] = goal

        return goal_map