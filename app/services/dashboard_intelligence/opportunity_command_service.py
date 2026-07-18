"""Opportunity command-center ranking and execution readiness."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable


class OpportunityReadiness(str, Enum):
    READY = "Ready"
    CONDITIONAL = "Conditional"
    EARLY = "Early"
    BLOCKED = "Blocked"


@dataclass(frozen=True)
class OpportunityCommandInput:
    opportunity_id: str
    title: str
    buyer_name: str
    product_name: str
    country: str
    expected_revenue: float
    expected_landed_cost: float
    verified_demand_score: int
    buyer_readiness_score: int
    supplier_availability_score: int
    logistics_feasibility_score: int
    strategic_fit_score: int
    competition_score: int
    confidence_score: int
    risk_score: int
    execution_readiness_score: int
    buyer_funds_cleared: bool
    supplier_qualified: bool
    compliance_cleared: bool


@dataclass(frozen=True)
class OpportunityCommandRecord:
    opportunity_id: str
    title: str
    protected_profit: float
    protected_margin_percent: float
    priority_score: int
    readiness: OpportunityReadiness
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    recommended_action: str


@dataclass(frozen=True)
class OpportunityCommandSnapshot:
    total_opportunities: int
    ready_opportunities: int
    conditional_opportunities: int
    blocked_opportunities: int
    total_expected_revenue: float
    total_protected_profit: float
    weighted_pipeline_value: float
    records: tuple[OpportunityCommandRecord, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class OpportunityCommandService:
    """Rank commercial opportunities without bypassing governance controls."""

    def build(
        self,
        opportunities: Iterable[OpportunityCommandInput],
    ) -> OpportunityCommandSnapshot:
        items = list(opportunities)
        records = tuple(self._evaluate(item) for item in items)

        weighted_pipeline = sum(
            item.expected_revenue
            * record.priority_score
            / 100.0
            for item, record in zip(items, records)
        )

        return OpportunityCommandSnapshot(
            total_opportunities=len(items),
            ready_opportunities=sum(
                1
                for item in records
                if item.readiness == OpportunityReadiness.READY
            ),
            conditional_opportunities=sum(
                1
                for item in records
                if item.readiness == OpportunityReadiness.CONDITIONAL
            ),
            blocked_opportunities=sum(
                1
                for item in records
                if item.readiness == OpportunityReadiness.BLOCKED
            ),
            total_expected_revenue=round(
                sum(item.expected_revenue for item in items),
                2,
            ),
            total_protected_profit=round(
                sum(item.protected_profit for item in records),
                2,
            ),
            weighted_pipeline_value=round(weighted_pipeline, 2),
            records=tuple(
                sorted(
                    records,
                    key=lambda item: (
                        -item.priority_score,
                        -item.protected_profit,
                        item.title,
                    ),
                )
            ),
        )

    def _evaluate(
        self,
        item: OpportunityCommandInput,
    ) -> OpportunityCommandRecord:
        blockers: list[str] = []
        warnings: list[str] = []

        protected_profit = item.expected_revenue - item.expected_landed_cost
        margin_percent = (
            protected_profit / item.expected_revenue * 100.0
            if item.expected_revenue > 0
            else 0.0
        )

        score = round(
            item.verified_demand_score * 0.16
            + item.buyer_readiness_score * 0.16
            + item.supplier_availability_score * 0.12
            + item.logistics_feasibility_score * 0.10
            + item.strategic_fit_score * 0.10
            + (100 - item.competition_score) * 0.06
            + item.confidence_score * 0.10
            + (100 - item.risk_score) * 0.10
            + item.execution_readiness_score * 0.10
        )
        score = max(0, min(100, score))

        if not item.compliance_cleared:
            blockers.append("Compliance clearance is incomplete.")
        if not item.supplier_qualified:
            blockers.append("Supplier qualification is incomplete.")
        if item.risk_score >= 80:
            blockers.append("Opportunity risk is critical.")

        if not item.buyer_funds_cleared:
            warnings.append("Buyer funds are not yet cleared.")
        if margin_percent < 15:
            warnings.append("Protected margin is below target.")
        if item.confidence_score < 60:
            warnings.append("Opportunity confidence is below target.")

        if blockers:
            readiness = OpportunityReadiness.BLOCKED
        elif (
            score >= 80
            and item.buyer_funds_cleared
            and margin_percent >= 15
        ):
            readiness = OpportunityReadiness.READY
        elif score >= 60:
            readiness = OpportunityReadiness.CONDITIONAL
        else:
            readiness = OpportunityReadiness.EARLY

        recommended_action = (
            "Stop execution and resolve governance blockers."
            if readiness == OpportunityReadiness.BLOCKED
            else "Route opportunity to approval gateway."
            if readiness == OpportunityReadiness.READY
            else "Clear buyer funds and complete readiness conditions."
            if readiness == OpportunityReadiness.CONDITIONAL
            else "Continue qualification and evidence collection."
        )

        return OpportunityCommandRecord(
            opportunity_id=item.opportunity_id,
            title=item.title,
            protected_profit=round(protected_profit, 2),
            protected_margin_percent=round(margin_percent, 2),
            priority_score=score,
            readiness=readiness,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            recommended_action=recommended_action,
        )


_service = OpportunityCommandService()


def get_opportunity_command_service() -> OpportunityCommandService:
    return _service