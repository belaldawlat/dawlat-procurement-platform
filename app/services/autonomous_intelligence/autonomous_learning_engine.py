"""Autonomous Learning Engine.

Produces bounded, auditable learning adjustments from completed procurement
outcomes. Learning can influence future rankings, but can never override
mandatory approval, risk, trust, compliance, payment, or contract controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class AutonomousOutcome:
    case_id: str
    opportunity_id: str
    supplier_id: str
    buyer_id: str
    product_name: str
    route_id: str
    predicted_success_probability: float
    predicted_margin_percent: float
    realised_margin_percent: float | None
    predicted_landed_cost: float
    realised_landed_cost: float | None
    predicted_transit_days: int | None
    actual_transit_days: int | None
    buyer_paid_on_time: bool | None
    supplier_delivered_on_time: bool | None
    quality_accepted: bool | None
    disruption_occurred: bool
    dispute_occurred: bool
    completed: bool


@dataclass(frozen=True)
class LearningAdjustment:
    subject_type: str
    subject_id: str
    metric: str
    adjustment: float
    confidence_score: int
    evidence_count: int
    explanation: str


@dataclass(frozen=True)
class AutonomousLearningReport:
    outcomes_processed: int
    adjustments: tuple[LearningAdjustment, ...]
    warnings: tuple[str, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


class AutonomousLearningEngine:
    """Generate bounded learning adjustments from real outcomes."""

    MAXIMUM_ADJUSTMENT = 12.0

    def learn(
        self,
        outcomes: Iterable[AutonomousOutcome],
    ) -> AutonomousLearningReport:
        completed = [
            outcome
            for outcome in outcomes
            if outcome.completed
        ]

        warnings: list[str] = []
        grouped: dict[
            tuple[str, str, str],
            list[float],
        ] = {}

        for outcome in completed:
            self._add(
                grouped,
                "Supplier",
                outcome.supplier_id,
                "Reliability",
                self._supplier_score(outcome),
            )
            self._add(
                grouped,
                "Buyer",
                outcome.buyer_id,
                "Payment Reliability",
                self._buyer_score(outcome),
            )
            self._add(
                grouped,
                "Product",
                outcome.product_name,
                "Margin Performance",
                self._margin_score(outcome),
            )
            self._add(
                grouped,
                "Route",
                outcome.route_id,
                "Transit Performance",
                self._route_score(outcome),
            )
            self._add(
                grouped,
                "Opportunity",
                outcome.opportunity_id,
                "Prediction Accuracy",
                self._prediction_accuracy(outcome),
            )

        adjustments: list[LearningAdjustment] = []

        for (
            subject_type,
            subject_id,
            metric,
        ), scores in grouped.items():
            average_score = mean(scores)
            raw_adjustment = (
                (average_score - 50.0)
                / 50.0
                * self.MAXIMUM_ADJUSTMENT
            )
            bounded = max(
                -self.MAXIMUM_ADJUSTMENT,
                min(
                    self.MAXIMUM_ADJUSTMENT,
                    raw_adjustment,
                ),
            )
            confidence = min(
                100,
                45 + len(scores) * 10,
            )

            adjustments.append(
                LearningAdjustment(
                    subject_type=subject_type,
                    subject_id=subject_id,
                    metric=metric,
                    adjustment=round(
                        bounded,
                        2,
                    ),
                    confidence_score=confidence,
                    evidence_count=len(scores),
                    explanation=(
                        f"Adjustment is based on {len(scores)} "
                        f"completed outcome(s) with average score "
                        f"{average_score:.2f}/100."
                    ),
                )
            )

        if not completed:
            warnings.append(
                "No completed outcomes were available for learning."
            )

        return AutonomousLearningReport(
            outcomes_processed=len(completed),
            adjustments=tuple(adjustments),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _add(
        grouped: dict[
            tuple[str, str, str],
            list[float],
        ],
        subject_type: str,
        subject_id: str,
        metric: str,
        score: float,
    ) -> None:
        grouped.setdefault(
            (
                subject_type,
                subject_id,
                metric,
            ),
            [],
        ).append(score)

    @staticmethod
    def _supplier_score(
        outcome: AutonomousOutcome,
    ) -> float:
        score = 50.0

        if outcome.supplier_delivered_on_time is True:
            score += 20.0
        elif outcome.supplier_delivered_on_time is False:
            score -= 25.0

        if outcome.quality_accepted is True:
            score += 20.0
        elif outcome.quality_accepted is False:
            score -= 30.0

        if outcome.disruption_occurred:
            score -= 10.0

        if outcome.dispute_occurred:
            score -= 15.0

        return max(
            0.0,
            min(100.0, score),
        )

    @staticmethod
    def _buyer_score(
        outcome: AutonomousOutcome,
    ) -> float:
        score = 50.0

        if outcome.buyer_paid_on_time is True:
            score += 35.0
        elif outcome.buyer_paid_on_time is False:
            score -= 35.0

        if outcome.dispute_occurred:
            score -= 15.0

        return max(
            0.0,
            min(100.0, score),
        )

    @staticmethod
    def _margin_score(
        outcome: AutonomousOutcome,
    ) -> float:
        if outcome.realised_margin_percent is None:
            return 50.0

        difference = (
            outcome.realised_margin_percent
            - outcome.predicted_margin_percent
        )

        return max(
            0.0,
            min(
                100.0,
                70.0 + difference * 2.0,
            ),
        )

    @staticmethod
    def _route_score(
        outcome: AutonomousOutcome,
    ) -> float:
        if (
            outcome.predicted_transit_days is None
            or outcome.actual_transit_days is None
            or outcome.predicted_transit_days <= 0
        ):
            return 50.0

        ratio = (
            outcome.actual_transit_days
            - outcome.predicted_transit_days
        ) / outcome.predicted_transit_days

        return max(
            0.0,
            min(
                100.0,
                85.0 - ratio * 100.0,
            ),
        )

    @staticmethod
    def _prediction_accuracy(
        outcome: AutonomousOutcome,
    ) -> float:
        realised_success = 1.0

        if (
            outcome.dispute_occurred
            or outcome.quality_accepted is False
            or outcome.supplier_delivered_on_time is False
            or outcome.buyer_paid_on_time is False
        ):
            realised_success = 0.0

        prediction_error = abs(
            outcome.predicted_success_probability
            - realised_success
        )

        return max(
            0.0,
            min(
                100.0,
                100.0 - prediction_error * 100.0,
            ),
        )


_engine = AutonomousLearningEngine()


def get_autonomous_learning_engine() -> AutonomousLearningEngine:
    return _engine