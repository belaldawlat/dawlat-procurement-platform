"""Logistics Optimization Engine for the Autonomous Procurement Brain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable


class LogisticsMode(str, Enum):
    SEA = "Sea"
    AIR = "Air"
    ROAD = "Road"
    RAIL = "Rail"
    MULTIMODAL = "Multimodal"


@dataclass(frozen=True)
class LogisticsOption:
    option_id: str
    mode: LogisticsMode
    origin: str
    destination: str
    carrier_name: str
    transit_days: int
    freight_cost: float
    port_cost: float
    customs_cost: float
    trucking_cost: float
    warehouse_cost: float
    insurance_cost: float
    reliability_score: int
    customs_delay_risk: int
    disruption_risk: int
    emissions_score: int
    capacity_available: float
    required_capacity: float
    supports_consolidation: bool = False
    supports_split_shipment: bool = False
    incoterms: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LogisticsRecommendation:
    option_id: str
    overall_score: int
    total_cost: float
    transit_days: int
    risk_score: int
    recommended: bool
    consolidation_recommended: bool
    split_shipment_recommended: bool
    preferred_incoterm: str | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class LogisticsOptimizationEngine:
    """Rank logistics options using cost, time, reliability and risk."""

    def evaluate(
        self,
        option: LogisticsOption,
    ) -> LogisticsRecommendation:
        blockers: list[str] = []
        warnings: list[str] = []

        if option.required_capacity <= 0:
            blockers.append("Required shipment capacity is invalid.")

        if option.capacity_available < option.required_capacity:
            blockers.append("Logistics capacity is insufficient.")

        if option.reliability_score < 50:
            blockers.append("Carrier reliability is below threshold.")
        elif option.reliability_score < 70:
            warnings.append("Carrier reliability is moderate.")

        if option.disruption_risk >= 80:
            blockers.append("Route disruption risk is critically high.")
        elif option.disruption_risk >= 60:
            warnings.append("Route disruption risk requires enhanced review.")

        if option.customs_delay_risk >= 70:
            warnings.append("Customs delay risk is elevated.")

        total_cost = sum(
            [
                option.freight_cost,
                option.port_cost,
                option.customs_cost,
                option.trucking_cost,
                option.warehouse_cost,
                option.insurance_cost,
            ]
        )

        cost_score = max(
            0,
            min(100, round(100 - total_cost / 1000)),
        )
        time_score = max(
            0,
            min(100, round(100 - option.transit_days * 2)),
        )
        risk_score = round(
            option.disruption_risk * 0.60
            + option.customs_delay_risk * 0.40
        )

        overall_score = round(
            cost_score * 0.25
            + time_score * 0.20
            + option.reliability_score * 0.25
            + (100 - risk_score) * 0.20
            + option.emissions_score * 0.10
        )
        overall_score = max(0, min(100, overall_score))

        recommended = overall_score >= 65 and not blockers

        consolidation_recommended = bool(
            recommended
            and option.supports_consolidation
            and option.capacity_available
            >= option.required_capacity * 1.25
        )

        split_shipment_recommended = bool(
            recommended
            and option.supports_split_shipment
            and option.disruption_risk >= 50
        )

        preferred_incoterm = (
            option.incoterms[0]
            if option.incoterms
            else None
        )

        return LogisticsRecommendation(
            option_id=option.option_id,
            overall_score=overall_score,
            total_cost=round(total_cost, 2),
            transit_days=option.transit_days,
            risk_score=risk_score,
            recommended=recommended,
            consolidation_recommended=consolidation_recommended,
            split_shipment_recommended=split_shipment_recommended,
            preferred_incoterm=preferred_incoterm,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            explanation=(
                f"Logistics option scored {overall_score}/100 with "
                f"total cost {total_cost:.2f}, transit time "
                f"{option.transit_days} day(s), and risk {risk_score}/100."
            ),
        )

    def rank(
        self,
        options: Iterable[LogisticsOption],
    ) -> list[LogisticsRecommendation]:
        results = [
            self.evaluate(option)
            for option in options
        ]

        results.sort(
            key=lambda item: (
                not item.recommended,
                -item.overall_score,
                item.total_cost,
                item.transit_days,
            )
        )
        return results


_engine = LogisticsOptimizationEngine()


def get_logistics_optimization_engine() -> LogisticsOptimizationEngine:
    return _engine