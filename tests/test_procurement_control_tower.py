"""Procurement Control Tower tests."""

from __future__ import annotations

from views.procurement_control_tower import ProcurementControlRecord, _money, _priority, build_control_snapshot


def _record(**overrides: object) -> ProcurementControlRecord:
    values: dict[str, object] = {
        "case_id": "CASE-1", "reference": "RFQ-001", "buyer_name": "Buyer",
        "supplier_name": "Supplier", "product_name": "Rice", "stage": "Quotation",
        "owner": "Procurement", "value": 100_000.0, "age_days": 4, "sla_days": 7,
        "buyer_commitment_confirmed": True, "supplier_response_received": True,
        "documents_complete": True, "approval_required": False,
        "approval_status": "Not Required", "next_action": "Continue monitoring.",
        "risk_score": 20, "ai_confidence": 90, "blockers": (), "warnings": (),
    }
    values.update(overrides)
    return ProcurementControlRecord(**values)


def test_procurement_snapshot_counts_all_control_failures() -> None:
    critical = _record(
        case_id="CRITICAL", reference="RFQ-CRITICAL", age_days=12, sla_days=5,
        buyer_commitment_confirmed=False, supplier_response_received=False,
        documents_complete=False, approval_required=True, approval_status="Pending",
        risk_score=90, blockers=("Compliance approval missing.",),
    )
    snapshot = build_control_snapshot((critical, _record(case_id="SAFE")))
    assert snapshot.total_cases == 2
    assert snapshot.total_pipeline_value == 200_000
    assert snapshot.overdue_cases == 1
    assert snapshot.blocked_cases == 1
    assert snapshot.pending_approvals == 1
    assert snapshot.missing_documents == 1
    assert snapshot.awaiting_supplier_response == 1
    assert snapshot.buyer_commitment_gaps == 1
    assert snapshot.records[0].case_id == "CRITICAL"


def test_procurement_priority_is_deterministic() -> None:
    assert _priority(_record(blockers=("Blocked",))) == "Critical"
    assert _priority(_record(risk_score=80)) == "Critical"
    assert _priority(_record(age_days=9, sla_days=7)) == "High"
    assert _priority(_record()) == "Moderate"


def test_procurement_empty_snapshot_is_safe() -> None:
    snapshot = build_control_snapshot(())
    assert snapshot.total_cases == 0
    assert snapshot.average_age_days == 0
    assert snapshot.stage_counts == {}
    assert _money(5000) == "$5,000.00"