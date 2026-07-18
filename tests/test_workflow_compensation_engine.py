"""Tests for Phase 21 Package E compensation engine."""

from __future__ import annotations

import pytest

from app.orchestration import (
    CompensationEngine,
    CompensationFailureStrategy,
    CompensationHandlerRegistry,
    CompensationPolicy,
    CompensationStatus,
    CompensationStepDefinition,
    InMemoryCompensationStore,
    WorkflowIntegrityError,
    WorkflowNotFoundError,
    WorkflowStateError,
    WorkflowValidationError,
    create_workflow_context,
)
from app.resilience.exceptions import NetworkError


def build_policy() -> CompensationPolicy:
    return CompensationPolicy(
        policy_id="procurement-compensation",
        name="Procurement Compensation",
        reverse_execution_order=True,
        require_idempotency_keys=True,
        maximum_total_steps=10,
    )


def build_steps() -> tuple[CompensationStepDefinition, ...]:
    return (
        CompensationStepDefinition(
            step_id="release-payment",
            name="Release Buyer Payment Hold",
            original_step_id="capture-payment",
            handler_key="release-payment",
            order=1,
            maximum_attempts=2,
            idempotency_key="WF-100:release-payment",
        ),
        CompensationStepDefinition(
            step_id="cancel-order",
            name="Cancel Supplier Purchase Order",
            original_step_id="issue-order",
            handler_key="cancel-order",
            order=2,
            maximum_attempts=2,
            idempotency_key="WF-100:cancel-order",
        ),
    )


def build_engine() -> CompensationEngine:
    store = InMemoryCompensationStore()
    registry = CompensationHandlerRegistry()
    engine = CompensationEngine(
        store=store,
        handler_registry=registry,
    )
    engine.register_policy(build_policy())
    return engine


def create_plan(engine: CompensationEngine):
    return engine.create_plan(
        policy_id="procurement-compensation",
        workflow_instance_id="WF-100",
        workflow_id="supplier-procurement",
        workflow_version="1.0.0",
        steps=build_steps(),
    )


def test_policy_requires_identity() -> None:
    with pytest.raises(ValueError):
        CompensationPolicy(policy_id="", name="Invalid")

    with pytest.raises(ValueError):
        CompensationPolicy(policy_id="policy", name="")


def test_step_definition_validates_attempts() -> None:
    with pytest.raises(ValueError):
        CompensationStepDefinition(
            step_id="rollback",
            name="Rollback",
            original_step_id="action",
            handler_key="rollback",
            order=1,
            maximum_attempts=0,
            idempotency_key="key",
        )


def test_store_registers_policy() -> None:
    store = InMemoryCompensationStore()
    policy = build_policy()
    assert store.register_policy(policy) is policy
    assert store.get_policy(policy.policy_id) is policy


def test_store_rejects_duplicate_policy() -> None:
    store = InMemoryCompensationStore()
    policy = build_policy()
    store.register_policy(policy)

    with pytest.raises(WorkflowIntegrityError):
        store.register_policy(policy)


def test_store_rejects_unknown_plan() -> None:
    with pytest.raises(WorkflowNotFoundError):
        InMemoryCompensationStore().get_plan("missing-plan")


def test_engine_creates_valid_plan() -> None:
    engine = build_engine()
    plan = create_plan(engine)
    assert plan.status is CompensationStatus.PENDING
    assert len(plan.steps) == 2


def test_engine_rejects_missing_idempotency_key() -> None:
    engine = build_engine()
    steps = (
        CompensationStepDefinition(
            step_id="rollback",
            name="Rollback",
            original_step_id="action",
            handler_key="rollback",
            order=1,
        ),
    )

    with pytest.raises(WorkflowValidationError):
        engine.create_plan(
            policy_id="procurement-compensation",
            workflow_instance_id="WF-100",
            workflow_id="supplier-procurement",
            workflow_version="1.0.0",
            steps=steps,
        )


def test_handler_registry_rejects_duplicate() -> None:
    registry = CompensationHandlerRegistry()
    registry.register("handler", lambda context, data: "ok")

    with pytest.raises(WorkflowIntegrityError):
        registry.register("handler", lambda context, data: "again")


def test_engine_executes_reverse_order() -> None:
    engine = build_engine()
    order: list[str] = []

    engine.handler_registry.register(
        "release-payment",
        lambda context, data: order.append("release-payment"),
    )
    engine.handler_registry.register(
        "cancel-order",
        lambda context, data: order.append("cancel-order"),
    )

    result = engine.execute(
        create_plan(engine).plan_id,
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
    )

    assert result.successful is True
    assert order == ["cancel-order", "release-payment"]


def test_engine_records_successful_steps() -> None:
    engine = build_engine()
    engine.handler_registry.register(
        "release-payment",
        lambda context, data: {"released": True},
    )
    engine.handler_registry.register(
        "cancel-order",
        lambda context, data: {"cancelled": True},
    )

    result = engine.execute(
        create_plan(engine).plan_id,
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
    )

    assert len(result.plan.records) == 2
    assert all(record.successful for record in result.plan.records)


def test_engine_retries_retryable_failure() -> None:
    engine = build_engine()
    attempts = {"count": 0}

    def cancel_order(context, data):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise NetworkError("Temporary supplier API failure.")
        return {"cancelled": True}

    engine.handler_registry.register("cancel-order", cancel_order)
    engine.handler_registry.register(
        "release-payment",
        lambda context, data: {"released": True},
    )

    result = engine.execute(
        create_plan(engine).plan_id,
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
    )

    assert result.successful is True
    assert attempts["count"] == 2


def test_stop_strategy_fails_plan() -> None:
    engine = build_engine()
    engine.handler_registry.register(
        "cancel-order",
        lambda context, data: (_ for _ in ()).throw(
            NetworkError("Supplier API unavailable.")
        ),
    )
    engine.handler_registry.register(
        "release-payment",
        lambda context, data: {"released": True},
    )

    result = engine.execute(
        create_plan(engine).plan_id,
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
    )

    assert result.plan.status is CompensationStatus.FAILED
    assert result.plan.failed_step_ids == ("cancel-order",)


def test_manual_intervention_strategy() -> None:
    engine = build_engine()
    steps = (
        CompensationStepDefinition(
            step_id="manual-refund",
            name="Manual Refund",
            original_step_id="capture-payment",
            handler_key="manual-refund",
            order=1,
            failure_strategy=(
                CompensationFailureStrategy.REQUIRE_MANUAL_INTERVENTION
            ),
            idempotency_key="WF-200:manual-refund",
        ),
    )
    plan = engine.create_plan(
        policy_id="procurement-compensation",
        workflow_instance_id="WF-200",
        workflow_id="supplier-procurement",
        workflow_version="1.0.0",
        steps=steps,
    )
    engine.handler_registry.register(
        "manual-refund",
        lambda context, data: (_ for _ in ()).throw(
            RuntimeError("Manual refund required.")
        ),
    )

    result = engine.execute(
        plan.plan_id,
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
    )

    assert result.requires_manual_intervention is True


def test_idempotent_completed_plan_returns_existing_result() -> None:
    engine = build_engine()
    calls = {"count": 0}

    def cancel_order(context, data):
        calls["count"] += 1
        return {"cancelled": True}

    engine.handler_registry.register("cancel-order", cancel_order)
    engine.handler_registry.register(
        "release-payment",
        lambda context, data: {"released": True},
    )

    plan = create_plan(engine)
    context = create_workflow_context(
        "supplier-procurement",
        "1.0.0",
    )

    first = engine.execute(plan.plan_id, context=context)
    second = engine.execute(plan.plan_id, context=context)

    assert first.successful is True
    assert second.successful is True
    assert calls["count"] == 1


def test_terminal_failed_plan_cannot_execute_again() -> None:
    engine = build_engine()
    engine.handler_registry.register(
        "cancel-order",
        lambda context, data: (_ for _ in ()).throw(
            RuntimeError("Failure.")
        ),
    )
    engine.handler_registry.register(
        "release-payment",
        lambda context, data: {"released": True},
    )

    plan = create_plan(engine)
    context = create_workflow_context(
        "supplier-procurement",
        "1.0.0",
    )
    engine.execute(plan.plan_id, context=context)

    with pytest.raises(WorkflowStateError):
        engine.execute(plan.plan_id, context=context)


def test_engine_cancels_pending_plan() -> None:
    engine = build_engine()
    cancelled = engine.cancel(
        create_plan(engine).plan_id,
        actor_id="USER-1",
        reason="Manual recovery selected.",
    )
    assert cancelled.status is CompensationStatus.CANCELLED


def test_plan_serialises_safely() -> None:
    engine = build_engine()
    engine.handler_registry.register(
        "cancel-order",
        lambda context, data: {"cancelled": True},
    )
    engine.handler_registry.register(
        "release-payment",
        lambda context, data: {"released": True},
    )

    result = engine.execute(
        create_plan(engine).plan_id,
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
    )

    payload = result.plan.as_dict()
    assert payload["status"] == "compensated"
    assert len(payload["records"]) == 2