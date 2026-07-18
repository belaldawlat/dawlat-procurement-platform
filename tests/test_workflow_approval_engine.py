"""Tests for Phase 21 Package D approval engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.orchestration import (
    ApprovalDecisionType,
    ApprovalEngine,
    ApprovalPolicy,
    ApprovalStatus,
    ApprovalSubjectType,
    InMemoryApprovalStore,
    WorkflowIntegrityError,
    WorkflowNotFoundError,
    WorkflowStateError,
    WorkflowValidationError,
)


def build_policy(
    *,
    policy_id: str = "commercial-approval",
    required_approvals: int = 2,
    allow_requester_approval: bool = False,
    reject_on_first_rejection: bool = True,
) -> ApprovalPolicy:
    """Create a standard commercial approval policy."""

    return ApprovalPolicy(
        policy_id=policy_id,
        name="Commercial Approval",
        required_approvals=required_approvals,
        allowed_roles=frozenset(
            {
                "commercial_manager",
                "finance_manager",
                "director",
            }
        ),
        minimum_amount=1_000,
        maximum_amount=100_000,
        allow_requester_approval=(
            allow_requester_approval
        ),
        reject_on_first_rejection=(
            reject_on_first_rejection
        ),
    )


def build_engine(
    *,
    raise_on_rejection: bool = True,
) -> ApprovalEngine:
    """Create an isolated approval engine."""

    store = InMemoryApprovalStore()
    engine = ApprovalEngine(
        store=store,
        raise_on_rejection=raise_on_rejection,
    )
    engine.register_policy(build_policy())
    return engine


def create_request(
    engine: ApprovalEngine,
    *,
    requested_by: str = "USER-REQUESTER",
    amount: float = 25_000,
    expires_at: str = "",
):
    """Create a standard purchase-order approval request."""

    return engine.create_request(
        policy_id="commercial-approval",
        subject_type=(
            ApprovalSubjectType.PURCHASE_ORDER
        ),
        subject_id="PO-100",
        requested_by=requested_by,
        workflow_instance_id="WF-100",
        workflow_step_id="approve-commercials",
        title="Approve purchase order",
        amount=amount,
        currency="aud",
        expires_at=expires_at,
        metadata={
            "api_key": "secret-value",
        },
    )


def test_policy_validates_required_approvals() -> None:
    with pytest.raises(ValueError):
        ApprovalPolicy(
            policy_id="invalid",
            name="Invalid",
            required_approvals=0,
        )


def test_policy_validates_amount_range() -> None:
    with pytest.raises(ValueError):
        ApprovalPolicy(
            policy_id="invalid",
            name="Invalid",
            minimum_amount=10_000,
            maximum_amount=1_000,
        )


def test_store_registers_policy() -> None:
    store = InMemoryApprovalStore()
    policy = build_policy()

    stored = store.register_policy(policy)

    assert stored is policy
    assert store.get_policy(policy.policy_id) is policy


def test_store_rejects_duplicate_policy() -> None:
    store = InMemoryApprovalStore()
    policy = build_policy()

    store.register_policy(policy)

    with pytest.raises(WorkflowIntegrityError):
        store.register_policy(policy)


def test_store_allows_policy_replacement() -> None:
    store = InMemoryApprovalStore()
    first = build_policy(required_approvals=1)
    second = build_policy(required_approvals=3)

    store.register_policy(first)
    store.register_policy(
        second,
        replace_existing=True,
    )

    assert (
        store.get_policy("commercial-approval")
        .required_approvals
        == 3
    )


def test_engine_creates_valid_request() -> None:
    engine = build_engine()

    request = create_request(engine)

    assert request.status is ApprovalStatus.PENDING
    assert request.subject_id == "PO-100"
    assert request.currency == "AUD"
    assert request.approval_count == 0
    assert request.metadata["api_key"] != "secret-value"


def test_engine_rejects_amount_below_policy() -> None:
    engine = build_engine()

    with pytest.raises(WorkflowValidationError):
        create_request(
            engine,
            amount=500,
        )


def test_engine_rejects_amount_above_policy() -> None:
    engine = build_engine()

    with pytest.raises(WorkflowValidationError):
        create_request(
            engine,
            amount=200_000,
        )


def test_engine_rejects_unknown_policy() -> None:
    engine = build_engine()

    with pytest.raises(WorkflowNotFoundError):
        engine.create_request(
            policy_id="missing-policy",
            subject_type=ApprovalSubjectType.PAYMENT,
            subject_id="PAY-100",
            requested_by="USER-1",
        )


def test_first_approval_creates_partial_status() -> None:
    engine = build_engine()
    request = create_request(engine)

    result = engine.approve(
        request.request_id,
        approver_id="USER-MANAGER",
        approver_role="commercial_manager",
        reason="Commercial terms verified.",
    )

    assert result.accepted is True
    assert result.approved is False
    assert (
        result.request.status
        is ApprovalStatus.PARTIALLY_APPROVED
    )
    assert result.request.approval_count == 1


def test_second_approval_satisfies_quorum() -> None:
    engine = build_engine()
    request = create_request(engine)

    first = engine.approve(
        request.request_id,
        approver_id="USER-COMMERCIAL",
        approver_role="commercial_manager",
    )

    second = engine.approve(
        first.request.request_id,
        approver_id="USER-FINANCE",
        approver_role="finance_manager",
    )

    assert second.accepted is True
    assert second.approved is True
    assert (
        second.request.status
        is ApprovalStatus.APPROVED
    )
    assert second.request.approval_count == 2
    assert engine.is_gate_satisfied(
        request.request_id
    ) is True


def test_requester_cannot_approve_own_request() -> None:
    engine = build_engine()
    request = create_request(
        engine,
        requested_by="USER-REQUESTER",
    )

    with pytest.raises(WorkflowStateError):
        engine.approve(
            request.request_id,
            approver_id="USER-REQUESTER",
            approver_role="commercial_manager",
        )


def test_disallowed_role_cannot_approve() -> None:
    engine = build_engine()
    request = create_request(engine)

    with pytest.raises(WorkflowStateError):
        engine.approve(
            request.request_id,
            approver_id="USER-WAREHOUSE",
            approver_role="warehouse_operator",
        )


def test_duplicate_approver_decision_is_blocked() -> None:
    engine = build_engine()
    request = create_request(engine)

    engine.approve(
        request.request_id,
        approver_id="USER-COMMERCIAL",
        approver_role="commercial_manager",
    )

    with pytest.raises(WorkflowStateError):
        engine.approve(
            request.request_id,
            approver_id="USER-COMMERCIAL",
            approver_role="commercial_manager",
        )


def test_first_rejection_rejects_request() -> None:
    engine = build_engine()
    request = create_request(engine)

    result = engine.reject(
        request.request_id,
        approver_id="USER-FINANCE",
        approver_role="finance_manager",
        reason="Margin is below approved threshold.",
    )

    assert result.rejected is True
    assert (
        result.request.status
        is ApprovalStatus.REJECTED
    )
    assert result.request.rejection_count == 1


def test_terminal_request_rejects_further_decisions() -> None:
    engine = build_engine()
    request = create_request(engine)

    rejected = engine.reject(
        request.request_id,
        approver_id="USER-FINANCE",
        approver_role="finance_manager",
    )

    with pytest.raises(WorkflowStateError):
        engine.approve(
            rejected.request.request_id,
            approver_id="USER-DIRECTOR",
            approver_role="director",
        )


def test_non_raising_engine_returns_violations() -> None:
    store = InMemoryApprovalStore()
    engine = ApprovalEngine(
        store=store,
        raise_on_rejection=False,
    )
    engine.register_policy(build_policy())

    request = create_request(engine)

    result = engine.approve(
        request.request_id,
        approver_id=request.requested_by,
        approver_role="commercial_manager",
    )

    assert result.accepted is False
    assert result.decision is None
    assert any(
        violation.code
        == "SEPARATION_OF_DUTIES_VIOLATION"
        for violation in result.violations
    )


def test_expired_request_fails_closed() -> None:
    engine = build_engine()

    expired_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    ).isoformat()

    request = create_request(
        engine,
        expires_at=expired_at,
    )

    with pytest.raises(WorkflowStateError):
        engine.approve(
            request.request_id,
            approver_id="USER-FINANCE",
            approver_role="finance_manager",
        )

    refreshed = engine.refresh_status(
        request.request_id
    )

    assert refreshed.status is ApprovalStatus.EXPIRED


def test_future_expiry_remains_pending() -> None:
    engine = build_engine()

    future_at = (
        datetime.now(timezone.utc)
        + timedelta(hours=1)
    ).isoformat()

    request = create_request(
        engine,
        expires_at=future_at,
    )

    refreshed = engine.refresh_status(
        request.request_id
    )

    assert refreshed.status is ApprovalStatus.PENDING


def test_invalid_expiry_timestamp_is_rejected() -> None:
    engine = build_engine()

    with pytest.raises(WorkflowValidationError):
        create_request(
            engine,
            expires_at="not-a-timestamp",
        )


def test_cancel_pending_request() -> None:
    engine = build_engine()
    request = create_request(engine)

    cancelled = engine.cancel(
        request.request_id,
        actor_id="USER-REQUESTER",
        reason="Purchase requirement withdrawn.",
    )

    assert (
        cancelled.status
        is ApprovalStatus.CANCELLED
    )


def test_terminal_request_cannot_be_cancelled() -> None:
    engine = build_engine()
    request = create_request(engine)

    rejected = engine.reject(
        request.request_id,
        approver_id="USER-DIRECTOR",
        approver_role="director",
    )

    with pytest.raises(WorkflowStateError):
        engine.cancel(
            rejected.request.request_id,
            actor_id="USER-REQUESTER",
        )


def test_require_approved_returns_approved_request() -> None:
    store = InMemoryApprovalStore()
    engine = ApprovalEngine(store=store)

    policy = build_policy(required_approvals=1)
    engine.register_policy(policy)

    request = create_request(engine)

    engine.approve(
        request.request_id,
        approver_id="USER-DIRECTOR",
        approver_role="director",
    )

    approved = engine.require_approved(
        request.request_id
    )

    assert approved.status is ApprovalStatus.APPROVED


def test_require_approved_fails_for_pending_request() -> None:
    engine = build_engine()
    request = create_request(engine)

    with pytest.raises(WorkflowStateError):
        engine.require_approved(request.request_id)


def test_store_lists_requests_by_status() -> None:
    engine = build_engine()

    first = create_request(engine)
    second = engine.create_request(
        policy_id="commercial-approval",
        subject_type=ApprovalSubjectType.PAYMENT,
        subject_id="PAY-200",
        requested_by="USER-2",
        amount=10_000,
        currency="AUD",
    )

    engine.reject(
        second.request_id,
        approver_id="USER-DIRECTOR",
        approver_role="director",
    )

    pending = engine.store.list_requests(
        status=ApprovalStatus.PENDING
    )
    rejected = engine.store.list_requests(
        status=ApprovalStatus.REJECTED
    )

    assert [
        request.request_id
        for request in pending
    ] == [first.request_id]

    assert [
        request.request_id
        for request in rejected
    ] == [second.request_id]


def test_request_serialises_decision_history() -> None:
    store = InMemoryApprovalStore()
    engine = ApprovalEngine(store=store)

    engine.register_policy(
        build_policy(required_approvals=1)
    )

    request = create_request(engine)

    result = engine.approve(
        request.request_id,
        approver_id="USER-DIRECTOR",
        approver_role="director",
    )

    payload = result.request.as_dict()

    assert payload["status"] == "approved"
    assert payload["approval_count"] == 1
    assert (
        payload["decisions"][0]["decision"]
        == ApprovalDecisionType.APPROVE.value
    )