"""Opportunity Command Center tests."""

from __future__ import annotations

from views.opportunity_command_center import (
    OpportunityCommandRecord,
    _money,
    _opportunity_priority,
    build_operations_snapshot,
)


def _record(**overrides: object) -> OpportunityCommandRecord:
    values: dict[str, object] = {
        "opportunity_id": "OPP-1", "title": "Premium Rice Opportunity",
        "buyer_name": "Buyer", "product_name": "Rice", "market": "Australia",
        "stage": "Qualified", "owner": "Commercial", "expected_revenue": 100_000.0,
        "expected_profit": 20_000.0, "probability_percent": 50.0,
        "buyer_readiness_score": 80, "payment_readiness_score": 80,
        "days_in_stage": 5, "stage_sla_days": 10, "approval_required": False,
        "approval_status": "Not Required", "lost_reason": None,
        "next_action": "Request final specifications.",
    }
    values.update(overrides)
    return OpportunityCommandRecord(**values)


def test_opportunity_snapshot_calculates_forecast_margin_and_win_rate() -> None:
    won = _record(opportunity_id="WON", stage="Won", expected_revenue=200_000, expected_profit=40_000, probability_percent=100)
    lost = _record(opportunity_id="LOST", stage="Lost", expected_revenue=100_000, expected_profit=10_000, probability_percent=0, lost_reason="Price")
    risky = _record(opportunity_id="RISKY", days_in_stage=20, stage_sla_days=10, buyer_readiness_score=30, payment_readiness_score=40, approval_required=True, approval_status="Pending")
    snapshot = build_operations_snapshot((won, lost, risky))
    assert snapshot.total_opportunities == 3
    assert snapshot.total_pipeline_revenue == 400_000
    assert snapshot.weighted_revenue_forecast == 250_000
    assert snapshot.total_expected_profit == 70_000
    assert snapshot.protected_margin_percent == 17.5
    assert snapshot.win_rate_percent == 50
    assert snapshot.lost_opportunities == 1
    assert snapshot.pending_approvals == 1
    assert snapshot.overdue_stage_cases == 1
    assert snapshot.records[0].opportunity_id == "RISKY"


def test_opportunity_priority_and_empty_state() -> None:
    assert _opportunity_priority(_record(buyer_readiness_score=20)) == "Critical"
    assert _opportunity_priority(_record(days_in_stage=20, stage_sla_days=10)) == "High"
    assert _opportunity_priority(_record()) == "Moderate"
    assert _money(100000) == "$100,000.00"
    empty = build_operations_snapshot(())
    assert empty.total_opportunities == 0
    assert empty.protected_margin_percent == 0