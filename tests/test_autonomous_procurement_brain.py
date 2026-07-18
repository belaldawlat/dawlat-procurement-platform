"""Tests for the Autonomous Procurement Brain."""

from __future__ import annotations

from services.autonomous_intelligence.approval_policy_engine import (
    ActionType,
    ApprovalDecision,
    ApprovalRequest,
    get_approval_policy_engine,
)
from services.autonomous_intelligence.autonomous_learning_engine import (
    AutonomousOutcome,
    get_autonomous_learning_engine,
)
from services.autonomous_intelligence.landed_cost_forecasting_engine import (
    LandedCostScenario,
    get_landed_cost_forecasting_engine,
)


def test_payment_release_is_denied_without_cleared_funds() -> None:
    request = ApprovalRequest(
        request_id="APR-001",
        action_type=ActionType.RELEASE_PAYMENT,
        actor_role="Finance Approver",
        case_id="CASE-001",
        buyer_verified=True,
        supplier_verified=True,
        compliance_cleared=True,
        buyer_final_approval=True,
        funds_cleared=False,
        documents_verified=True,
        contract_ready=True,
        margin_protected=True,
        authorised_human_approval=True,
        risk_score=20,
        trust_score=90,
    )

    result = get_approval_policy_engine().evaluate(
        request
    )

    assert result.decision == ApprovalDecision.DENY
    assert result.allowed is False


def test_landed_cost_forecast_uses_weighted_scenarios() -> None:
    scenarios = (
        LandedCostScenario(
            scenario_name="Base",
            product_cost=10000,
            freight_cost=2000,
            insurance_cost=100,
            customs_cost=500,
            port_charges=300,
            biosecurity_cost=200,
            handling_cost=150,
            trucking_cost=250,
            warehouse_cost=100,
            other_cost=0,
            exchange_rate=1.0,
            quantity=10,
            contingency_percent=5,
            probability=0.7,
        ),
        LandedCostScenario(
            scenario_name="Stress",
            product_cost=10000,
            freight_cost=3000,
            insurance_cost=150,
            customs_cost=600,
            port_charges=400,
            biosecurity_cost=250,
            handling_cost=200,
            trucking_cost=300,
            warehouse_cost=150,
            other_cost=100,
            exchange_rate=1.0,
            quantity=10,
            contingency_percent=10,
            probability=0.3,
        ),
    )

    result = get_landed_cost_forecasting_engine().forecast(
        scenarios
    )

    assert result.scenarios_evaluated == 2
    assert result.expected_total_cost > result.minimum_total_cost
    assert result.expected_total_cost < result.maximum_total_cost


def test_learning_adjustments_are_bounded() -> None:
    outcome = AutonomousOutcome(
        case_id="CASE-001",
        opportunity_id="OPP-001",
        supplier_id="SUP-001",
        buyer_id="BUY-001",
        product_name="ST25 Rice",
        route_id="VN-AU",
        predicted_success_probability=0.80,
        predicted_margin_percent=20,
        realised_margin_percent=22,
        predicted_landed_cost=14000,
        realised_landed_cost=13800,
        predicted_transit_days=25,
        actual_transit_days=24,
        buyer_paid_on_time=True,
        supplier_delivered_on_time=True,
        quality_accepted=True,
        disruption_occurred=False,
        dispute_occurred=False,
        completed=True,
    )

    report = get_autonomous_learning_engine().learn(
        [outcome]
    )

    assert report.outcomes_processed == 1
    assert all(
        -12.0 <= item.adjustment <= 12.0
        for item in report.adjustments
    )