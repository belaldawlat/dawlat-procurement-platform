"""Executive command-center orchestration tests."""

from __future__ import annotations

from datetime import date, timedelta

from services.dashboard_intelligence.command_center_service import CommandCenterRequest, CommandCenterService
from services.dashboard_intelligence.dashboard_health_service import DashboardDependencyStatus
from services.dashboard_intelligence.executive_kpi_engine import ExecutiveKPIInput
from services.dashboard_intelligence.financial_exposure_service import FinancialExposureItem
from services.dashboard_intelligence.pipeline_intelligence_service import PipelineCase
from services.dashboard_intelligence.risk_command_service import RiskCommandItem
from views.executive_command_center import _money, _serialisable_snapshot


def _healthy_dependency() -> DashboardDependencyStatus:
    return DashboardDependencyStatus(
        name="Primary Database",
        category="Database",
        available=True,
        latency_ms=20,
        error_count=0,
        stale_minutes=0,
        critical=True,
    )


def test_command_center_allows_safe_execution() -> None:
    snapshot = CommandCenterService().build(
        CommandCenterRequest(
            kpi_inputs=(
                ExecutiveKPIInput(
                    pipeline_value=100_000,
                    expected_revenue=100_000,
                    expected_landed_cost=75_000,
                    cleared_buyer_funds=80_000,
                    committed_supplier_payments=70_000,
                    blocked_procurement_value=0,
                    active_opportunities=1,
                    blocked_cases=0,
                    completed_cases=1,
                    critical_risks=0,
                    ai_confidence_scores=(90,),
                    service_health_scores=(95,),
                ),
            ),
            dependencies=(_healthy_dependency(),),
        )
    )
    assert snapshot.transaction_execution_allowed is True
    assert snapshot.executive_attention_required is False
    assert snapshot.actions == ()


def test_command_center_blocks_unsafe_execution_and_builds_actions() -> None:
    today = date.today()
    snapshot = CommandCenterService().build(
        CommandCenterRequest(
            financial_items=(
                FinancialExposureItem(
                    case_id="CASE-1",
                    cleared_buyer_funds=1_000,
                    supplier_obligation=10_000,
                    protected_profit=500,
                    expected_landed_cost=9_000,
                    expected_revenue=10_000,
                    fx_exposure=0,
                    receivable_amount=0,
                    overdue_receivable_amount=0,
                    authorised_exposure_limit=2_000,
                ),
            ),
            risk_items=(
                RiskCommandItem(
                    case_id="CASE-1",
                    category="Compliance",
                    title="Blocked supplier",
                    probability=1.0,
                    impact_score=100,
                    confidence_score=100,
                    blocking=True,
                    evidence=("Supplier block confirmed",),
                ),
            ),
            pipeline_cases=(
                PipelineCase(
                    case_id="CASE-1",
                    stage="Approval",
                    value=10_000,
                    owner="Procurement",
                    created_at=str(today - timedelta(days=10)),
                    updated_at=str(today - timedelta(days=5)),
                    deadline_date=str(today - timedelta(days=1)),
                    approval_pending=True,
                    quotation_expired=False,
                    documents_complete=False,
                    landed_cost_validated=False,
                    blocked=True,
                ),
            ),
            dependencies=(_healthy_dependency(),),
        )
    )
    categories = {action.category for action in snapshot.actions}
    assert snapshot.transaction_execution_allowed is False
    assert snapshot.executive_attention_required is True
    assert {"Risk", "Finance", "Pipeline"}.issubset(categories)


def test_executive_view_helpers_are_stable() -> None:
    assert _money(1234.5) == "$1,234.50"
    snapshot = CommandCenterService().build(
        CommandCenterRequest(dependencies=(_healthy_dependency(),))
    )
    payload = _serialisable_snapshot(snapshot)
    assert isinstance(payload, dict)
    assert "kpis" in payload
    assert "platform_health" in payload