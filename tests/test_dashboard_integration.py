"""Cross-package enterprise integration tests for Phase 19."""

from __future__ import annotations

from datetime import date, timedelta

from services.dashboard_intelligence.command_center_service import CommandCenterRequest, CommandCenterService
from services.dashboard_intelligence.dashboard_health_service import DashboardDependencyStatus
from services.dashboard_intelligence.executive_kpi_engine import ExecutiveKPIInput
from services.dashboard_intelligence.financial_exposure_service import FinancialExposureItem
from services.dashboard_intelligence.opportunity_command_service import OpportunityCommandInput, OpportunityCommandService, OpportunityReadiness
from services.dashboard_intelligence.pipeline_intelligence_service import PipelineCase
from services.dashboard_intelligence.risk_command_service import RiskCommandItem
from services.dashboard_intelligence.shipment_command_service import ShipmentCommandInput, ShipmentCommandService, ShipmentCommandStatus
from services.dashboard_intelligence.supplier_portfolio_service import SupplierPortfolioInput, SupplierPortfolioService, SupplierPortfolioTier


def _healthy_dependency() -> DashboardDependencyStatus:
    return DashboardDependencyStatus(
        name="Primary Database", category="Database", available=True,
        latency_ms=15, error_count=0, stale_minutes=0, critical=True,
    )


def test_safe_buyer_funded_workflow_remains_executable() -> None:
    today = date.today()
    supplier = SupplierPortfolioService().build((
        SupplierPortfolioInput(
            supplier_id="SUP-1", supplier_name="Approved Supplier", country="Pakistan",
            category="Rice", annual_spend=100_000, quality_score=95, delivery_score=95,
            price_score=90, responsiveness_score=90, compliance_score=100, capacity_score=90,
            dispute_count=0, documents_complete=True, sanctions_clear=True,
            approved=True, active=True, backup_supplier_count=1,
        ),
    ))
    assert supplier.records[0].tier in {SupplierPortfolioTier.STRATEGIC, SupplierPortfolioTier.PREFERRED}

    opportunity = OpportunityCommandService().build((
        OpportunityCommandInput(
            opportunity_id="OPP-1", title="Funded Rice Order", buyer_name="Buyer",
            product_name="Rice", country="Australia", expected_revenue=120_000,
            expected_landed_cost=90_000, verified_demand_score=95,
            buyer_readiness_score=95, supplier_availability_score=95,
            logistics_feasibility_score=90, strategic_fit_score=95, competition_score=20,
            confidence_score=95, risk_score=10, execution_readiness_score=95,
            buyer_funds_cleared=True, supplier_qualified=True, compliance_cleared=True,
        ),
    ))
    assert opportunity.records[0].readiness == OpportunityReadiness.READY

    shipment = ShipmentCommandService().build((
        ShipmentCommandInput(
            shipment_id="SHIP-1", reference="SHP-1", supplier_name="Approved Supplier",
            customer_name="Buyer", product_name="Rice", origin_port="Karachi",
            destination_port="Melbourne", status="In Transit",
            etd=str(today - timedelta(days=10)), eta=str(today + timedelta(days=10)),
            atd=str(today - timedelta(days=8)), ata=None, shipment_value=120_000,
            expected_landed_cost=90_000, actual_landed_cost=None,
            documents_complete=True, customs_clearance_complete=True,
            tracking_stale_hours=2, delay_reason=None, owner="Logistics",
        ),
    ))
    assert shipment.records[0].command_status in {ShipmentCommandStatus.ON_TRACK, ShipmentCommandStatus.ATTENTION}

    executive = CommandCenterService().build(CommandCenterRequest(
        kpi_inputs=(ExecutiveKPIInput(
            pipeline_value=120_000, expected_revenue=120_000,
            expected_landed_cost=90_000, cleared_buyer_funds=100_000,
            committed_supplier_payments=90_000, blocked_procurement_value=0,
            active_opportunities=1, blocked_cases=0, completed_cases=0,
            critical_risks=0, ai_confidence_scores=(95,), service_health_scores=(98,),
        ),),
        financial_items=(FinancialExposureItem(
            case_id="OPP-1", cleared_buyer_funds=100_000, supplier_obligation=90_000,
            protected_profit=30_000, expected_landed_cost=90_000,
            expected_revenue=120_000, fx_exposure=0, receivable_amount=20_000,
            overdue_receivable_amount=0, authorised_exposure_limit=20_000,
        ),),
        pipeline_cases=(PipelineCase(
            case_id="OPP-1", stage="Shipment", value=120_000, owner="Procurement",
            created_at=str(today - timedelta(days=20)), updated_at=str(today),
            deadline_date=str(today + timedelta(days=30)), approval_pending=False,
            quotation_expired=False, documents_complete=True,
            landed_cost_validated=True, blocked=False,
        ),),
        dependencies=(_healthy_dependency(),),
    ))
    assert executive.transaction_execution_allowed is True
    assert executive.financial_exposure.unprotected_exposure == 0
    assert executive.risk_posture.execution_allowed is True


def test_risky_workflow_is_stopped_at_multiple_control_layers() -> None:
    today = date.today()
    opportunity = OpportunityCommandService().build((
        OpportunityCommandInput(
            opportunity_id="OPP-RISK", title="Unfunded Order", buyer_name="Buyer",
            product_name="Rice", country="Australia", expected_revenue=100_000,
            expected_landed_cost=95_000, verified_demand_score=60,
            buyer_readiness_score=40, supplier_availability_score=50,
            logistics_feasibility_score=50, strategic_fit_score=50, competition_score=80,
            confidence_score=50, risk_score=90, execution_readiness_score=40,
            buyer_funds_cleared=False, supplier_qualified=False, compliance_cleared=False,
        ),
    ))
    assert opportunity.records[0].readiness == OpportunityReadiness.BLOCKED

    executive = CommandCenterService().build(CommandCenterRequest(
        financial_items=(FinancialExposureItem(
            case_id="OPP-RISK", cleared_buyer_funds=0, supplier_obligation=95_000,
            protected_profit=5_000, expected_landed_cost=95_000, expected_revenue=100_000,
            fx_exposure=20_000, receivable_amount=100_000,
            overdue_receivable_amount=50_000, authorised_exposure_limit=10_000,
        ),),
        risk_items=(RiskCommandItem(
            case_id="OPP-RISK", category="Compliance",
            title="Supplier and compliance controls failed", probability=1.0,
            impact_score=100, confidence_score=100, blocking=True,
            evidence=("Supplier not qualified", "Compliance not cleared"),
        ),),
        pipeline_cases=(PipelineCase(
            case_id="OPP-RISK", stage="Supplier Award", value=100_000,
            owner="Procurement", created_at=str(today - timedelta(days=30)),
            updated_at=str(today - timedelta(days=10)),
            deadline_date=str(today - timedelta(days=2)), approval_pending=True,
            quotation_expired=True, documents_complete=False,
            landed_cost_validated=False, blocked=True,
        ),),
        dependencies=(_healthy_dependency(),),
    ))
    assert executive.transaction_execution_allowed is False
    assert executive.executive_attention_required is True
    assert executive.actions
    assert executive.financial_exposure.unprotected_exposure == 95_000
    assert executive.risk_posture.execution_allowed is False