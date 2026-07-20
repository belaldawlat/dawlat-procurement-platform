"""Tests for Phase 21 Package U enterprise execution intelligence."""

from __future__ import annotations

import pytest

from app.orchestration import (
    EnterpriseExecution,
    EnterpriseExecutionCheckpointStore,
    EnterpriseExecutionEventBridge,
    EnterpriseExecutionIntelligence,
    EnterpriseExecutionPolicy,
    EnterpriseExecutionRegistry,
    EnterpriseExecutionSideEffect,
    EnterpriseExecutionStatus,
    EnterpriseExecutionStep,
    EnterpriseExecutionStepStatus,
    EnterpriseExecutionStore,
    EnterpriseExecutionTelemetry,
    WorkflowIntegrityError,
)


def step(
    step_id: str,
    handler_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    side_effect: EnterpriseExecutionSideEffect = (
        EnterpriseExecutionSideEffect.NONE
    ),
    requires_approval: bool = False,
    compensation_handler_id: str = "",
    maximum_attempts: int = 3,
) -> EnterpriseExecutionStep:
    return EnterpriseExecutionStep(
        step_id=step_id,
        name=step_id,
        handler_id=handler_id,
        depends_on=depends_on,
        payload={"step_id": step_id},
        side_effect=side_effect,
        requires_human_approval=requires_approval,
        compensation_handler_id=compensation_handler_id,
        maximum_attempts=maximum_attempts,
    )


def execution(
    *steps: EnterpriseExecutionStep,
) -> EnterpriseExecution:
    return EnterpriseExecution(
        execution_id="EXEC-100",
        case_id="CASE-100",
        name="Execution 100",
        steps=tuple(steps),
        correlation_id="CORR-100",
        decision_id="DEC-100",
        plan_id="PLAN-100",
    )


def build_engine() -> EnterpriseExecutionIntelligence:
    registry = EnterpriseExecutionRegistry()
    registry.register(
        "success",
        lambda payload: {"processed": payload["step_id"]},
    )

    return EnterpriseExecutionIntelligence(
        registry=registry,
        store=EnterpriseExecutionStore(),
        checkpoint_store=EnterpriseExecutionCheckpointStore(),
        telemetry=EnterpriseExecutionTelemetry(),
        event_bridge=EnterpriseExecutionEventBridge(),
    )


def test_policy_validates_limits() -> None:
    with pytest.raises(ValueError):
        EnterpriseExecutionPolicy(
            policy_id="invalid",
            name="Invalid",
            maximum_execution_steps=0,
        )


def test_execution_requires_steps() -> None:
    with pytest.raises(ValueError):
        EnterpriseExecution(
            execution_id="EXEC",
            case_id="CASE",
            name="Execution",
            steps=(),
        )


def test_execution_rejects_duplicate_step_ids() -> None:
    with pytest.raises(ValueError):
        execution(
            step("S1", "success"),
            step("S1", "success"),
        )


def test_registry_rejects_duplicate_handler() -> None:
    registry = EnterpriseExecutionRegistry()
    registry.register("handler", lambda payload: {})

    with pytest.raises(WorkflowIntegrityError):
        registry.register("handler", lambda payload: {})


def test_successful_execution_completes() -> None:
    engine = build_engine()

    result = engine.execute(
        execution(
            step("S1", "success"),
        )
    )

    assert result.successful is True
    assert result.execution.status is EnterpriseExecutionStatus.COMPLETED
    assert len(result.completed_steps) == 1


def test_dependencies_execute_in_order() -> None:
    order: list[str] = []
    registry = EnterpriseExecutionRegistry()
    registry.register(
        "ordered",
        lambda payload: order.append(
            payload["step_id"]
        ) or {"ok": True},
    )
    engine = EnterpriseExecutionIntelligence(
        registry=registry,
        store=EnterpriseExecutionStore(),
    )

    result = engine.execute(
        execution(
            step("S2", "ordered", depends_on=("S1",)),
            step("S1", "ordered"),
        )
    )

    assert result.successful is True
    assert order == ["S1", "S2"]


def test_missing_handler_fails_execution() -> None:
    engine = EnterpriseExecutionIntelligence(
        registry=EnterpriseExecutionRegistry(),
        store=EnterpriseExecutionStore(),
    )

    result = engine.execute(
        execution(
            step("S1", "missing", maximum_attempts=1),
        )
    )

    assert result.successful is False
    assert result.execution.status is EnterpriseExecutionStatus.FAILED
    assert result.failed_steps


def test_transient_failure_recovers() -> None:
    state = {"attempts": 0}
    registry = EnterpriseExecutionRegistry()

    def transient(payload):
        state["attempts"] += 1
        if state["attempts"] == 1:
            raise RuntimeError("temporary")
        return {"recovered": True}

    registry.register("transient", transient)
    engine = EnterpriseExecutionIntelligence(
        registry=registry,
        store=EnterpriseExecutionStore(),
    )

    result = engine.execute(
        execution(
            step("S1", "transient"),
        )
    )

    assert result.successful is True
    assert result.completed_steps[0].metadata["recovered"] is True


def test_compensation_can_resolve_terminal_failure() -> None:
    registry = EnterpriseExecutionRegistry()

    def failing(payload):
        raise RuntimeError("failed")

    registry.register("failing", failing)
    registry.register(
        "compensate",
        lambda payload: {"compensated": True},
    )
    engine = EnterpriseExecutionIntelligence(
        registry=registry,
        store=EnterpriseExecutionStore(),
        policy=EnterpriseExecutionPolicy(
            policy_id="compensate",
            name="Compensate",
            recover_failed_steps=False,
        ),
    )

    result = engine.execute(
        execution(
            step(
                "S1",
                "failing",
                compensation_handler_id="compensate",
            ),
        )
    )

    assert result.successful is True
    assert (
        result.completed_steps[0].step.status
        is EnterpriseExecutionStepStatus.COMPENSATED
    )


def test_financial_step_requires_approval() -> None:
    engine = build_engine()
    item = execution(
        step(
            "S1",
            "success",
            side_effect=EnterpriseExecutionSideEffect.FINANCIAL,
        )
    )

    result = engine.execute(item)

    assert result.successful is False
    assert any(
        issue.code == "STEP_APPROVAL_REQUIRED"
        for issue in result.issues
    )


def test_approved_financial_step_executes() -> None:
    engine = build_engine()
    item = execution(
        step(
            "S1",
            "success",
            side_effect=EnterpriseExecutionSideEffect.FINANCIAL,
        )
    )

    result = engine.execute(
        item,
        approved_step_ids=("S1",),
    )

    assert result.successful is True


def test_checkpoint_created_after_successful_step() -> None:
    engine = build_engine()
    item = execution(step("S1", "success"))

    result = engine.execute(item)
    checkpoints = engine.checkpoint_store.list_for_execution(
        item.execution_id
    )

    assert result.successful is True
    assert len(checkpoints) == 1


def test_telemetry_records_step_and_execution_duration() -> None:
    engine = build_engine()
    item = execution(step("S1", "success"))

    engine.execute(item)

    records = engine.telemetry.list_records(
        execution_id=item.execution_id
    )
    metric_names = {
        record.metric_name
        for record in records
    }

    assert "step_duration_ms" in metric_names
    assert "execution_duration_ms" in metric_names


def test_event_bridge_publishes_lifecycle_events() -> None:
    engine = build_engine()
    item = execution(step("S1", "success"))

    engine.execute(item)

    names = [
        event.event_name
        for event in engine.event_bridge.history()
    ]

    assert names == [
        "execution.started",
        "execution.completed",
    ]


def test_execution_is_persisted() -> None:
    engine = build_engine()
    item = execution(step("S1", "success"))

    result = engine.execute(item)

    stored = engine.get_execution(item.execution_id)

    assert stored == result.execution


def test_cycle_is_detected() -> None:
    engine = build_engine()
    item = execution(
        step("S1", "success", depends_on=("S2",)),
        step("S2", "success", depends_on=("S1",)),
    )

    result = engine.execute(item)

    assert result.successful is False
    assert any(
        issue.code == "EXECUTION_DEPENDENCY_CYCLE"
        for issue in result.issues
    )


def test_result_serialises() -> None:
    result = build_engine().execute(
        execution(step("S1", "success"))
    )

    payload = result.as_dict()

    assert payload["successful"] is True
    assert payload["completed_step_count"] == 1
    assert payload["execution"]["status"] == "completed"


def test_disabled_policy_rejects_execution() -> None:
    engine = EnterpriseExecutionIntelligence(
        policy=EnterpriseExecutionPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        engine.execute(
            execution(step("S1", "success"))
        )