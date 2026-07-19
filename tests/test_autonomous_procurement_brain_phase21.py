"""Tests for Phase 21 Package I autonomous procurement brain."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestration import (
    AutonomousAction,
    AutonomousProcurementBrain,
    AutonomousProcurementContext,
    AutonomousProcurementPolicy,
    AutonomyMode,
    BrainConfidence,
    DecisionCategory,
    DecisionFinding,
    DecisionSeverity,
    IntelligenceCategory,
    IntelligencePriority,
    ProcurementDecision,
    ProcurementDecisionResult,
    ProcurementIntelligenceResult,
    ProcurementRecommendation,
    RecommendationType,
    SupplierRanking,
)


def decision_result(
    decision: ProcurementDecision = ProcurementDecision.PROCEED,
    score: float = 95,
) -> ProcurementDecisionResult:
    findings = ()

    if decision is not ProcurementDecision.PROCEED:
        findings = (
            DecisionFinding(
                code="BLOCKER",
                message="Blocking condition.",
                category=DecisionCategory.RISK,
                severity=DecisionSeverity.HIGH,
                blocking=True,
            ),
        )

    return ProcurementDecisionResult(
        case_id="CASE-100",
        decision=decision,
        score=score,
        findings=findings,
        policy_id="decision-policy",
        policy_version="1.0.0",
    )


def intelligence_result(
    *,
    recommendation_type: RecommendationType = (
        RecommendationType.SELECT_SUPPLIER
    ),
    supplier_score: float = 90,
) -> ProcurementIntelligenceResult:
    recommendation = ProcurementRecommendation(
        recommendation_type=recommendation_type,
        title="Recommended action",
        rationale="Strong expected business value.",
        priority=IntelligencePriority.HIGH,
        category=IntelligenceCategory.SUPPLIER,
        expected_value_score=90,
        supplier_id="SUP-100",
        quotation_id="Q-100",
    )

    ranking = SupplierRanking(
        rank=1,
        supplier_id="SUP-100",
        supplier_name="Supplier 100",
        quotation_id="Q-100",
        score=supplier_score,
        landed_cost=100,
        risk_score=20,
    )

    return ProcurementIntelligenceResult(
        case_id="CASE-100",
        rankings=(ranking,),
        recommendations=(recommendation,),
        policy_id="intelligence-policy",
        policy_version="1.0.0",
    )


def safe_context() -> AutonomousProcurementContext:
    return AutonomousProcurementContext(
        approval_satisfied=True,
        payment_cleared=True,
        documents_complete=True,
        shipment_ready=True,
        compensation_available=True,
        autonomy_mode=AutonomyMode.CONTROLLED_AUTOMATION,
    )


def test_policy_validates_confidence() -> None:
    with pytest.raises(ValueError):
        AutonomousProcurementPolicy(
            policy_id="invalid",
            name="Invalid",
            minimum_execution_confidence=101,
        )


def test_proceed_decision_creates_proceed_action() -> None:
    result = AutonomousProcurementBrain().plan(
        decision_result(),
        intelligence_result(),
        context=safe_context(),
    )

    assert any(
        action.action is AutonomousAction.PROCEED
        for action in result.actions
    )


def test_supplier_recommendation_maps_to_action() -> None:
    result = AutonomousProcurementBrain().plan(
        decision_result(),
        intelligence_result(),
        context=safe_context(),
    )

    assert any(
        action.action is AutonomousAction.SELECT_SUPPLIER
        for action in result.actions
    )


def test_missing_payment_adds_secure_payment() -> None:
    context = replace(
        safe_context(),
        payment_cleared=False,
    )

    result = AutonomousProcurementBrain().plan(
        decision_result(),
        intelligence_result(),
        context=context,
    )

    assert any(
        action.action is AutonomousAction.SECURE_PAYMENT
        for action in result.actions
    )
    assert result.safe_to_execute is False


def test_missing_documents_adds_action() -> None:
    context = replace(
        safe_context(),
        documents_complete=False,
    )

    result = AutonomousProcurementBrain().plan(
        decision_result(),
        intelligence_result(),
        context=context,
    )

    assert any(
        action.action is AutonomousAction.COMPLETE_DOCUMENTS
        for action in result.actions
    )


def test_reject_decision_adds_compensation() -> None:
    result = AutonomousProcurementBrain().plan(
        decision_result(ProcurementDecision.REJECT, 30),
        intelligence_result(),
        context=safe_context(),
    )

    assert any(
        action.action is AutonomousAction.REJECT
        for action in result.actions
    )
    assert any(
        action.action is AutonomousAction.START_COMPENSATION
        for action in result.actions
    )


def test_hold_decision_adds_hold_action() -> None:
    result = AutonomousProcurementBrain().plan(
        decision_result(ProcurementDecision.HOLD, 60),
        intelligence_result(),
        context=safe_context(),
    )

    assert any(
        action.action is AutonomousAction.HOLD
        for action in result.actions
    )


def test_manual_review_decision_adds_review() -> None:
    result = AutonomousProcurementBrain().plan(
        decision_result(
            ProcurementDecision.MANUAL_REVIEW,
            70,
        ),
        intelligence_result(),
        context=safe_context(),
    )

    assert any(
        action.action is AutonomousAction.MANUAL_REVIEW
        for action in result.actions
    )


def test_case_mismatch_is_rejected() -> None:
    intelligence = replace(
        intelligence_result(),
        case_id="CASE-OTHER",
    )

    with pytest.raises(ValueError):
        AutonomousProcurementBrain().plan(
            decision_result(),
            intelligence,
            context=safe_context(),
        )


def test_controlled_automation_can_be_safe() -> None:
    policy = AutonomousProcurementPolicy(
        policy_id="automation",
        name="Automation",
        require_human_approval_for_supplier_selection=False,
        require_human_approval_for_po=False,
    )

    result = AutonomousProcurementBrain(policy).plan(
        decision_result(),
        intelligence_result(),
        context=safe_context(),
    )

    assert result.confidence in {
        BrainConfidence.HIGH,
        BrainConfidence.VERY_HIGH,
    }


def test_advisory_mode_is_not_executable() -> None:
    context = replace(
        safe_context(),
        autonomy_mode=AutonomyMode.ADVISORY,
    )

    result = AutonomousProcurementBrain().plan(
        decision_result(),
        intelligence_result(),
        context=context,
    )

    assert result.safe_to_execute is False


def test_result_serialises() -> None:
    result = AutonomousProcurementBrain().plan(
        decision_result(),
        intelligence_result(),
        context=safe_context(),
    )

    payload = result.as_dict()

    assert payload["case_id"] == "CASE-100"
    assert payload["actions"]
    assert "confidence" in payload


def test_disabled_policy_rejects_execution() -> None:
    brain = AutonomousProcurementBrain(
        AutonomousProcurementPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        brain.plan(
            decision_result(),
            intelligence_result(),
            context=safe_context(),
        )