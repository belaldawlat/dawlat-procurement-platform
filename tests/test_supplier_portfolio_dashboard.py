"""Supplier Portfolio Dashboard tests."""

from __future__ import annotations

from datetime import date, timedelta

from services.dashboard_intelligence.supplier_portfolio_service import SupplierPortfolioTier
from views.supplier_portfolio_dashboard import (
    SupplierPortfolioControlRecord,
    _expiring_certificate_count,
    _supplier_priority,
    build_control_snapshot,
)


def _record(**overrides: object) -> SupplierPortfolioControlRecord:
    values: dict[str, object] = {
        "supplier_id": "SUP-1", "supplier_name": "Supplier", "country": "Pakistan",
        "category": "Rice", "on_time_in_full_percent": 96.0,
        "quality_incident_count": 0, "open_corrective_actions": 0,
        "production_capacity_utilisation_percent": 70.0,
        "certificate_expiry_dates": (), "compliance_status": "Approved",
        "latest_audit_score": 90, "response_sla_hours": 24.0,
        "average_response_hours": 12.0, "active_orders": 2, "open_disputes": 0,
        "backup_supplier_count": 1, "owner": "Supplier Management",
    }
    values.update(overrides)
    return SupplierPortfolioControlRecord(**values)


def test_supplier_snapshot_detects_resilience_and_compliance_failures() -> None:
    expiry = str(date.today() + timedelta(days=10))
    risky = _record(
        supplier_id="SUP-RISK", on_time_in_full_percent=70,
        quality_incident_count=2, open_corrective_actions=3,
        production_capacity_utilisation_percent=96,
        certificate_expiry_dates=(expiry,), compliance_status="Restricted",
        open_disputes=1, backup_supplier_count=0,
    )
    snapshot = build_control_snapshot((risky, _record(supplier_id="SUP-SAFE")))
    assert snapshot.total_suppliers == 2
    assert snapshot.otif_below_target == 1
    assert snapshot.quality_attention == 1
    assert snapshot.certificate_expiry_alerts == 1
    assert snapshot.compliance_exceptions == 1
    assert snapshot.capacity_alerts == 1
    assert snapshot.open_corrective_actions == 3
    assert snapshot.open_disputes == 1
    assert snapshot.records[0].supplier_id == "SUP-RISK"


def test_supplier_certificate_and_priority_helpers() -> None:
    soon = str(date.today() + timedelta(days=30))
    later = str(date.today() + timedelta(days=365))
    assert _expiring_certificate_count((soon, later, "invalid")) == 1
    assert _supplier_priority(_record(), SupplierPortfolioTier.BLOCKED) == "Critical"
    assert _supplier_priority(_record(compliance_status="Restricted"), SupplierPortfolioTier.RESTRICTED) == "Critical"
    assert _supplier_priority(_record(on_time_in_full_percent=70), SupplierPortfolioTier.PREFERRED) == "High"


def test_supplier_empty_state_is_safe() -> None:
    snapshot = build_control_snapshot(())
    assert snapshot.total_suppliers == 0
    assert snapshot.records == ()