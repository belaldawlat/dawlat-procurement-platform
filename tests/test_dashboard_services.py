"""Package B command-service regression tests."""

from __future__ import annotations

from datetime import date, timedelta

from services.dashboard_intelligence.opportunity_command_service import OpportunityCommandInput, OpportunityCommandService, OpportunityReadiness
from services.dashboard_intelligence.shipment_command_service import ShipmentCommandInput, ShipmentCommandService, ShipmentCommandStatus
from services.dashboard_intelligence.supplier_portfolio_service import SupplierPortfolioInput, SupplierPortfolioService, SupplierPortfolioTier


def test_supplier_portfolio_blocks_noncompliant_supplier() -> None:
    snapshot = SupplierPortfolioService().build((
        SupplierPortfolioInput(
            supplier_id="SUP-1", supplier_name="Blocked Supplier", country="Pakistan",
            category="Rice", annual_spend=100_000, quality_score=95, delivery_score=95,
            price_score=95, responsiveness_score=95, compliance_score=95, capacity_score=95,
            dispute_count=0, documents_complete=False, sanctions_clear=False,
            approved=True, active=True, backup_supplier_count=0,
        ),
    ))
    record = snapshot.records[0]
    assert record.tier == SupplierPortfolioTier.BLOCKED
    assert snapshot.blocked_suppliers == 1
    assert record.warnings


def test_shipment_service_blocks_missing_documents() -> None:
    today = date.today()
    snapshot = ShipmentCommandService().build((
        ShipmentCommandInput(
            shipment_id="SHIP-1", reference="SHP-1", supplier_name="Supplier",
            customer_name="Buyer", product_name="Rice", origin_port="Karachi",
            destination_port="Melbourne", status="Customs Clearance",
            etd=str(today - timedelta(days=20)), eta=str(today + timedelta(days=2)),
            atd=str(today - timedelta(days=18)), ata=None, shipment_value=100_000,
            expected_landed_cost=80_000, actual_landed_cost=None,
            documents_complete=False, customs_clearance_complete=False,
            tracking_stale_hours=30, delay_reason=None, owner="Logistics",
        ),
    ))
    record = snapshot.records[0]
    assert record.command_status == ShipmentCommandStatus.BLOCKED
    assert snapshot.blocked_shipments == 1
    assert "Complete missing documents" in record.next_action


def test_opportunity_service_marks_unfunded_execution_conditional() -> None:
    snapshot = OpportunityCommandService().build((
        OpportunityCommandInput(
            opportunity_id="OPP-1", title="Rice Opportunity", buyer_name="Buyer",
            product_name="Rice", country="Australia", expected_revenue=100_000,
            expected_landed_cost=75_000, verified_demand_score=90,
            buyer_readiness_score=90, supplier_availability_score=90,
            logistics_feasibility_score=90, strategic_fit_score=90,
            competition_score=20, confidence_score=90, risk_score=20,
            execution_readiness_score=90, buyer_funds_cleared=False,
            supplier_qualified=True, compliance_cleared=True,
        ),
    ))
    record = snapshot.records[0]
    assert record.readiness == OpportunityReadiness.CONDITIONAL
    assert snapshot.conditional_opportunities == 1
    assert any("fund" in warning.lower() for warning in record.warnings)


def test_service_outputs_are_deterministically_sorted() -> None:
    common = dict(
        country="Pakistan", category="Rice", annual_spend=100, quality_score=80,
        delivery_score=80, price_score=80, responsiveness_score=80,
        compliance_score=80, capacity_score=80, dispute_count=0,
        documents_complete=True, sanctions_clear=True, approved=True, active=True,
        backup_supplier_count=1,
    )
    snapshot = SupplierPortfolioService().build((
        SupplierPortfolioInput(supplier_id="B", supplier_name="B Supplier", **common),
        SupplierPortfolioInput(supplier_id="A", supplier_name="A Supplier", **common),
    ))
    assert [record.supplier_name for record in snapshot.records] == ["A Supplier", "B Supplier"]