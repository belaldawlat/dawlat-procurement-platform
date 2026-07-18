"""Market Gap Intelligence Engine for GPNI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class GapSeverity(str, Enum):
    """Severity levels for detected market gaps."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass(frozen=True)
class MarketGap:
    """Immutable market-gap assessment."""

    product_name: str
    destination_country: str
    demand_count: int
    verified_supply_count: int
    local_verified_supply_count: int
    estimated_demand_quantity: float
    estimated_supply_capacity: float
    shortage_quantity: float
    severity: GapSeverity
    confidence_score: int
    opportunity_score: int
    explanation: str
    recommended_actions: tuple[str, ...]


class MarketGapIntelligenceEngine:
    """Analyse buyer demand against verified supplier capacity."""

    def analyse(
        self,
        demands: Iterable[dict[str, Any]],
        supplies: Iterable[dict[str, Any]],
    ) -> list[MarketGap]:
        """Return deterministic market-gap assessments."""

        grouped_demand: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = {}

        grouped_supply: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = {}

        for demand in demands:
            product = _normalise_text(demand.get("product_name"))
            destination = _normalise_text(
                demand.get("destination_country")
            )

            if not product:
                continue

            key = (product, destination)
            grouped_demand.setdefault(key, []).append(demand)

        for supply in supplies:
            product = _normalise_text(supply.get("product_name"))
            country = _normalise_text(supply.get("country"))

            if not product:
                continue

            if country:
                grouped_supply.setdefault(
                    (product, country),
                    [],
                ).append(supply)

            grouped_supply.setdefault(
                (product, "global"),
                [],
            ).append(supply)

        results: list[MarketGap] = []

        for key, demand_items in grouped_demand.items():
            product, destination = key

            supply_items = self._deduplicate_supplies(
                grouped_supply.get(
                    (product, destination),
                    [],
                )
                + grouped_supply.get(
                    (product, "global"),
                    [],
                )
            )

            verified_supply = [
                item
                for item in supply_items
                if _normalise_status(
                    item.get("verification_status")
                )
                == "verified"
                and bool(item.get("matching_allowed", True))
            ]

            local_verified_supply = [
                item
                for item in verified_supply
                if _normalise_text(item.get("country"))
                == destination
            ]

            demand_quantity = sum(
                _number(item.get("quantity"))
                for item in demand_items
            )

            supply_capacity = sum(
                _number(item.get("capacity"))
                for item in verified_supply
            )

            shortage_quantity = max(
                0.0,
                demand_quantity - supply_capacity,
            )

            demand_count = len(demand_items)
            verified_supply_count = len(verified_supply)

            severity = self._determine_severity(
                demand_count=demand_count,
                verified_supply_count=verified_supply_count,
                local_verified_supply_count=len(
                    local_verified_supply
                ),
                shortage_quantity=shortage_quantity,
                supply_capacity=supply_capacity,
            )

            confidence_score = self._calculate_confidence_score(
                demand_count=demand_count,
                verified_supply_count=verified_supply_count,
            )

            opportunity_score = self._calculate_opportunity_score(
                demand_count=demand_count,
                severity=severity,
                has_local_verified_supply=bool(
                    local_verified_supply
                ),
            )

            explanation = (
                f"{demand_count} demand record(s) are matched "
                f"against {verified_supply_count} verified supply "
                f"record(s). Estimated shortage is "
                f"{shortage_quantity:.2f} units."
            )

            recommended_actions = (
                "Verify buyer demand and commercial readiness.",
                "Run local and international supplier discovery.",
                "Request comparable quotations and landed-cost scenarios.",
                "Apply risk, trust, compliance and payment safeguards.",
            )

            results.append(
                MarketGap(
                    product_name=_display_name(product),
                    destination_country=_display_name(destination),
                    demand_count=demand_count,
                    verified_supply_count=verified_supply_count,
                    local_verified_supply_count=len(
                        local_verified_supply
                    ),
                    estimated_demand_quantity=round(
                        demand_quantity,
                        2,
                    ),
                    estimated_supply_capacity=round(
                        supply_capacity,
                        2,
                    ),
                    shortage_quantity=round(
                        shortage_quantity,
                        2,
                    ),
                    severity=severity,
                    confidence_score=confidence_score,
                    opportunity_score=opportunity_score,
                    explanation=explanation,
                    recommended_actions=recommended_actions,
                )
            )

        severity_rank = {
            GapSeverity.CRITICAL: 4,
            GapSeverity.HIGH: 3,
            GapSeverity.MEDIUM: 2,
            GapSeverity.LOW: 1,
        }

        results.sort(
            key=lambda item: (
                -severity_rank[item.severity],
                -item.opportunity_score,
                -item.confidence_score,
                item.product_name,
                item.destination_country,
            )
        )

        return results

    @staticmethod
    def _deduplicate_supplies(
        supplies: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Remove duplicate supply records deterministically."""

        unique: list[dict[str, Any]] = []
        seen: set[int] = set()

        for supply in supplies:
            identity = id(supply)

            if identity in seen:
                continue

            seen.add(identity)
            unique.append(supply)

        return unique

    @staticmethod
    def _determine_severity(
        *,
        demand_count: int,
        verified_supply_count: int,
        local_verified_supply_count: int,
        shortage_quantity: float,
        supply_capacity: float,
    ) -> GapSeverity:
        """Determine gap severity using deterministic thresholds."""

        if demand_count > 0 and verified_supply_count == 0:
            return GapSeverity.CRITICAL

        if shortage_quantity > 0 and supply_capacity <= 0:
            return GapSeverity.CRITICAL

        if (
            supply_capacity > 0
            and shortage_quantity > supply_capacity * 0.5
        ):
            return GapSeverity.HIGH

        if local_verified_supply_count == 0:
            return GapSeverity.MEDIUM

        return GapSeverity.LOW

    @staticmethod
    def _calculate_confidence_score(
        *,
        demand_count: int,
        verified_supply_count: int,
    ) -> int:
        """Calculate confidence using available evidence volume."""

        score = (
            30
            + demand_count * 8
            + verified_supply_count * 6
        )

        return max(0, min(100, round(score)))

    @staticmethod
    def _calculate_opportunity_score(
        *,
        demand_count: int,
        severity: GapSeverity,
        has_local_verified_supply: bool,
    ) -> int:
        """Calculate commercial opportunity potential."""

        score = demand_count * 12

        if severity == GapSeverity.CRITICAL:
            score += 25
        elif severity == GapSeverity.HIGH:
            score += 15

        if not has_local_verified_supply:
            score += 10

        return max(0, min(100, round(score)))


def _normalise_text(value: Any) -> str:
    """Return a normalised lowercase text value."""

    return str(value or "").strip().lower()


def _normalise_status(value: Any) -> str:
    """Return a normalised status value."""

    return str(value or "").strip().lower()


def _display_name(value: str) -> str:
    """Return a display-safe title."""

    if not value:
        return "Unknown"

    return value.title()


def _number(value: Any) -> float:
    """Safely convert a value into a non-negative float."""

    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, number)


_engine = MarketGapIntelligenceEngine()


def get_market_gap_intelligence_engine() -> MarketGapIntelligenceEngine:
    """Return the shared market-gap intelligence engine."""

    return _engine