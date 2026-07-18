"""Highest-level enterprise AI orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.autonomous_intelligence.autonomous_decision_engine import (
    DecisionInput,
    DecisionResult,
    get_autonomous_decision_engine,
)
from services.autonomous_intelligence.executive_intelligence_engine import (
    ExecutiveSnapshot,
    get_executive_intelligence_engine,
)
from services.autonomous_intelligence.global_event_engine import (
    GlobalEvent,
    GlobalEventImpact,
    get_global_event_engine,
)
from services.autonomous_intelligence.risk_correlation_engine import (
    RiskCorrelationReport,
    RiskFactor,
    get_risk_correlation_engine,
)


@dataclass(frozen=True)
class EnterpriseOrchestrationInput:
    case_id: str
    decision_input: DecisionInput
    risk_factors: tuple[RiskFactor, ...]
    global_events: tuple[GlobalEvent, ...]
    opportunities: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    margin_leakage_amount: float
    supplier_concentration_percent: float
    cash_exposure_amount: float
    growth_forecast_percent: float
    procurement_kpis: dict[str, Any]


@dataclass(frozen=True)
class EnterpriseOrchestrationResult:
    case_id: str
    decision: DecisionResult
    risk_report: RiskCorrelationReport
    event_impacts: tuple[GlobalEventImpact, ...]
    executive_snapshot: ExecutiveSnapshot
    execution_allowed: bool
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class EnterpriseAIOrchestrator:
    def __init__(self) -> None:
        self._decision = get_autonomous_decision_engine()
        self._risk = get_risk_correlation_engine()
        self._events = get_global_event_engine()
        self._executive = get_executive_intelligence_engine()

    def orchestrate(
        self,
        item: EnterpriseOrchestrationInput,
    ) -> EnterpriseOrchestrationResult:
        risk_report = self._risk.analyse(
            item.risk_factors
        )
        event_impacts = tuple(
            self._events.evaluate(event)
            for event in item.global_events
        )
        decision = self._decision.decide(
            item.decision_input
        )
        snapshot = self._executive.generate(
            opportunities=item.opportunities,
            risks=item.risks,
            margin_leakage_amount=(
                item.margin_leakage_amount
            ),
            supplier_concentration_percent=(
                item.supplier_concentration_percent
            ),
            cash_exposure_amount=(
                item.cash_exposure_amount
            ),
            growth_forecast_percent=(
                item.growth_forecast_percent
            ),
            procurement_kpis=item.procurement_kpis,
        )

        execution_allowed = bool(
            decision.execution_allowed
            and risk_report.execution_allowed
            and not any(
                impact.blocking
                for impact in event_impacts
            )
        )

        return EnterpriseOrchestrationResult(
            case_id=item.case_id,
            decision=decision,
            risk_report=risk_report,
            event_impacts=event_impacts,
            executive_snapshot=snapshot,
            execution_allowed=execution_allowed,
            explanation=(
                f"Enterprise orchestration completed for {item.case_id}. "
                f"Execution is "
                f"{'allowed' if execution_allowed else 'not allowed'}."
            ),
        )


_orchestrator = EnterpriseAIOrchestrator()


def get_enterprise_ai_orchestrator() -> EnterpriseAIOrchestrator:
    return _orchestrator