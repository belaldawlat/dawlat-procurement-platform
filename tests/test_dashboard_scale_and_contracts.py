"""Scale, immutability and public-contract regression tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from services.dashboard_intelligence.executive_kpi_engine import ExecutiveKPIEngine, ExecutiveKPIInput
from views.procurement_control_tower import ProcurementControlRecord, build_control_snapshot


def test_large_portfolio_aggregation_remains_exact() -> None:
    items = tuple(
        ExecutiveKPIInput(
            pipeline_value=1_000, expected_revenue=1_000, expected_landed_cost=800,
            cleared_buyer_funds=900, committed_supplier_payments=800,
            blocked_procurement_value=0, active_opportunities=1, blocked_cases=0,
            completed_cases=0, critical_risks=0, ai_confidence_scores=(90,),
            service_health_scores=(95,),
        )
        for _ in range(10_000)
    )
    snapshot = ExecutiveKPIEngine().portfolio_snapshot(items)
    assert snapshot.procurement_pipeline_value == 10_000_000
    assert snapshot.expected_revenue == 10_000_000
    assert snapshot.expected_landed_cost == 8_000_000
    assert snapshot.protected_gross_profit == 2_000_000
    assert snapshot.capital_at_risk == 0


def test_control_snapshot_handles_large_dataset_deterministically() -> None:
    records = tuple(
        ProcurementControlRecord(
            case_id=f"CASE-{index:05d}", reference=f"RFQ-{index:05d}",
            buyer_name="Buyer", supplier_name="Supplier", product_name="Rice",
            stage="Quotation", owner=f"Owner-{index % 5}", value=100,
            age_days=index % 20, sla_days=10,
            buyer_commitment_confirmed=index % 2 == 0,
            supplier_response_received=True, documents_complete=True,
            approval_required=False, approval_status="Not Required",
            next_action="Continue.", risk_score=index % 100,
            ai_confidence=90, blockers=(), warnings=(),
        )
        for index in range(5_000)
    )
    snapshot = build_control_snapshot(records)
    assert snapshot.total_cases == 5_000
    assert snapshot.total_pipeline_value == 500_000
    assert sum(snapshot.owner_workload.values()) == 5_000
    assert len(snapshot.records) == 5_000


def test_snapshot_dataclasses_are_immutable() -> None:
    snapshot = ExecutiveKPIEngine().portfolio_snapshot(())
    with pytest.raises(FrozenInstanceError):
        snapshot.expected_revenue = 123  # type: ignore[misc]