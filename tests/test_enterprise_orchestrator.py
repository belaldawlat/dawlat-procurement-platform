"""Tests for Phase 21 Package J enterprise orchestrator."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestration import (
    AutonomousAction,
    AutonomousProcurementAction,
    AutonomousProcurementContext,
    AutonomousProcurementResult,
    BrainConfidence,
    DecisionCategory,
    DecisionFinding,
    DecisionSeverity,
    EnterpriseCommand,
    EnterpriseOrchestrationContext,
    EnterpriseOrchestrationPolicy,
    EnterpriseOrchestrationSnapshot,
    EnterpriseOrchestrator,
    EnterpriseStage,
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
    )


def intelligence_result() -> ProcurementIntelligenceResult:
    recommendation = ProcurementRecommendation(
        recommendation_type=RecommendationType.SELECT_SUPPLIER,
        title="Select supplier",
        rationale="Best value supplier.",
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
        score=90,
        landed_cost=100,
        risk_score=20,
    )

    return ProcurementIntelligenceResult(
        case_id="CASE-100",
        rankings=(ranking,),
        recommendations=(recommendation,),
    )


def autonomous_result(
    *,
    safe_to_execute: bool = True,
    confidence_score: float = 95,
    compensation: bool = False,
) -> AutonomousProcurementResult:
    actions = [
        AutonomousProcurementAction(
            action=AutonomousAction.PROCEED,
            title="Proceed",
            rationale="Controls passed.",
            priority=80,
            requires_human_approval=False,
            executable=True,
            source_decision=ProcurementDecision.PROCEED,
        )
    ]

    if compensation:
        actions.append(
            AutonomousProcurementAction(
                action=AutonomousAction.START_COMPENSATION,
                title="Start compensation",
                rationale="Rollback required.",
                priority=100,
                requires_human_approval=True,
                executable=True,
                source_decision=ProcurementDecision.REJECT,
            )
        )

    return AutonomousProcurementResult(
        case_id="CASE-100",
        confidence_score=confidence_score,
        confidence=BrainConfidence.VERY_HIGH,
        actions=tuple(actions),
        safe_to_execute=safe_to_execute,
    )


def snapshot(
    *,
    decision: ProcurementDecision = ProcurementDecision.PROCEED,
    approval_satisfied: bool = True,
    execution_requested: bool = True,
    dry_run: bool = False,
    safe_to_execute: bool = True,
    confidence_score: float = 95,
    compensation: bool = False,
) -> EnterpriseOrchestrationSnapshot:
    return EnterpriseOrchestrationSnapshot(
        case_id="CASE-100",
        decision_result=decision_result(decision),
        intelligence_result=intelligence_result(),
        autonomous_result=autonomous_result(
            safe_to_execute=safe_to_execute,
            confidence_score=confidence_score,
            compensation=compensation,
        ),
        context=EnterpriseOrchestrationContext(
            approval_satisfied=approval_satisfied,
            execution_requested=execution_requested,
            compensation_available=True,
            dry_run=dry_run,
        ),
    )


def test_policy_validates_confidence() -> None:
    with pytest.raises(ValueError):
        EnterpriseOrchestrationPolicy(
            policy_id="invalid",
            name="Invalid",
            minimum_autonomous_confidence=101,
        )


def test_ready_snapshot_executes() -> None:
    result = EnterpriseOrchestrator().coordinate(snapshot())

    assert result.successful is True
    assert result.execution_allowed is True
    assert result.command is EnterpriseCommand.EXECUTE


def test_missing_approval_requests_approval() -> None:
    result = EnterpriseOrchestrator().coordinate(
        snapshot(approval_satisfied=False)
    )

    assert result.execution_allowed is False
    assert result.command is EnterpriseCommand.REQUEST_APPROVAL
    assert result.stage is EnterpriseStage.APPROVAL_REQUIRED


def test_dry_run_blocks_execution() -> None:
    result = EnterpriseOrchestrator().coordinate(
        snapshot(dry_run=True)
    )

    assert result.successful is True
    assert result.execution_allowed is False
    assert result.stage is EnterpriseStage.READY_FOR_EXECUTION


def test_hold_blocks_execution() -> None:
    result = EnterpriseOrchestrator().coordinate(
        snapshot(decision=ProcurementDecision.HOLD)
    )

    assert result.successful is False
    assert result.command is EnterpriseCommand.HOLD


def test_manual_review_blocks_execution() -> None:
    result = EnterpriseOrchestrator().coordinate(
        snapshot(decision=ProcurementDecision.MANUAL_REVIEW)
    )

    assert result.command is EnterpriseCommand.MANUAL_REVIEW
    assert result.stage is EnterpriseStage.APPROVAL_REQUIRED


def test_reject_without_compensation() -> None:
    result = EnterpriseOrchestrator().coordinate(
        snapshot(decision=ProcurementDecision.REJECT)
    )

    assert result.command is EnterpriseCommand.REJECT
    assert result.compensation_required is False


def test_reject_with_compensation() -> None:
    result = EnterpriseOrchestrator().coordinate(
        snapshot(
            decision=ProcurementDecision.REJECT,
            compensation=True,
        )
    )

    assert result.command is EnterpriseCommand.START_COMPENSATION
    assert result.compensation_required is True


def test_low_confidence_requires_manual_review() -> None:
    result = EnterpriseOrchestrator().coordinate(
        snapshot(confidence_score=50)
    )

    assert result.command is EnterpriseCommand.MANUAL_REVIEW
    assert result.execution_allowed is False


def test_not_execution_requested_returns_plan() -> None:
    result = EnterpriseOrchestrator().coordinate(
        snapshot(execution_requested=False)
    )

    assert result.successful is True
    assert result.execution_allowed is False
    assert result.command is EnterpriseCommand.PROCEED


def test_unsafe_autonomous_plan_does_not_execute() -> None:
    result = EnterpriseOrchestrator().coordinate(
        snapshot(safe_to_execute=False)
    )

    assert result.execution_allowed is False


def test_snapshot_rejects_case_mismatch() -> None:
    with pytest.raises(ValueError):
        EnterpriseOrchestrationSnapshot(
            case_id="CASE-OTHER",
            decision_result=decision_result(),
            intelligence_result=intelligence_result(),
            autonomous_result=autonomous_result(),
            context=EnterpriseOrchestrationContext(),
        )


def test_result_serialises() -> None:
    result = EnterpriseOrchestrator().coordinate(snapshot())

    payload = result.as_dict()

    assert payload["case_id"] == "CASE-100"
    assert payload["command"] == "execute"
    assert payload["execution_allowed"] is True


def test_disabled_policy_rejects_execution() -> None:
    orchestrator = EnterpriseOrchestrator(
        EnterpriseOrchestrationPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        orchestrator.coordinate(snapshot())