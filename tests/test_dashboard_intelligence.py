"""Core tests for Package A dashboard intelligence services."""

from __future__ import annotations

from datetime import date, timedelta

from services.dashboard_intelligence.dashboard_health_service import (
    DashboardDependencyStatus,
    DashboardHealthLevel,
    DashboardHealthService,
)
from services.dashboard_intelligence.executive_kpi_engine import (
    ExecutiveKPIEngine,
    ExecutiveKPIInput,
)
from services.dashboard_intelligence.financial_exposure_service import (
    ExposureLevel,
    FinancialExposureItem,
    FinancialExposureService,
)
from services.dashboard_intelligence.pipeline_intelligence_service import (
    PipelineCase,
    PipelineIntelligenceService,
    PipelineStatus,
)
from services.dashboard_intelligence.risk_command_service import (
    EnterpriseRiskLevel,
    RiskCommandItem,
    RiskCommandService,
)


def test_executive_kpi_engine_protects_margin_and_capital() -> None:
    snapshot = ExecutiveKPIEngine().calculate(
        ExecutiveKPIInput(
            pipeline_value=500_000,
            expected_revenue=200_000,
            expected_landed_cost=150_000,
            cleared_buyer_funds=120_000,
            committed_supplier_payments=100_000,
            blocked_procurement_value=20_000,
            active_opportunities=4,
            blocked_cases=1,
            completed_cases=5,
            critical_risks=0,
            ai_confidence_scores=(80, 90, 100),
            service_health_scores=(90, 80),
        )
    )
    assert snapshot.protected_gross_profit == 50_000
    assert snapshot.protected_margin_percent == 25
    assert snapshot.capital_at_risk == 0
    assert snapshot.ai_confidence_index == 90
    assert snapshot.enterprise_health_score == 85
    assert snapshot.completion_rate_percent == 50


def test_executive_kpi_engine_flags_unprotected_capital() -> None:
    snapshot = ExecutiveKPIEngine().calculate(
        ExecutiveKPIInput(
            pipeline_value=1,
            expected_revenue=100,
            expected_landed_cost=95,
            cleared_buyer_funds=20,
            committed_supplier_payments=80,
            blocked_procurement_value=0,
            active_opportunities=1,
            blocked_cases=0,
            completed_cases=0,
            critical_risks=1,
            service_health_scores=(50,),
        )
    )
    assert snapshot.capital_at_risk == 60
    assert snapshot.protected_margin_percent == 5
    assert len(snapshot.warnings) >= 3


def test_financial_exposure_service_blocks_unfunded_case() -> None:
    snapshot = FinancialExposureService().calculate(
        (
            FinancialExposureItem(
                case_id="CASE-1",
                cleared_buyer_funds=20_000,
                supplier_obligation=50_000,
                protected_profit=10_000,
                expected_landed_cost=60_000,
                expected_revenue=80_000,
                fx_exposure=5_000,
                receivable_amount=10_000,
                overdue_receivable_amount=2_000,
                authorised_exposure_limit=25_000,
            ),
        )
    )
    assert snapshot.unprotected_exposure == 30_000
    assert snapshot.blocked_case_ids == ("CASE-1",)
    assert snapshot.exposure_level in {ExposureLevel.HIGH, ExposureLevel.CRITICAL}


def test_pipeline_service_prioritises_blocked_and_overdue_cases() -> None:
    today = date.today()
    snapshot = PipelineIntelligenceService().snapshot(
        (
            PipelineCase(
                case_id="BLOCKED",
                stage="Quotation",
                value=10_000,
                owner="Procurement",
                created_at=str(today - timedelta(days=10)),
                updated_at=str(today - timedelta(days=4)),
                deadline_date=str(today + timedelta(days=3)),
                approval_pending=False,
                quotation_expired=False,
                documents_complete=False,
                landed_cost_validated=False,
                blocked=True,
            ),
            PipelineCase(
                case_id="OVERDUE",
                stage="RFQ",
                value=20_000,
                owner="Procurement",
                created_at=str(today - timedelta(days=20)),
                updated_at=str(today - timedelta(days=8)),
                deadline_date=str(today - timedelta(days=1)),
                approval_pending=True,
                quotation_expired=False,
                documents_complete=True,
                landed_cost_validated=True,
                blocked=False,
            ),
        )
    )
    statuses = {case.case_id: case.status for case in snapshot.cases}
    assert statuses["BLOCKED"] == PipelineStatus.BLOCKED
    assert statuses["OVERDUE"] == PipelineStatus.OVERDUE
    assert snapshot.blocked_cases == 1
    assert snapshot.overdue_cases == 1


def test_risk_service_blocks_execution_for_blocking_risk() -> None:
    snapshot = RiskCommandService().evaluate(
        (
            RiskCommandItem(
                case_id="CASE-RISK",
                category="Compliance",
                title="Sanctions screening incomplete",
                probability=0.9,
                impact_score=95,
                confidence_score=90,
                blocking=True,
                evidence=("Screening pending",),
            ),
        )
    )
    assert snapshot.execution_allowed is False
    assert snapshot.blocking_case_ids == ("CASE-RISK",)
    assert snapshot.risk_level in {EnterpriseRiskLevel.HIGH, EnterpriseRiskLevel.CRITICAL}


def test_health_service_prevents_rendering_on_critical_dependency_failure() -> None:
    snapshot = DashboardHealthService().evaluate(
        (
            DashboardDependencyStatus(
                name="Primary Database",
                category="Database",
                available=False,
                latency_ms=0,
                error_count=1,
                stale_minutes=0,
                critical=True,
            ),
        )
    )
    assert snapshot.level == DashboardHealthLevel.CRITICAL
    assert snapshot.dashboard_rendering_allowed is False
    assert snapshot.critical_failures


def test_empty_inputs_are_safe_and_deterministic() -> None:
    assert ExecutiveKPIEngine().portfolio_snapshot(()).procurement_pipeline_value == 0
    assert FinancialExposureService().calculate(()).expected_revenue == 0
    assert RiskCommandService().evaluate(()).critical_risk_count == 0
    assert PipelineIntelligenceService().snapshot(()).total_cases == 0
    assert DashboardHealthService().evaluate(()).dashboard_rendering_allowed is False