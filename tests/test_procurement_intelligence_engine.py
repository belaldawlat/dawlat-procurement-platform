"""Tests for Phase 21 Package H procurement intelligence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestration import (
    IntelligencePriority,
    ProcurementIntelligenceContext,
    ProcurementIntelligenceEngine,
    ProcurementIntelligencePolicy,
    RecommendationType,
    SupplierIntelligenceInput,
)


def supplier(
    supplier_id: str,
    landed_cost: float,
    *,
    quality: float = 90,
    reliability: float = 90,
    compliance: float = 95,
    risk: float = 20,
    lead_time: int = 30,
) -> SupplierIntelligenceInput:
    return SupplierIntelligenceInput(
        supplier_id=supplier_id,
        supplier_name=f"Supplier {supplier_id}",
        quotation_id=f"Q-{supplier_id}",
        landed_cost=landed_cost,
        quality_score=quality,
        reliability_score=reliability,
        compliance_score=compliance,
        risk_score=risk,
        lead_time_days=lead_time,
        currency="AUD",
    )


def ready_context() -> ProcurementIntelligenceContext:
    return ProcurementIntelligenceContext(
        buyer_priority_score=60,
        buyer_payment_cleared=True,
        documents_complete=True,
        shipment_delay_days=0,
        inventory_days_remaining=60,
        opportunity_score=50,
        margin_percentage=15,
    )


def test_policy_requires_weights_total_one() -> None:
    with pytest.raises(ValueError):
        ProcurementIntelligencePolicy(
            policy_id="invalid",
            name="Invalid",
            landed_cost_weight=0.50,
        )


def test_engine_ranks_best_value_supplier_first() -> None:
    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (
            supplier("A", 100, quality=95),
            supplier("B", 120, quality=80),
        ),
        context=ready_context(),
    )

    assert result.best_supplier is not None
    assert result.best_supplier.supplier_id == "A"
    assert result.rankings[0].rank == 1


def test_engine_generates_supplier_selection() -> None:
    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100),),
        context=ready_context(),
    )

    assert any(
        item.recommendation_type
        is RecommendationType.SELECT_SUPPLIER
        for item in result.recommendations
    )


def test_critical_supplier_risk_escalates() -> None:
    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100, risk=90),),
        context=ready_context(),
    )

    first = result.recommendations[0]
    assert (
        first.recommendation_type
        is RecommendationType.ESCALATE_RISK
    )
    assert first.priority is IntelligencePriority.CRITICAL


def test_uncleared_payment_is_critical() -> None:
    context = replace(
        ready_context(),
        buyer_payment_cleared=False,
    )

    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100),),
        context=context,
    )

    assert any(
        item.recommendation_type
        is RecommendationType.SECURE_PAYMENT
        for item in result.urgent_recommendations
    )


def test_incomplete_documents_are_flagged() -> None:
    context = replace(
        ready_context(),
        documents_complete=False,
    )

    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100),),
        context=context,
    )

    assert any(
        item.recommendation_type
        is RecommendationType.COMPLETE_DOCUMENTS
        for item in result.recommendations
    )


def test_delayed_shipment_is_escalated() -> None:
    context = replace(
        ready_context(),
        shipment_delay_days=10,
    )

    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100),),
        context=context,
    )

    assert any(
        item.recommendation_type
        is RecommendationType.EXPEDITE_SHIPMENT
        for item in result.recommendations
    )


def test_low_inventory_triggers_replenishment() -> None:
    context = replace(
        ready_context(),
        inventory_days_remaining=10,
    )

    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100),),
        context=context,
    )

    assert any(
        item.recommendation_type
        is RecommendationType.REPLENISH_INVENTORY
        for item in result.recommendations
    )


def test_high_opportunity_is_prioritised() -> None:
    context = replace(
        ready_context(),
        opportunity_score=90,
        margin_percentage=20,
    )

    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100),),
        context=context,
    )

    assert any(
        item.recommendation_type
        is RecommendationType.PURSUE_OPPORTUNITY
        for item in result.recommendations
    )


def test_low_margin_blocks_opportunity_recommendation() -> None:
    context = replace(
        ready_context(),
        opportunity_score=90,
        margin_percentage=5,
    )

    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100),),
        context=context,
    )

    assert not any(
        item.recommendation_type
        is RecommendationType.PURSUE_OPPORTUNITY
        for item in result.recommendations
    )


def test_strategic_buyer_is_prioritised() -> None:
    context = replace(
        ready_context(),
        buyer_priority_score=90,
    )

    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100),),
        context=context,
    )

    assert any(
        item.recommendation_type
        is RecommendationType.PRIORITISE_BUYER
        for item in result.recommendations
    )


def test_empty_supplier_list_still_returns_actions() -> None:
    context = replace(
        ready_context(),
        buyer_payment_cleared=False,
    )

    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (),
        context=context,
    )

    assert result.rankings == ()
    assert result.recommendations


def test_result_serialises() -> None:
    result = ProcurementIntelligenceEngine().evaluate(
        "CASE-100",
        (supplier("A", 100),),
        context=ready_context(),
    )

    payload = result.as_dict()

    assert payload["case_id"] == "CASE-100"
    assert payload["best_supplier"]["supplier_id"] == "A"
    assert payload["recommendations"]


def test_disabled_policy_rejects_execution() -> None:
    engine = ProcurementIntelligenceEngine(
        ProcurementIntelligencePolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        engine.evaluate(
            "CASE-100",
            (supplier("A", 100),),
        )