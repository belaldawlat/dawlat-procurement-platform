"""Tests for Phase 21 Package S enterprise planning intelligence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestration import (
    EnterpriseCriticalPath,
    EnterpriseDependencyResolver,
    EnterpriseGoal,
    EnterpriseGoalHierarchy,
    EnterpriseMilestone,
    EnterprisePlan,
    EnterprisePlanDomain,
    EnterprisePlanningEngine,
    EnterprisePlanningPolicy,
    EnterprisePlanningRegistry,
    EnterprisePlanningResource,
    EnterprisePlanStore,
    EnterprisePlanStatus,
    WorkflowIntegrityError,
)


def goal(
    goal_id: str,
    duration: float,
    *,
    depends_on: tuple[str, ...] = (),
    capacity: float = 1.0,
    capabilities: tuple[str, ...] = (),
) -> EnterpriseGoal:
    return EnterpriseGoal(
        goal_id=goal_id,
        name=goal_id,
        domain=EnterprisePlanDomain.PROCUREMENT,
        estimated_duration_hours=duration,
        required_capacity_units=capacity,
        depends_on=depends_on,
        required_capabilities=capabilities,
    )


def resource(
    resource_id: str = "resource-1",
    *,
    capacity: float = 20.0,
    available: float = 20.0,
    capabilities: tuple[str, ...] = (),
    cost: float = 2.0,
) -> EnterprisePlanningResource:
    return EnterprisePlanningResource(
        resource_id=resource_id,
        name=resource_id,
        capacity_units=capacity,
        available_units=available,
        capabilities=capabilities,
        cost_per_unit=cost,
    )


def simple_plan() -> EnterprisePlan:
    first = goal("G1", 5, capacity=2)
    second = goal(
        "G2",
        3,
        depends_on=("G1",),
        capacity=2,
    )

    return EnterprisePlan(
        plan_id="PLAN-1",
        name="Plan 1",
        goals=(first, second),
        resources=(resource(),),
    )


def test_policy_validates_goal_limit() -> None:
    with pytest.raises(ValueError):
        EnterprisePlanningPolicy(
            policy_id="invalid",
            name="Invalid",
            maximum_plan_goals=0,
        )


def test_plan_requires_goals() -> None:
    with pytest.raises(ValueError):
        EnterprisePlan(
            plan_id="PLAN-1",
            name="Plan",
            goals=(),
        )


def test_plan_rejects_duplicate_goal_ids() -> None:
    first = goal("G1", 1)
    second = goal("G1", 2)

    with pytest.raises(ValueError):
        EnterprisePlan(
            plan_id="PLAN-1",
            name="Plan",
            goals=(first, second),
        )


def test_dependency_resolver_orders_goals() -> None:
    first = goal("G1", 1)
    second = goal("G2", 1, depends_on=("G1",))

    resolution = EnterpriseDependencyResolver().resolve(
        (second, first)
    )

    assert resolution.ordered_goal_ids == ("G1", "G2")
    assert resolution.valid is True


def test_dependency_resolver_detects_cycle() -> None:
    first = goal("G1", 1, depends_on=("G2",))
    second = goal("G2", 1, depends_on=("G1",))

    resolution = EnterpriseDependencyResolver().resolve(
        (first, second)
    )

    assert resolution.has_cycle is True
    assert set(resolution.cycle_goal_ids) == {"G1", "G2"}


def test_goal_hierarchy_calculates_depth() -> None:
    first = goal("G1", 1)
    second = goal("G2", 1, depends_on=("G1",))
    third = goal("G3", 1, depends_on=("G2",))

    nodes = EnterpriseGoalHierarchy().build(
        (third, first, second)
    )
    depth_map = {
        node.goal.goal_id: node.depth
        for node in nodes
    }

    assert depth_map == {"G1": 0, "G2": 1, "G3": 2}


def test_critical_path_calculates_duration() -> None:
    first = goal("G1", 5)
    second = goal("G2", 3, depends_on=("G1",))

    result = EnterpriseCriticalPath().calculate(
        (first, second)
    )

    assert result.total_duration_hours == 8
    assert result.critical_path_goal_ids == ("G1", "G2")


def test_parallel_goal_has_float() -> None:
    first = goal("G1", 5)
    second = goal("G2", 2)
    third = goal(
        "G3",
        3,
        depends_on=("G1", "G2"),
    )

    result = EnterpriseCriticalPath().calculate(
        (first, second, third)
    )
    schedule_map = {
        item.goal_id: item
        for item in result.schedules
    }

    assert schedule_map["G2"].total_float_hours == 3
    assert schedule_map["G2"].critical is False


def test_engine_evaluates_feasible_plan() -> None:
    result = EnterprisePlanningEngine().evaluate(
        simple_plan()
    )

    assert result.valid is True
    assert result.feasible is True
    assert result.total_duration_hours == 8
    assert len(result.schedules) == 2


def test_engine_assigns_resources() -> None:
    result = EnterprisePlanningEngine().evaluate(
        simple_plan()
    )

    assert all(
        schedule.assigned_resource_ids
        for schedule in result.schedules
    )


def test_engine_reports_insufficient_capacity() -> None:
    plan = replace(
        simple_plan(),
        resources=(
            resource(
                capacity=1,
                available=1,
            ),
        ),
    )

    result = EnterprisePlanningEngine().evaluate(plan)

    assert result.feasible is False
    assert any(
        issue.code == "INSUFFICIENT_RESOURCE_CAPACITY"
        for issue in result.issues
    )


def test_engine_enforces_maximum_duration() -> None:
    engine = EnterprisePlanningEngine(
        policy=EnterprisePlanningPolicy(
            policy_id="short",
            name="Short",
            maximum_plan_duration_hours=4,
        )
    )

    result = engine.evaluate(simple_plan())

    assert result.valid is False
    assert any(
        issue.code == "MAXIMUM_PLAN_DURATION_EXCEEDED"
        for issue in result.issues
    )


def test_unlinked_milestone_is_blocking() -> None:
    plan = replace(
        simple_plan(),
        milestones=(
            EnterpriseMilestone(
                milestone_id="M1",
                name="Milestone",
                target_at="2030-01-01T00:00:00+00:00",
                goal_ids=(),
            ),
        ),
    )

    result = EnterprisePlanningEngine().evaluate(plan)

    assert result.valid is False
    assert any(
        issue.code == "MILESTONE_WITHOUT_GOALS"
        for issue in result.issues
    )


def test_evaluate_can_persist_plan() -> None:
    store = EnterprisePlanStore()
    engine = EnterprisePlanningEngine(
        plan_store=store
    )
    plan = simple_plan()

    engine.evaluate(plan, persist=True)

    assert engine.get_plan(plan.plan_id) == plan


def test_plan_store_rejects_duplicate_create() -> None:
    store = EnterprisePlanStore()
    plan = simple_plan()
    store.create(plan)

    with pytest.raises(WorkflowIntegrityError):
        store.create(plan)


def test_planning_registry_rejects_duplicate_strategy() -> None:
    registry = EnterprisePlanningRegistry()
    registry.register("default", lambda plan: plan)

    with pytest.raises(WorkflowIntegrityError):
        registry.register("default", lambda plan: plan)


def test_result_serialises() -> None:
    payload = EnterprisePlanningEngine().evaluate(
        simple_plan()
    ).as_dict()

    assert payload["valid"] is True
    assert payload["feasible"] is True
    assert payload["critical_path_goal_ids"] == ["G1", "G2"]
    assert payload["schedules"]


def test_disabled_policy_rejects_evaluation() -> None:
    engine = EnterprisePlanningEngine(
        policy=EnterprisePlanningPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        engine.evaluate(simple_plan())