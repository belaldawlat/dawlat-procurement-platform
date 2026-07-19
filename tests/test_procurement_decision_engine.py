"""Tests for Phase 21 Package G procurement decision engine."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestration import (
    BuyerDemand,
    BuyerReadiness,
    DecisionCategory,
    ProcurementCase,
    ProcurementDecision,
    ProcurementDecisionContext,
    ProcurementDecisionEngine,
    ProcurementDecisionPolicy,
    QuotationCompliance,
    SupplierQuotation,
)


def build_case(
    *,
    readiness: BuyerReadiness = BuyerReadiness.COMMITTED,
    compliance: QuotationCompliance = QuotationCompliance.COMPLIANT,
    selected: bool = True,
) -> ProcurementCase:
    quotation = SupplierQuotation(
        supplier_id="SUP-100",
        quotation_id="Q-100",
        unit_price=2.5,
        currency="USD",
        incoterm="CIF",
        lead_time_days=30,
        landed_cost=3.2,
        compliance=compliance,
        score=92,
    )

    return ProcurementCase(
        demand=BuyerDemand(
            buyer_id="BUY-100",
            product_name="Premium Basmati Rice",
            quantity=1000,
            unit="kg",
            destination_country="AU",
            readiness=readiness,
        ),
        quotations=(quotation,),
        selected_quotation_id=(
            quotation.quotation_id if selected else ""
        ),
    )


def ready_context() -> ProcurementDecisionContext:
    return ProcurementDecisionContext(
        approval_satisfied=True,
        buyer_payment_cleared=True,
        shipment_ready=True,
        supplier_qualified=True,
        documents_complete=True,
        landed_cost_budget_ratio=0.95,
        supplier_risk_score=20,
        external_risk_score=25,
    )


def test_policy_validates_threshold_order() -> None:
    with pytest.raises(ValueError):
        ProcurementDecisionPolicy(
            policy_id="invalid",
            name="Invalid",
            proceed_score_threshold=60,
            manual_review_score_threshold=70,
        )


def test_ready_case_proceeds() -> None:
    result = ProcurementDecisionEngine().evaluate(
        build_case(),
        context=ready_context(),
    )

    assert result.decision is ProcurementDecision.PROCEED
    assert result.can_proceed is True
    assert result.score == 100
    assert result.findings == ()


def test_uncommitted_buyer_holds_decision() -> None:
    result = ProcurementDecisionEngine().evaluate(
        build_case(readiness=BuyerReadiness.QUALIFIED),
        context=ready_context(),
    )

    assert result.decision is ProcurementDecision.HOLD
    assert any(
        finding.code == "BUYER_NOT_COMMITTED"
        for finding in result.findings
    )


def test_unqualified_supplier_rejects() -> None:
    context = replace(
        ready_context(),
        supplier_qualified=False,
    )

    result = ProcurementDecisionEngine().evaluate(
        build_case(),
        context=context,
    )

    assert result.decision is ProcurementDecision.REJECT
    assert any(
        finding.code == "SUPPLIER_NOT_QUALIFIED"
        for finding in result.blocking_findings
    )


def test_missing_selected_quotation_holds() -> None:
    result = ProcurementDecisionEngine().evaluate(
        build_case(selected=False),
        context=ready_context(),
    )

    assert result.decision is ProcurementDecision.HOLD
    assert any(
        finding.category is DecisionCategory.QUOTATION
        for finding in result.findings
    )


def test_non_compliant_quotation_rejects() -> None:
    result = ProcurementDecisionEngine().evaluate(
        build_case(
            compliance=QuotationCompliance.NON_COMPLIANT
        ),
        context=ready_context(),
    )

    assert result.decision is ProcurementDecision.REJECT


def test_landed_cost_over_budget_holds() -> None:
    context = replace(
        ready_context(),
        landed_cost_budget_ratio=1.20,
    )

    result = ProcurementDecisionEngine().evaluate(
        build_case(),
        context=context,
    )

    assert result.decision is ProcurementDecision.HOLD
    assert any(
        finding.code == "LANDED_COST_EXCEEDS_BUDGET"
        for finding in result.findings
    )


def test_missing_approval_holds() -> None:
    context = replace(
        ready_context(),
        approval_satisfied=False,
    )

    result = ProcurementDecisionEngine().evaluate(
        build_case(),
        context=context,
    )

    assert result.decision is ProcurementDecision.HOLD


def test_uncleared_payment_rejects() -> None:
    context = replace(
        ready_context(),
        buyer_payment_cleared=False,
    )

    result = ProcurementDecisionEngine().evaluate(
        build_case(),
        context=context,
    )

    assert result.decision is ProcurementDecision.REJECT
    assert any(
        finding.code == "BUYER_PAYMENT_NOT_CLEARED"
        for finding in result.findings
    )


def test_incomplete_documents_hold() -> None:
    context = replace(
        ready_context(),
        documents_complete=False,
    )

    result = ProcurementDecisionEngine().evaluate(
        build_case(),
        context=context,
    )

    assert result.decision is ProcurementDecision.HOLD


def test_high_supplier_risk_holds() -> None:
    context = replace(
        ready_context(),
        supplier_risk_score=80,
    )

    result = ProcurementDecisionEngine().evaluate(
        build_case(),
        context=context,
    )

    assert result.decision is ProcurementDecision.HOLD


def test_shipment_readiness_can_be_required() -> None:
    policy = ProcurementDecisionPolicy(
        policy_id="shipment-ready",
        name="Shipment Ready",
        require_shipment_readiness=True,
    )
    context = replace(
        ready_context(),
        shipment_ready=False,
    )

    result = ProcurementDecisionEngine(policy).evaluate(
        build_case(),
        context=context,
    )

    assert result.decision is ProcurementDecision.HOLD
    assert any(
        finding.code == "SHIPMENT_NOT_READY"
        for finding in result.findings
    )


def test_disabled_policy_rejects() -> None:
    policy = ProcurementDecisionPolicy(
        policy_id="disabled",
        name="Disabled",
        enabled=False,
    )

    result = ProcurementDecisionEngine(policy).evaluate(
        build_case(),
        context=ready_context(),
    )

    assert result.decision is ProcurementDecision.REJECT


def test_result_serialises_safely() -> None:
    result = ProcurementDecisionEngine().evaluate(
        build_case(),
        context=ready_context(),
    )

    payload = result.as_dict()

    assert payload["decision"] == "proceed"
    assert payload["can_proceed"] is True
    assert payload["policy_id"]