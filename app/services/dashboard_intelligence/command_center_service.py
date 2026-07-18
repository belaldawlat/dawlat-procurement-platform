"""Executive Command Center aggregation service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from services.dashboard_intelligence.dashboard_health_service import (
    DashboardDependencyStatus,
    DashboardHealthService,
    DashboardHealthSnapshot,
)
from services.dashboard_intelligence.executive_kpi_engine import (
    ExecutiveKPIEngine,
    ExecutiveKPIInput,
    ExecutiveKPISnapshot,
)
from services.dashboard_intelligence.financial_exposure_service import (
    FinancialExposureItem,
    FinancialExposureService,
    FinancialExposureSnapshot,
)
from services.dashboard_intelligence.pipeline_intelligence_service import (
    PipelineCase,
    PipelineIntelligenceService,
    PipelineSnapshot,
)
from services.dashboard_intelligence.risk_command_service import (
    RiskCommandItem,
    RiskCommandService,
    RiskCommandSnapshot,
)


@dataclass(frozen=True)
class ExecutiveAction:
    action_id: str
    title: str
    category: str
    priority: int
    owner: str
    case_id: str | None
    reason: str
    approval_required: bool
    route: str


@dataclass(frozen=True)
class CommandCenterRequest:
    kpi_inputs: tuple[ExecutiveKPIInput, ...] = ()
    financial_items: tuple[FinancialExposureItem, ...] = ()
    risk_items: tuple[RiskCommandItem, ...] = ()
    pipeline_cases: tuple[PipelineCase, ...] = ()
    dependencies: tuple[DashboardDependencyStatus, ...] = ()


@dataclass(frozen=True)
class ExecutiveCommandCenterSnapshot:
    kpis: ExecutiveKPISnapshot
    financial_exposure: FinancialExposureSnapshot
    risk_posture: RiskCommandSnapshot
    pipeline: PipelineSnapshot
    platform_health: DashboardHealthSnapshot
    actions: tuple[ExecutiveAction, ...]
    executive_attention_required: bool
    transaction_execution_allowed: bool
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class CommandCenterService:
    """Create one governed executive view across procurement intelligence."""

    def __init__(
        self,
        *,
        kpi_engine: ExecutiveKPIEngine | None = None,
        financial_service: FinancialExposureService | None = None,
        risk_service: RiskCommandService | None = None,
        pipeline_service: PipelineIntelligenceService | None = None,
        health_service: DashboardHealthService | None = None,
    ) -> None:
        self._kpi_engine = kpi_engine or ExecutiveKPIEngine()
        self._financial_service = (
            financial_service or FinancialExposureService()
        )
        self._risk_service = risk_service or RiskCommandService()
        self._pipeline_service = (
            pipeline_service or PipelineIntelligenceService()
        )
        self._health_service = health_service or DashboardHealthService()

    def build(
        self,
        request: CommandCenterRequest,
    ) -> ExecutiveCommandCenterSnapshot:
        kpis = self._kpi_engine.portfolio_snapshot(request.kpi_inputs)
        financial = self._financial_service.calculate(request.financial_items)
        risks = self._risk_service.evaluate(request.risk_items)
        pipeline = self._pipeline_service.snapshot(request.pipeline_cases)
        health = self._health_service.evaluate(request.dependencies)

        actions = self._build_actions(
            financial=financial,
            risks=risks,
            pipeline=pipeline,
            health=health,
        )

        executive_attention_required = any(
            (
                bool(actions),
                risks.critical_risk_count > 0,
                pipeline.overdue_cases > 0,
                financial.unprotected_exposure > 0,
                not health.dashboard_rendering_allowed,
            )
        )

        transaction_execution_allowed = all(
            (
                risks.execution_allowed,
                financial.unprotected_exposure == 0,
                health.dashboard_rendering_allowed,
                pipeline.blocked_cases == 0,
                pipeline.overdue_cases == 0,
            )
        )

        return ExecutiveCommandCenterSnapshot(
            kpis=kpis,
            financial_exposure=financial,
            risk_posture=risks,
            pipeline=pipeline,
            platform_health=health,
            actions=actions,
            executive_attention_required=executive_attention_required,
            transaction_execution_allowed=transaction_execution_allowed,
        )

    def _build_actions(
        self,
        *,
        financial: FinancialExposureSnapshot,
        risks: RiskCommandSnapshot,
        pipeline: PipelineSnapshot,
        health: DashboardHealthSnapshot,
    ) -> tuple[ExecutiveAction, ...]:
        actions: list[ExecutiveAction] = []

        for case_id in risks.blocking_case_ids:
            actions.append(
                ExecutiveAction(
                    action_id=f"risk:{case_id}",
                    title="Resolve blocking enterprise risk",
                    category="Risk",
                    priority=100,
                    owner="Risk & Compliance",
                    case_id=case_id,
                    reason="The case is blocked by enterprise risk controls.",
                    approval_required=True,
                    route="Approval Gateway",
                )
            )

        for case_id in financial.blocked_case_ids:
            actions.append(
                ExecutiveAction(
                    action_id=f"finance:{case_id}",
                    title="Protect buyer-funded payment position",
                    category="Finance",
                    priority=95,
                    owner="Finance",
                    case_id=case_id,
                    reason=(
                        "Supplier obligations exceed cleared buyer funds "
                        "for this case."
                    ),
                    approval_required=True,
                    route="Payment Protection Engine",
                )
            )

        for item in pipeline.cases:
            if item.status.value in {"Blocked", "Overdue"}:
                actions.append(
                    ExecutiveAction(
                        action_id=f"pipeline:{item.case_id}",
                        title=item.next_action,
                        category="Pipeline",
                        priority=90 if item.status.value == "Overdue" else 85,
                        owner="Procurement Operations",
                        case_id=item.case_id,
                        reason="; ".join(item.blockers or item.warnings),
                        approval_required=False,
                        route="Workflow Router",
                    )
                )

        for failure in health.critical_failures:
            actions.append(
                ExecutiveAction(
                    action_id=f"health:{len(actions) + 1}",
                    title="Restore critical platform dependency",
                    category="Platform",
                    priority=100,
                    owner="Platform Operations",
                    case_id=None,
                    reason=failure,
                    approval_required=False,
                    route="Incident Response",
                )
            )

        return tuple(
            sorted(
                actions,
                key=lambda item: (
                    -item.priority,
                    item.category,
                    item.action_id,
                ),
            )
        )


_service = CommandCenterService()


def get_command_center_service() -> CommandCenterService:
    return _service