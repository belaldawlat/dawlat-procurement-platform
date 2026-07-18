"""Procurement Timing Engine for the Autonomous Procurement Brain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any


class TimingDecision(str, Enum):
    BUY_NOW = "Buy Now"
    PREPARE_NOW = "Prepare Now"
    WAIT = "Wait"
    DELAY = "Delay"
    AVOID = "Avoid"


@dataclass(frozen=True)
class ProcurementTimingInput:
    case_id: str
    required_by_date: str | None
    supplier_lead_time_days: int | None
    transit_time_days: int | None
    customs_buffer_days: int = 7
    safety_buffer_days: int = 7
    quotation_expiry_date: str | None = None
    expected_price_change_percent: float = 0.0
    expected_freight_change_percent: float = 0.0
    disruption_probability: float = 0.0
    buyer_readiness_score: int = 0
    supplier_readiness_score: int = 0
    funds_clearance_score: int = 0
    compliance_ready: bool = False


@dataclass(frozen=True)
class ProcurementTimingRecommendation:
    case_id: str
    decision: TimingDecision
    urgency_score: int
    recommended_action_date: str | None
    latest_safe_order_date: str | None
    days_of_buffer: int | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class ProcurementTimingEngine:
    def evaluate(
        self,
        timing: ProcurementTimingInput,
    ) -> ProcurementTimingRecommendation:
        blockers: list[str] = []
        warnings: list[str] = []

        required_by = _parse_date(timing.required_by_date)
        quotation_expiry = _parse_date(timing.quotation_expiry_date)

        total_required_days = sum(
            value
            for value in (
                timing.supplier_lead_time_days,
                timing.transit_time_days,
                timing.customs_buffer_days,
                timing.safety_buffer_days,
            )
            if value is not None
        )

        latest_safe_order_date: date | None = None
        days_of_buffer: int | None = None

        if required_by is not None:
            latest_safe_order_date = required_by - timedelta(
                days=total_required_days
            )
            days_of_buffer = (
                latest_safe_order_date - date.today()
            ).days

        if timing.buyer_readiness_score < 50:
            blockers.append("Buyer readiness is incomplete.")
        if timing.supplier_readiness_score < 50:
            blockers.append("Supplier readiness is incomplete.")
        if timing.funds_clearance_score < 50:
            blockers.append("Funds clearance readiness is incomplete.")
        if not timing.compliance_ready:
            blockers.append("Compliance readiness is incomplete.")

        if (
            quotation_expiry is not None
            and quotation_expiry < date.today()
        ):
            blockers.append("Current quotation has expired.")

        if timing.disruption_probability >= 0.70:
            blockers.append(
                "Supply disruption probability is critically high."
            )
        elif timing.disruption_probability >= 0.40:
            warnings.append(
                "Supply disruption probability is elevated."
            )

        urgency_score = 40

        if days_of_buffer is not None:
            if days_of_buffer <= 0:
                urgency_score = 100
            elif days_of_buffer <= 7:
                urgency_score = 90
            elif days_of_buffer <= 21:
                urgency_score = 75
            elif days_of_buffer <= 45:
                urgency_score = 60
            else:
                urgency_score = 40

        if timing.expected_price_change_percent > 5:
            urgency_score += 10
            warnings.append("Price is expected to increase.")

        if timing.expected_freight_change_percent > 5:
            urgency_score += 10
            warnings.append("Freight cost is expected to increase.")

        urgency_score = min(100, urgency_score)

        decision = self._decision(
            blockers=blockers,
            urgency_score=urgency_score,
            days_of_buffer=days_of_buffer,
        )

        recommended_action_date = (
            date.today().isoformat()
            if decision in {
                TimingDecision.BUY_NOW,
                TimingDecision.PREPARE_NOW,
            }
            else latest_safe_order_date.isoformat()
            if latest_safe_order_date is not None
            else None
        )

        return ProcurementTimingRecommendation(
            case_id=timing.case_id,
            decision=decision,
            urgency_score=urgency_score,
            recommended_action_date=recommended_action_date,
            latest_safe_order_date=(
                latest_safe_order_date.isoformat()
                if latest_safe_order_date is not None
                else None
            ),
            days_of_buffer=days_of_buffer,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            explanation=(
                f"Timing decision: {decision.value}. Urgency score is "
                f"{urgency_score}/100. Estimated procurement duration is "
                f"{total_required_days} day(s)."
            ),
        )

    @staticmethod
    def _decision(
        *,
        blockers: list[str],
        urgency_score: int,
        days_of_buffer: int | None,
    ) -> TimingDecision:
        if blockers:
            return TimingDecision.AVOID
        if urgency_score >= 85:
            return TimingDecision.BUY_NOW
        if urgency_score >= 65:
            return TimingDecision.PREPARE_NOW
        if days_of_buffer is not None and days_of_buffer > 45:
            return TimingDecision.WAIT
        return TimingDecision.DELAY


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


_engine = ProcurementTimingEngine()


def get_procurement_timing_engine() -> ProcurementTimingEngine:
    return _engine