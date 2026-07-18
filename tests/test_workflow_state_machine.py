"""Tests for Phase 21 Package B workflow state machine."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestration.exceptions import (
    WorkflowStateError,
)
from app.orchestration.state_machine import (
    WorkflowStateMachine,
)
from app.orchestration.transition_policy import (
    TransitionGuard,
    TransitionPolicy,
    build_default_transition_policy,
)
from app.orchestration.workflow_models import (
    StepStatus,
    WorkflowInstance,
    WorkflowStatus,
)


def build_instance(
    status: WorkflowStatus = WorkflowStatus.CREATED,
) -> WorkflowInstance:
    """Create a workflow instance for state-machine tests."""

    return WorkflowInstance(
        workflow_id="procurement-order",
        workflow_version="1.0.0",
        status=status,
        data={
            "buyer_payment_cleared": False,
        },
    )


def test_default_policy_allows_created_to_ready() -> None:
    policy = build_default_transition_policy()
    instance = build_instance()

    violations = policy.validate_workflow_transition(
        instance,
        WorkflowStatus.READY,
    )

    assert violations == ()


def test_default_policy_rejects_created_to_completed() -> None:
    policy = build_default_transition_policy()
    instance = build_instance()

    violations = policy.validate_workflow_transition(
        instance,
        WorkflowStatus.COMPLETED,
    )

    assert len(violations) == 1
    assert (
        violations[0].code
        == "INVALID_WORKFLOW_TRANSITION"
    )


def test_state_machine_prepares_workflow() -> None:
    machine = WorkflowStateMachine()
    instance = build_instance()

    result = machine.prepare(
        instance,
        reason="Definition validated.",
        actor_id="USER-1",
    )

    assert result.accepted is True
    assert result.changed is True
    assert result.previous_status is WorkflowStatus.CREATED
    assert result.instance.status is WorkflowStatus.READY
    assert len(result.instance.transitions) == 1
    assert (
        result.instance.transitions[0].reason
        == "Definition validated."
    )


def test_state_machine_starts_ready_workflow() -> None:
    machine = WorkflowStateMachine()
    instance = build_instance(
        WorkflowStatus.READY
    )

    result = machine.start(instance)

    assert result.instance.status is WorkflowStatus.RUNNING
    assert result.accepted is True


def test_state_machine_supports_wait_and_resume() -> None:
    machine = WorkflowStateMachine()
    running = build_instance(
        WorkflowStatus.RUNNING
    )

    waiting = machine.wait(
        running,
        reason="Awaiting supplier quotation.",
    ).instance

    resumed = machine.start(
        waiting,
        reason="Quotation received.",
    ).instance

    assert waiting.status is WorkflowStatus.WAITING
    assert resumed.status is WorkflowStatus.RUNNING
    assert len(resumed.transitions) == 2


def test_state_machine_supports_pause_and_resume() -> None:
    machine = WorkflowStateMachine()
    running = build_instance(
        WorkflowStatus.RUNNING
    )

    paused = machine.pause(
        running,
        reason="Human review required.",
    ).instance

    resumed = machine.start(paused).instance

    assert paused.status is WorkflowStatus.PAUSED
    assert resumed.status is WorkflowStatus.RUNNING


def test_state_machine_completes_running_workflow() -> None:
    machine = WorkflowStateMachine()
    running = build_instance(
        WorkflowStatus.RUNNING
    )

    result = machine.complete(
        running,
        reason="All steps succeeded.",
    )

    assert result.instance.status is WorkflowStatus.COMPLETED
    assert machine.policy.is_workflow_terminal(
        result.instance.status
    )


def test_terminal_workflow_cannot_transition() -> None:
    machine = WorkflowStateMachine()
    completed = build_instance(
        WorkflowStatus.COMPLETED
    )

    with pytest.raises(WorkflowStateError):
        machine.cancel(completed)


def test_non_raising_machine_returns_rejected_result() -> None:
    machine = WorkflowStateMachine(
        raise_on_rejection=False
    )
    created = build_instance()

    result = machine.complete(created)

    assert result.accepted is False
    assert result.changed is False
    assert result.instance is created
    assert result.violation_count == 1


def test_idempotent_transition_is_accepted_without_history() -> None:
    machine = WorkflowStateMachine()
    running = build_instance(
        WorkflowStatus.RUNNING
    )

    result = machine.start(running)

    assert result.accepted is True
    assert result.changed is False
    assert result.instance is running
    assert result.instance.transitions == ()


def test_policy_can_disable_idempotent_transitions() -> None:
    default = build_default_transition_policy()

    policy = TransitionPolicy(
        workflow_transitions=(
            default.workflow_transitions
        ),
        step_transitions=default.step_transitions,
        workflow_terminal_states=(
            default.workflow_terminal_states
        ),
        step_terminal_states=(
            default.step_terminal_states
        ),
        allow_idempotent_transitions=False,
    )

    machine = WorkflowStateMachine(
        policy,
        raise_on_rejection=False,
    )

    instance = build_instance(
        WorkflowStatus.RUNNING
    )

    result = machine.start(instance)

    assert result.accepted is False
    assert (
        result.violations[0].code
        == "IDEMPOTENT_TRANSITION_NOT_ALLOWED"
    )


def test_failed_workflow_can_enter_compensation() -> None:
    machine = WorkflowStateMachine()
    failed = build_instance(
        WorkflowStatus.FAILED
    )

    compensating = machine.begin_compensation(
        failed
    ).instance

    compensated = machine.finish_compensation(
        compensating
    ).instance

    assert (
        compensating.status
        is WorkflowStatus.COMPENSATING
    )
    assert (
        compensated.status
        is WorkflowStatus.COMPENSATED
    )


def test_running_workflow_can_fail() -> None:
    machine = WorkflowStateMachine()
    running = build_instance(
        WorkflowStatus.RUNNING
    )

    result = machine.fail(
        running,
        reason="Supplier API exhausted retries.",
    )

    assert result.instance.status is WorkflowStatus.FAILED


def test_created_workflow_can_be_cancelled() -> None:
    machine = WorkflowStateMachine()
    instance = build_instance()

    result = machine.cancel(
        instance,
        reason="Buyer withdrew request.",
    )

    assert (
        result.instance.status
        is WorkflowStatus.CANCELLED
    )


def test_step_transition_pending_to_ready() -> None:
    machine = WorkflowStateMachine()

    result = machine.transition_step(
        StepStatus.PENDING,
        StepStatus.READY,
        step_id="verify-buyer",
    )

    assert result.accepted is True
    assert result.changed is True


def test_step_transition_ready_to_running() -> None:
    machine = WorkflowStateMachine()

    result = machine.transition_step(
        StepStatus.READY,
        StepStatus.RUNNING,
        step_id="compare-quotations",
    )

    assert result.accepted is True


def test_step_transition_running_to_succeeded() -> None:
    machine = WorkflowStateMachine()

    result = machine.transition_step(
        StepStatus.RUNNING,
        StepStatus.SUCCEEDED,
        step_id="issue-purchase-order",
    )

    assert result.accepted is True
    assert (
        result.requested_status
        is StepStatus.SUCCEEDED
    )


def test_terminal_step_cannot_transition() -> None:
    machine = WorkflowStateMachine()

    with pytest.raises(WorkflowStateError):
        machine.transition_step(
            StepStatus.SUCCEEDED,
            StepStatus.RUNNING,
            step_id="completed-step",
        )


def test_failed_step_can_be_retried() -> None:
    machine = WorkflowStateMachine()

    result = machine.transition_step(
        StepStatus.FAILED,
        StepStatus.READY,
        step_id="freight-quote",
    )

    assert result.accepted is True


def test_step_transition_requires_step_id() -> None:
    machine = WorkflowStateMachine(
        raise_on_rejection=False
    )

    result = machine.transition_step(
        StepStatus.PENDING,
        StepStatus.READY,
        step_id="",
    )

    assert result.accepted is False
    assert result.violations[0].code == "STEP_ID_REQUIRED"


def test_can_transition_helpers_are_deterministic() -> None:
    machine = WorkflowStateMachine()
    instance = build_instance(
        WorkflowStatus.READY
    )

    assert machine.can_transition_workflow(
        instance,
        WorkflowStatus.RUNNING,
    ) is True

    assert machine.can_transition_workflow(
        instance,
        WorkflowStatus.COMPLETED,
    ) is False

    assert machine.can_transition_step(
        StepStatus.READY,
        StepStatus.RUNNING,
        step_id="supplier-check",
    ) is True


def test_transition_history_is_immutable() -> None:
    machine = WorkflowStateMachine()
    original = build_instance()

    ready = machine.prepare(original).instance
    running = machine.start(ready).instance

    assert original.status is WorkflowStatus.CREATED
    assert original.transitions == ()
    assert len(ready.transitions) == 1
    assert len(running.transitions) == 2


def test_transition_guard_can_block_completion() -> None:
    guard = TransitionGuard(
        name="buyer-payment-cleared",
        predicate=lambda instance, target: (
            target is not WorkflowStatus.COMPLETED
            or bool(
                instance.data.get(
                    "buyer_payment_cleared"
                )
            )
        ),
        failure_code="BUYER_PAYMENT_NOT_CLEARED",
        failure_message=(
            "Buyer payment must clear before completion."
        ),
    )

    base_policy = build_default_transition_policy()

    guarded_policy = TransitionPolicy(
        workflow_transitions=(
            base_policy.workflow_transitions
        ),
        step_transitions=base_policy.step_transitions,
        workflow_terminal_states=(
            base_policy.workflow_terminal_states
        ),
        step_terminal_states=(
            base_policy.step_terminal_states
        ),
        allow_idempotent_transitions=True,
        guards=(guard,),
    )

    machine = WorkflowStateMachine(
        guarded_policy,
        raise_on_rejection=False,
    )

    running = build_instance(
        WorkflowStatus.RUNNING
    )

    result = machine.complete(running)

    assert result.accepted is False
    assert (
        result.violations[0].code
        == "BUYER_PAYMENT_NOT_CLEARED"
    )


def test_transition_guard_allows_completion_when_satisfied() -> None:
    guard = TransitionGuard(
        name="buyer-payment-cleared",
        predicate=lambda instance, target: (
            target is not WorkflowStatus.COMPLETED
            or bool(
                instance.data.get(
                    "buyer_payment_cleared"
                )
            )
        ),
    )

    base_policy = build_default_transition_policy()

    guarded_policy = TransitionPolicy(
        workflow_transitions=(
            base_policy.workflow_transitions
        ),
        step_transitions=base_policy.step_transitions,
        workflow_terminal_states=(
            base_policy.workflow_terminal_states
        ),
        step_terminal_states=(
            base_policy.step_terminal_states
        ),
        guards=(guard,),
    )

    machine = WorkflowStateMachine(guarded_policy)

    running = replace(
        build_instance(WorkflowStatus.RUNNING),
        data={
            "buyer_payment_cleared": True,
        },
    )

    result = machine.complete(running)

    assert result.accepted is True
    assert result.instance.status is WorkflowStatus.COMPLETED


def test_transition_guard_failure_fails_closed() -> None:
    def broken_guard(
        _: WorkflowInstance,
        __: WorkflowStatus,
    ) -> bool:
        raise RuntimeError("Guard dependency unavailable.")

    guard = TransitionGuard(
        name="broken-guard",
        predicate=broken_guard,
    )

    base_policy = build_default_transition_policy()

    policy = TransitionPolicy(
        workflow_transitions=(
            base_policy.workflow_transitions
        ),
        step_transitions=base_policy.step_transitions,
        workflow_terminal_states=(
            base_policy.workflow_terminal_states
        ),
        step_terminal_states=(
            base_policy.step_terminal_states
        ),
        guards=(guard,),
    )

    machine = WorkflowStateMachine(
        policy,
        raise_on_rejection=False,
    )

    result = machine.start(
        build_instance(WorkflowStatus.READY)
    )

    assert result.accepted is False
    assert (
        result.violations[0].code
        == "TRANSITION_GUARD_ERROR"
    )