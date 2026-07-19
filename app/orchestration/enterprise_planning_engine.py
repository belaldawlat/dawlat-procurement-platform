"""Enterprise planning intelligence engine."""

from __future__ import annotations

from app.orchestration.enterprise_capacity_planner import (
    EnterpriseCapacityPlanner,
)
from app.orchestration.enterprise_critical_path import (
    EnterpriseCriticalPath,
)
from app.orchestration.enterprise_dependency_resolver import (
    EnterpriseDependencyResolver,
)
from app.orchestration.enterprise_goal_hierarchy import (
    EnterpriseGoalHierarchy,
)
from app.orchestration.enterprise_plan_store import (
    EnterprisePlanStore,
)
from app.orchestration.enterprise_planning_models import (
    EnterprisePlan,
)
from app.orchestration.enterprise_planning_policy import (
    EnterprisePlanningPolicy,
)
from app.orchestration.enterprise_planning_result import (
    EnterprisePlanningIssue,
    EnterprisePlanningIssueSeverity,
    EnterprisePlanningResult,
)


class EnterprisePlanningEngine:
    """Validate, schedule and capacity-plan enterprise goals."""

    def __init__(
        self,
        *,
        policy: EnterprisePlanningPolicy | None = None,
        dependency_resolver: EnterpriseDependencyResolver | None = None,
        critical_path: EnterpriseCriticalPath | None = None,
        capacity_planner: EnterpriseCapacityPlanner | None = None,
        goal_hierarchy: EnterpriseGoalHierarchy | None = None,
        plan_store: EnterprisePlanStore | None = None,
    ) -> None:
        self._policy = policy or EnterprisePlanningPolicy(
            policy_id="default-enterprise-planning",
            name="Default Enterprise Planning Policy",
        )
        self._dependency_resolver = (
            dependency_resolver or EnterpriseDependencyResolver()
        )
        self._critical_path = critical_path or EnterpriseCriticalPath(
            dependency_resolver=self._dependency_resolver,
        )
        self._capacity_planner = (
            capacity_planner or EnterpriseCapacityPlanner()
        )
        self._goal_hierarchy = (
            goal_hierarchy or EnterpriseGoalHierarchy()
        )
        self._plan_store = plan_store or EnterprisePlanStore()

    @property
    def policy(self) -> EnterprisePlanningPolicy:
        """Return the active planning policy."""

        return self._policy

    @property
    def plan_store(self) -> EnterprisePlanStore:
        """Return the plan store."""

        return self._plan_store

    def evaluate(
        self,
        plan: EnterprisePlan,
        *,
        persist: bool = False,
    ) -> EnterprisePlanningResult:
        """Evaluate one enterprise plan."""

        if not isinstance(plan, EnterprisePlan):
            raise TypeError(
                "Enterprise planning engine requires an EnterprisePlan."
            )

        if not self._policy.enabled:
            raise ValueError(
                "Enterprise planning policy is disabled."
            )

        issues: list[EnterprisePlanningIssue] = []

        if len(plan.goals) > self._policy.maximum_plan_goals:
            issues.append(
                EnterprisePlanningIssue(
                    code="MAXIMUM_GOAL_COUNT_EXCEEDED",
                    message=(
                        "Enterprise plan exceeds the maximum permitted "
                        "number of goals."
                    ),
                    severity=EnterprisePlanningIssueSeverity.CRITICAL,
                    blocking=True,
                    entity_id=plan.plan_id,
                    metadata={
                        "goal_count": len(plan.goals),
                        "maximum_plan_goals": (
                            self._policy.maximum_plan_goals
                        ),
                    },
                )
            )

        dependency_resolution = self._dependency_resolver.resolve(
            plan.goals
        )

        if dependency_resolution.missing_dependency_ids:
            issues.append(
                EnterprisePlanningIssue(
                    code="MISSING_GOAL_DEPENDENCIES",
                    message=(
                        "One or more goal dependencies do not exist "
                        "inside the plan."
                    ),
                    severity=EnterprisePlanningIssueSeverity.CRITICAL,
                    blocking=True,
                    entity_id=plan.plan_id,
                    metadata={
                        "missing_dependency_ids": list(
                            dependency_resolution.missing_dependency_ids
                        ),
                    },
                )
            )

        if (
            dependency_resolution.has_cycle
            and self._policy.require_acyclic_dependencies
        ):
            issues.append(
                EnterprisePlanningIssue(
                    code="GOAL_DEPENDENCY_CYCLE",
                    message=(
                        "The enterprise plan contains a dependency cycle."
                    ),
                    severity=EnterprisePlanningIssueSeverity.CRITICAL,
                    blocking=True,
                    entity_id=plan.plan_id,
                    metadata={
                        "cycle_goal_ids": list(
                            dependency_resolution.cycle_goal_ids
                        ),
                    },
                )
            )

        if (
            dependency_resolution.dependency_depth
            > self._policy.maximum_dependency_depth
        ):
            issues.append(
                EnterprisePlanningIssue(
                    code="MAXIMUM_DEPENDENCY_DEPTH_EXCEEDED",
                    message=(
                        "Goal dependency depth exceeds planning policy."
                    ),
                    severity=EnterprisePlanningIssueSeverity.ERROR,
                    blocking=True,
                    entity_id=plan.plan_id,
                    metadata={
                        "dependency_depth": (
                            dependency_resolution.dependency_depth
                        ),
                        "maximum_dependency_depth": (
                            self._policy.maximum_dependency_depth
                        ),
                    },
                )
            )

        if self._policy.require_milestone_goal_links:
            for milestone in plan.milestones:
                if not milestone.goal_ids:
                    issues.append(
                        EnterprisePlanningIssue(
                            code="MILESTONE_WITHOUT_GOALS",
                            message=(
                                f"Milestone {milestone.milestone_id!r} "
                                "is not linked to any goal."
                            ),
                            severity=(
                                EnterprisePlanningIssueSeverity.ERROR
                            ),
                            blocking=True,
                            entity_id=milestone.milestone_id,
                        )
                    )

        structural_blocking = any(
            issue.blocking
            for issue in issues
        )

        if structural_blocking:
            result = EnterprisePlanningResult(
                plan=plan,
                valid=False,
                feasible=False,
                total_duration_hours=0.0,
                critical_path_goal_ids=(),
                schedules=(),
                issues=tuple(issues),
                policy_id=self._policy.policy_id,
                policy_version=self._policy.version,
                metadata={
                    "goal_count": len(plan.goals),
                    "milestone_count": len(plan.milestones),
                    "resource_count": len(plan.resources),
                },
            )

            if (
                self._policy.fail_closed_on_validation_error
                and persist
            ):
                self._plan_store.upsert(plan)

            return result

        hierarchy = self._goal_hierarchy.build(plan.goals)

        critical_path_result = self._critical_path.calculate(
            plan.goals,
            tolerance_hours=(
                self._policy.critical_path_tolerance_hours
            ),
            maximum_dependency_depth=(
                self._policy.maximum_dependency_depth
            ),
        )

        if (
            critical_path_result.total_duration_hours
            > self._policy.maximum_plan_duration_hours
        ):
            issues.append(
                EnterprisePlanningIssue(
                    code="MAXIMUM_PLAN_DURATION_EXCEEDED",
                    message=(
                        "Calculated plan duration exceeds planning policy."
                    ),
                    severity=EnterprisePlanningIssueSeverity.ERROR,
                    blocking=True,
                    entity_id=plan.plan_id,
                    metadata={
                        "total_duration_hours": (
                            critical_path_result.total_duration_hours
                        ),
                        "maximum_plan_duration_hours": (
                            self._policy.maximum_plan_duration_hours
                        ),
                    },
                )
            )

        capacity_result = self._capacity_planner.allocate(
            goals=plan.goals,
            resources=plan.resources,
            schedules=critical_path_result.schedules,
            policy=self._policy,
        )
        issues.extend(capacity_result.issues)

        valid = not any(
            issue.blocking
            for issue in issues
            if issue.code != "INSUFFICIENT_RESOURCE_CAPACITY"
        )
        feasible = (
            valid
            and capacity_result.feasible
            and not any(issue.blocking for issue in issues)
        )

        result = EnterprisePlanningResult(
            plan=plan,
            valid=valid,
            feasible=feasible,
            total_duration_hours=(
                critical_path_result.total_duration_hours
            ),
            critical_path_goal_ids=(
                critical_path_result.critical_path_goal_ids
            ),
            schedules=capacity_result.schedules,
            issues=tuple(issues),
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "goal_count": len(plan.goals),
                "milestone_count": len(plan.milestones),
                "resource_count": len(plan.resources),
                "hierarchy_depth": max(
                    (
                        node.depth
                        for node in hierarchy
                    ),
                    default=0,
                ),
                "dependency_depth": (
                    dependency_resolution.dependency_depth
                ),
                "allocation_count": len(
                    capacity_result.allocations
                ),
                "total_estimated_cost": (
                    capacity_result.total_estimated_cost
                ),
            },
        )

        if persist:
            self._plan_store.upsert(plan)

        return result

    def save_plan(
        self,
        plan: EnterprisePlan,
    ) -> EnterprisePlan:
        """Create or replace a plan without evaluating it."""

        if not self._policy.enabled:
            raise ValueError(
                "Enterprise planning policy is disabled."
            )

        return self._plan_store.upsert(plan)

    def get_plan(self, plan_id: str) -> EnterprisePlan:
        """Return a stored plan."""

        return self._plan_store.get(plan_id)


_default_enterprise_planning_engine = EnterprisePlanningEngine()


def get_enterprise_planning_engine() -> EnterprisePlanningEngine:
    """Return the process-local default planning engine."""

    return _default_enterprise_planning_engine