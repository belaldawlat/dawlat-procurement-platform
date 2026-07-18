"""Opportunity Prediction Engine for the Autonomous Procurement Brain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable

from services.autonomous_intelligence.market_signal_engine import (
    MarketSignal,
    SignalDirection,
    SignalSeverity,
)


class OpportunityClass(str, Enum):
    AVOID = "Avoid"
    WATCH = "Watch"
    REVIEW = "Review"
    PURSUE = "Pursue"
    PRIORITY = "Priority"


@dataclass(frozen=True)
class OpportunityInput:
    opportunity_id: str
    product_name: str
    target_market: str
    demand_score: int
    supply_availability_score: int
    buyer_readiness_score: int
    supplier_readiness_score: int
    estimated_margin_percent: float
    risk_score: int
    trust_score: int
    competition_score: int
    strategic_fit_score: int
    cash_exposure_score: int
    market_signals: tuple[MarketSignal, ...] = ()


@dataclass(frozen=True)
class OpportunityPrediction:
    opportunity_id: str
    prediction_score: int
    confidence_score: int
    classification: OpportunityClass
    predicted_success_probability: float
    expected_margin_percent: float
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    reasons: tuple[str, ...]
    recommended_action: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class OpportunityPredictionEngine:
    def predict(
        self,
        opportunity: OpportunityInput,
    ) -> OpportunityPrediction:
        blockers: list[str] = []
        warnings: list[str] = []
        reasons: list[str] = []

        if opportunity.buyer_readiness_score < 50:
            blockers.append("Buyer readiness is below the minimum threshold.")

        if opportunity.supplier_readiness_score < 50:
            blockers.append("Supplier readiness is below the minimum threshold.")

        if opportunity.estimated_margin_percent < 8:
            blockers.append("Estimated margin is below the protected threshold.")
        elif opportunity.estimated_margin_percent < 15:
            warnings.append("Estimated margin is narrow.")

        if opportunity.risk_score >= 80:
            blockers.append("Risk score is critically high.")
        elif opportunity.risk_score >= 60:
            warnings.append("Risk score requires enhanced review.")

        if opportunity.trust_score < 50:
            blockers.append("Trust score is below the minimum threshold.")

        positive_signal_score = sum(
            signal.strength_score
            for signal in opportunity.market_signals
            if signal.direction == SignalDirection.POSITIVE
        )
        negative_signal_score = sum(
            signal.strength_score
            for signal in opportunity.market_signals
            if signal.direction == SignalDirection.NEGATIVE
        )
        signal_count = len(opportunity.market_signals)

        signal_balance = 50
        if signal_count:
            signal_balance = max(
                0,
                min(
                    100,
                    round(
                        50
                        + (
                            positive_signal_score
                            - negative_signal_score
                        )
                        / signal_count
                        * 0.25
                    ),
                ),
            )

        prediction_score = round(
            opportunity.demand_score * 0.16
            + opportunity.supply_availability_score * 0.10
            + opportunity.buyer_readiness_score * 0.12
            + opportunity.supplier_readiness_score * 0.12
            + min(
                100,
                max(
                    0,
                    opportunity.estimated_margin_percent * 4,
                ),
            )
            * 0.14
            + opportunity.trust_score * 0.10
            + opportunity.strategic_fit_score * 0.10
            + (100 - opportunity.risk_score) * 0.10
            + (100 - opportunity.competition_score) * 0.03
            + (100 - opportunity.cash_exposure_score) * 0.01
            + signal_balance * 0.02
        )
        prediction_score = max(0, min(100, prediction_score))

        confidence_score = min(
            100,
            round(
                45
                + signal_count * 5
                + (
                    sum(
                        signal.confidence_score
                        for signal in opportunity.market_signals
                    )
                    / signal_count
                    * 0.35
                    if signal_count
                    else 0
                )
            ),
        )

        probability = max(
            0.0,
            min(
                1.0,
                (
                    prediction_score * 0.70
                    + confidence_score * 0.30
                )
                / 100.0
            ),
        )

        classification = self._classification(
            prediction_score=prediction_score,
            blockers=blockers,
        )

        if opportunity.demand_score >= 75:
            reasons.append("Demand strength is high.")
        if opportunity.estimated_margin_percent >= 20:
            reasons.append("Projected margin is attractive.")
        if opportunity.trust_score >= 75:
            reasons.append("Trust profile is strong.")
        if any(
            signal.severity in {
                SignalSeverity.CRITICAL,
                SignalSeverity.HIGH,
            }
            and signal.direction == SignalDirection.POSITIVE
            for signal in opportunity.market_signals
        ):
            reasons.append(
                "Strong positive market signals support the opportunity."
            )

        return OpportunityPrediction(
            opportunity_id=opportunity.opportunity_id,
            prediction_score=prediction_score,
            confidence_score=confidence_score,
            classification=classification,
            predicted_success_probability=round(probability, 4),
            expected_margin_percent=round(
                opportunity.estimated_margin_percent,
                2,
            ),
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            reasons=tuple(reasons),
            recommended_action=self._recommended_action(
                classification=classification,
                blockers=blockers,
            ),
        )

    def rank(
        self,
        opportunities: Iterable[OpportunityInput],
    ) -> list[OpportunityPrediction]:
        results = [
            self.predict(opportunity)
            for opportunity in opportunities
        ]
        results.sort(
            key=lambda item: (
                item.classification
                in {
                    OpportunityClass.AVOID,
                    OpportunityClass.WATCH,
                },
                -item.prediction_score,
                -item.confidence_score,
            )
        )
        return results

    @staticmethod
    def _classification(
        *,
        prediction_score: int,
        blockers: list[str],
    ) -> OpportunityClass:
        if blockers:
            return OpportunityClass.AVOID
        if prediction_score >= 85:
            return OpportunityClass.PRIORITY
        if prediction_score >= 70:
            return OpportunityClass.PURSUE
        if prediction_score >= 55:
            return OpportunityClass.REVIEW
        return OpportunityClass.WATCH

    @staticmethod
    def _recommended_action(
        *,
        classification: OpportunityClass,
        blockers: list[str],
    ) -> str:
        if blockers:
            return (
                "Do not progress. Resolve all blockers and rerun the prediction."
            )

        return {
            OpportunityClass.PRIORITY: (
                "Escalate for immediate commercial review and verified sourcing."
            ),
            OpportunityClass.PURSUE: (
                "Proceed to controlled supplier discovery and quotation comparison."
            ),
            OpportunityClass.REVIEW: (
                "Validate assumptions and strengthen evidence before progressing."
            ),
            OpportunityClass.WATCH: (
                "Monitor the opportunity and collect additional evidence."
            ),
            OpportunityClass.AVOID: "Do not progress.",
        }[classification]


_engine = OpportunityPredictionEngine()


def get_opportunity_prediction_engine() -> OpportunityPredictionEngine:
    return _engine