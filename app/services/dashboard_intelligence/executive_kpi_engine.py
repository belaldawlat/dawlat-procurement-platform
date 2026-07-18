"""Executive KPI Engine for enterprise procurement dashboards."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

@dataclass(frozen=True)
class ExecutiveKPIInput:
    pipeline_value: float
    expected_revenue: float
    expected_landed_cost: float
    cleared_buyer_funds: float
    committed_supplier_payments: float
    blocked_procurement_value: float
    active_opportunities: int
    blocked_cases: int
    completed_cases: int
    critical_risks: int
    ai_confidence_scores: tuple[int, ...] = ()
    service_health_scores: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ExecutiveKPISnapshot:
    procurement_pipeline_value: float
    expected_revenue: float
    expected_landed_cost: float
    protected_gross_profit: float
    protected_margin_percent: float
    cleared_buyer_funds: float
    capital_at_risk: float
    blocked_procurement_value: float
    active_opportunities: int
    blocked_cases: int
    completed_cases: int
    critical_risks: int
    ai_confidence_index: int
    enterprise_health_score: int
    completion_rate_percent: float
    warnings: tuple[str, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

class ExecutiveKPIEngine:
    def calculate(
        self,
        data: ExecutiveKPIInput,
    ) -> ExecutiveKPISnapshot:
        warnings: list[str] = []
        gross_profit = data.expected_revenue - data.expected_landed_cost
        margin = (
            gross_profit / data.expected_revenue * 100.0
            if data.expected_revenue > 0
            else 0.0
        )
        capital_at_risk = max(
            0.0,
            data.committed_supplier_payments - data.cleared_buyer_funds,
        )
        total_cases = (
            data.active_opportunities
            + data.blocked_cases
            + data.completed_cases
        )
        completion_rate = (
            data.completed_cases / total_cases * 100.0
            if total_cases > 0
            else 0.0
        )
        confidence = _average_score(data.ai_confidence_scores)
        health = _average_score(data.service_health_scores)

        if margin < 15:
            warnings.append("Protected margin is below the executive threshold.")
        if capital_at_risk > 0:
            warnings.append("Committed supplier payments exceed cleared buyer funds.")
        if data.critical_risks > 0:
            warnings.append("Critical enterprise risks require executive attention.")
        if health < 70:
            warnings.append("Enterprise platform health is below target.")

        return ExecutiveKPISnapshot(
            procurement_pipeline_value=round(data.pipeline_value, 2),
            expected_revenue=round(data.expected_revenue, 2),
            expected_landed_cost=round(data.expected_landed_cost, 2),
            protected_gross_profit=round(gross_profit, 2),
            protected_margin_percent=round(margin, 2),
            cleared_buyer_funds=round(data.cleared_buyer_funds, 2),
            capital_at_risk=round(capital_at_risk, 2),
            blocked_procurement_value=round(data.blocked_procurement_value, 2),
            active_opportunities=max(0, data.active_opportunities),
            blocked_cases=max(0, data.blocked_cases),
            completed_cases=max(0, data.completed_cases),
            critical_risks=max(0, data.critical_risks),
            ai_confidence_index=confidence,
            enterprise_health_score=health,
            completion_rate_percent=round(completion_rate, 2),
            warnings=tuple(warnings),
        )

    def portfolio_snapshot(
        self,
        inputs: Iterable[ExecutiveKPIInput],
    ) -> ExecutiveKPISnapshot:
        items = list(inputs)
        if not items:
            return self.calculate(
                ExecutiveKPIInput(
                    pipeline_value=0,
                    expected_revenue=0,
                    expected_landed_cost=0,
                    cleared_buyer_funds=0,
                    committed_supplier_payments=0,
                    blocked_procurement_value=0,
                    active_opportunities=0,
                    blocked_cases=0,
                    completed_cases=0,
                    critical_risks=0,
                )
            )
        return self.calculate(
            ExecutiveKPIInput(
                pipeline_value=sum(item.pipeline_value for item in items),
                expected_revenue=sum(item.expected_revenue for item in items),
                expected_landed_cost=sum(item.expected_landed_cost for item in items),
                cleared_buyer_funds=sum(item.cleared_buyer_funds for item in items),
                committed_supplier_payments=sum(
                    item.committed_supplier_payments for item in items
                ),
                blocked_procurement_value=sum(
                    item.blocked_procurement_value for item in items
                ),
                active_opportunities=sum(item.active_opportunities for item in items),
                blocked_cases=sum(item.blocked_cases for item in items),
                completed_cases=sum(item.completed_cases for item in items),
                critical_risks=sum(item.critical_risks for item in items),
                ai_confidence_scores=tuple(
                    score
                    for item in items
                    for score in item.ai_confidence_scores
                ),
                service_health_scores=tuple(
                    score
                    for item in items
                    for score in item.service_health_scores
                ),
            )
        )

def _average_score(values: tuple[int, ...]) -> int:
    if not values:
        return 0
    return max(
        0,
        min(
            100,
            round(
                sum(max(0, min(100, value)) for value in values)
                / len(values)
            ),
        ),
    )

_engine = ExecutiveKPIEngine()

def get_executive_kpi_engine() -> ExecutiveKPIEngine:
    return _engine