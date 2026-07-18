"""Market Signal Engine for the Autonomous Procurement Brain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from statistics import mean
from typing import Any, Iterable


class MarketSignalType(str, Enum):
    DEMAND_GROWTH = "Demand Growth"
    DEMAND_DECLINE = "Demand Decline"
    PRICE_INCREASE = "Price Increase"
    PRICE_DECREASE = "Price Decrease"
    SHORTAGE = "Shortage"
    OVERSUPPLY = "Oversupply"
    FREIGHT_INCREASE = "Freight Increase"
    FREIGHT_DECREASE = "Freight Decrease"
    CURRENCY_RISK = "Currency Risk"
    REGULATORY_CHANGE = "Regulatory Change"
    PORT_CONGESTION = "Port Congestion"
    WEATHER_RISK = "Weather Risk"
    GEOPOLITICAL_RISK = "Geopolitical Risk"
    SUPPLIER_CAPACITY_CHANGE = "Supplier Capacity Change"


class SignalDirection(str, Enum):
    POSITIVE = "Positive"
    NEGATIVE = "Negative"
    NEUTRAL = "Neutral"


class SignalSeverity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass(frozen=True)
class MarketObservation:
    observation_id: str
    signal_type: MarketSignalType
    product_name: str
    country: str
    source_name: str
    observed_value: float
    baseline_value: float | None = None
    source_confidence: int = 50
    verified: bool = False
    observed_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketSignal:
    product_name: str
    country: str
    signal_type: MarketSignalType
    direction: SignalDirection
    severity: SignalSeverity
    strength_score: int
    confidence_score: int
    change_percent: float | None
    evidence_count: int
    explanation: str
    recommended_review: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class MarketSignalEngine:
    def analyse(
        self,
        observations: Iterable[MarketObservation],
    ) -> list[MarketSignal]:
        grouped: dict[
            tuple[str, str, MarketSignalType],
            list[MarketObservation],
        ] = {}

        for observation in observations:
            key = (
                observation.product_name.strip().lower(),
                observation.country.strip().lower(),
                observation.signal_type,
            )
            grouped.setdefault(key, []).append(observation)

        results = [
            self._build_signal(
                product_name=product.title(),
                country=country.title(),
                signal_type=signal_type,
                observations=items,
            )
            for (product, country, signal_type), items in grouped.items()
        ]

        severity_rank = {
            SignalSeverity.CRITICAL: 4,
            SignalSeverity.HIGH: 3,
            SignalSeverity.MEDIUM: 2,
            SignalSeverity.LOW: 1,
        }

        results.sort(
            key=lambda item: (
                -severity_rank[item.severity],
                -item.confidence_score,
                -item.strength_score,
            )
        )
        return results

    def _build_signal(
        self,
        *,
        product_name: str,
        country: str,
        signal_type: MarketSignalType,
        observations: list[MarketObservation],
    ) -> MarketSignal:
        verified_bonus = min(
            20,
            sum(1 for item in observations if item.verified) * 5,
        )

        confidence_score = min(
            100,
            round(
                mean(
                    max(0, min(100, item.source_confidence))
                    for item in observations
                )
                + verified_bonus
            ),
        )

        changes: list[float] = []
        for item in observations:
            if item.baseline_value not in (None, 0):
                changes.append(
                    (
                        item.observed_value - item.baseline_value
                    )
                    / abs(item.baseline_value)
                    * 100.0
                )

        change_percent = mean(changes) if changes else None

        strength_score = min(
            100,
            round(
                abs(change_percent) * 2 + verified_bonus
                if change_percent is not None
                else 30 + len(observations) * 10 + verified_bonus
            ),
        )

        direction = self._direction(
            signal_type=signal_type,
            change_percent=change_percent,
        )
        severity = self._severity(
            strength_score=strength_score,
            confidence_score=confidence_score,
        )

        return MarketSignal(
            product_name=product_name,
            country=country,
            signal_type=signal_type,
            direction=direction,
            severity=severity,
            strength_score=strength_score,
            confidence_score=confidence_score,
            change_percent=(
                round(change_percent, 2)
                if change_percent is not None
                else None
            ),
            evidence_count=len(observations),
            explanation=(
                f"{len(observations)} observation(s) indicate "
                f"{signal_type.value.lower()} for {product_name} in {country}. "
                f"Strength {strength_score}/100, confidence "
                f"{confidence_score}/100."
            ),
            recommended_review=self._review(
                signal_type=signal_type,
                severity=severity,
            ),
        )

    @staticmethod
    def _direction(
        *,
        signal_type: MarketSignalType,
        change_percent: float | None,
    ) -> SignalDirection:
        positive = {
            MarketSignalType.DEMAND_GROWTH,
            MarketSignalType.PRICE_DECREASE,
            MarketSignalType.FREIGHT_DECREASE,
            MarketSignalType.SUPPLIER_CAPACITY_CHANGE,
        }
        negative = {
            MarketSignalType.DEMAND_DECLINE,
            MarketSignalType.PRICE_INCREASE,
            MarketSignalType.SHORTAGE,
            MarketSignalType.FREIGHT_INCREASE,
            MarketSignalType.CURRENCY_RISK,
            MarketSignalType.REGULATORY_CHANGE,
            MarketSignalType.PORT_CONGESTION,
            MarketSignalType.WEATHER_RISK,
            MarketSignalType.GEOPOLITICAL_RISK,
        }

        if signal_type in positive:
            return SignalDirection.POSITIVE
        if signal_type in negative:
            return SignalDirection.NEGATIVE
        if change_percent is None or abs(change_percent) < 2:
            return SignalDirection.NEUTRAL
        return (
            SignalDirection.POSITIVE
            if change_percent > 0
            else SignalDirection.NEGATIVE
        )

    @staticmethod
    def _severity(
        *,
        strength_score: int,
        confidence_score: int,
    ) -> SignalSeverity:
        score = round(
            strength_score * 0.60
            + confidence_score * 0.40
        )
        if score >= 85:
            return SignalSeverity.CRITICAL
        if score >= 70:
            return SignalSeverity.HIGH
        if score >= 50:
            return SignalSeverity.MEDIUM
        return SignalSeverity.LOW

    @staticmethod
    def _review(
        *,
        signal_type: MarketSignalType,
        severity: SignalSeverity,
    ) -> str:
        if severity in {
            SignalSeverity.CRITICAL,
            SignalSeverity.HIGH,
        }:
            return (
                "Escalate for executive review and validate with "
                "independent evidence before commercial action."
            )
        if signal_type in {
            MarketSignalType.PRICE_INCREASE,
            MarketSignalType.FREIGHT_INCREASE,
            MarketSignalType.CURRENCY_RISK,
        }:
            return (
                "Refresh landed cost and margin analysis before quotation."
            )
        return (
            "Continue monitoring and collect additional evidence."
        )


_engine = MarketSignalEngine()


def get_market_signal_engine() -> MarketSignalEngine:
    return _engine