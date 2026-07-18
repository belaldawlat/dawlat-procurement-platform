"""Network Learning Engine for GPNI.

Learns from completed network cases while keeping all adjustments bounded,
auditable and subordinate to mandatory risk, trust, compliance and payment
controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class NetworkOutcome:
    case_id: str
    buyer_id: str
    supplier_id: str
    product_name: str
    destination_country: str
    match_score: int
    expected_margin_percent: float
    realised_margin_percent: float | None
    expected_delivery_days: int | None
    actual_delivery_days: int | None
    buyer_paid_on_time: bool | None
    supplier_delivered_on_time: bool | None
    quality_accepted: bool | None
    dispute_occurred: bool
    completed: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NetworkLearningSignal:
    subject_type: str
    subject_id: str
    metric: str
    score: float
    confidence_score: int
    direction: str
    evidence: str


@dataclass(frozen=True)
class NetworkLearningReport:
    outcomes_processed: int
    signals: tuple[NetworkLearningSignal, ...]
    buyer_adjustments: dict[str, float]
    supplier_adjustments: dict[str, float]
    product_adjustments: dict[str, float]
    route_adjustments: dict[str, float]
    warnings: tuple[str, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


class NetworkLearningEngine:
    """Generate bounded learning signals from completed trade outcomes."""

    MAXIMUM_ADJUSTMENT = 15.0

    def learn(
        self,
        outcomes: Iterable[NetworkOutcome],
    ) -> NetworkLearningReport:
        outcome_list = list(outcomes)
        signals: list[NetworkLearningSignal] = []
        warnings: list[str] = []

        buyer_scores: dict[str, list[float]] = {}
        supplier_scores: dict[str, list[float]] = {}
        product_scores: dict[str, list[float]] = {}
        route_scores: dict[str, list[float]] = {}

        for outcome in outcome_list:
            if not outcome.completed:
                warnings.append(
                    f"Case {outcome.case_id} was skipped because it is incomplete."
                )
                continue

            buyer_score = self._buyer_score(
                outcome
            )
            supplier_score = self._supplier_score(
                outcome
            )
            product_score = self._product_score(
                outcome
            )
            route_score = self._route_score(
                outcome
            )

            buyer_scores.setdefault(
                outcome.buyer_id,
                [],
            ).append(buyer_score)

            supplier_scores.setdefault(
                outcome.supplier_id,
                [],
            ).append(supplier_score)

            product_scores.setdefault(
                outcome.product_name,
                [],
            ).append(product_score)

            route_key = (
                f"{outcome.product_name}|"
                f"{outcome.destination_country}"
            )
            route_scores.setdefault(
                route_key,
                [],
            ).append(route_score)

            signals.extend(
                [
                    self._signal(
                        subject_type="Buyer",
                        subject_id=outcome.buyer_id,
                        metric="Payment Reliability",
                        score=buyer_score,
                        evidence=(
                            f"Outcome {outcome.case_id}: "
                            f"buyer_paid_on_time={outcome.buyer_paid_on_time}."
                        ),
                    ),
                    self._signal(
                        subject_type="Supplier",
                        subject_id=outcome.supplier_id,
                        metric="Delivery and Quality Reliability",
                        score=supplier_score,
                        evidence=(
                            f"Outcome {outcome.case_id}: "
                            f"delivered_on_time="
                            f"{outcome.supplier_delivered_on_time}, "
                            f"quality_accepted={outcome.quality_accepted}."
                        ),
                    ),
                    self._signal(
                        subject_type="Product",
                        subject_id=outcome.product_name,
                        metric="Margin Performance",
                        score=product_score,
                        evidence=(
                            f"Outcome {outcome.case_id}: "
                            f"expected_margin="
                            f"{outcome.expected_margin_percent:.2f}, "
                            f"realised_margin="
                            f"{outcome.realised_margin_percent}."
                        ),
                    ),
                    self._signal(
                        subject_type="Route",
                        subject_id=route_key,
                        metric="Transit Performance",
                        score=route_score,
                        evidence=(
                            f"Outcome {outcome.case_id}: "
                            f"expected_days="
                            f"{outcome.expected_delivery_days}, "
                            f"actual_days="
                            f"{outcome.actual_delivery_days}."
                        ),
                    ),
                ]
            )

        return NetworkLearningReport(
            outcomes_processed=sum(
                1
                for outcome in outcome_list
                if outcome.completed
            ),
            signals=tuple(signals),
            buyer_adjustments=self._adjustments(
                buyer_scores
            ),
            supplier_adjustments=self._adjustments(
                supplier_scores
            ),
            product_adjustments=self._adjustments(
                product_scores
            ),
            route_adjustments=self._adjustments(
                route_scores
            ),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _buyer_score(
        outcome: NetworkOutcome,
    ) -> float:
        score = 50.0

        if outcome.buyer_paid_on_time is True:
            score += 35.0
        elif outcome.buyer_paid_on_time is False:
            score -= 35.0

        if outcome.dispute_occurred:
            score -= 20.0

        return max(
            0.0,
            min(100.0, score),
        )

    @staticmethod
    def _supplier_score(
        outcome: NetworkOutcome,
    ) -> float:
        score = 50.0

        if outcome.supplier_delivered_on_time is True:
            score += 25.0
        elif outcome.supplier_delivered_on_time is False:
            score -= 25.0

        if outcome.quality_accepted is True:
            score += 25.0
        elif outcome.quality_accepted is False:
            score -= 35.0

        if outcome.dispute_occurred:
            score -= 15.0

        return max(
            0.0,
            min(100.0, score),
        )

    @staticmethod
    def _product_score(
        outcome: NetworkOutcome,
    ) -> float:
        if outcome.realised_margin_percent is None:
            return 50.0

        difference = (
            outcome.realised_margin_percent
            - outcome.expected_margin_percent
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
        outcome: NetworkOutcome,
    ) -> float:
        if (
            outcome.expected_delivery_days is None
            or outcome.actual_delivery_days is None
            or outcome.expected_delivery_days <= 0
        ):
            return 50.0

        delay_ratio = (
            outcome.actual_delivery_days
            - outcome.expected_delivery_days
        ) / outcome.expected_delivery_days

        return max(
            0.0,
            min(
                100.0,
                85.0 - delay_ratio * 100.0,
            ),
        )

    @staticmethod
    def _signal(
        *,
        subject_type: str,
        subject_id: str,
        metric: str,
        score: float,
        evidence: str,
    ) -> NetworkLearningSignal:
        confidence = 75

        if score >= 70:
            direction = "Positive"
        elif score <= 40:
            direction = "Negative"
        else:
            direction = "Neutral"

        return NetworkLearningSignal(
            subject_type=subject_type,
            subject_id=subject_id,
            metric=metric,
            score=round(score, 2),
            confidence_score=confidence,
            direction=direction,
            evidence=evidence,
        )

    def _adjustments(
        self,
        grouped_scores: dict[str, list[float]],
    ) -> dict[str, float]:
        adjustments: dict[str, float] = {}

        for subject_id, scores in grouped_scores.items():
            average_score = mean(scores)
            raw_adjustment = (
                (average_score - 50.0)
                / 50.0
                * self.MAXIMUM_ADJUSTMENT
            )

            adjustments[subject_id] = round(
                max(
                    -self.MAXIMUM_ADJUSTMENT,
                    min(
                        self.MAXIMUM_ADJUSTMENT,
                        raw_adjustment,
                    ),
                ),
                2,
            )

        return adjustments


_engine = NetworkLearningEngine()


def get_network_learning_engine() -> NetworkLearningEngine:
    return _engine