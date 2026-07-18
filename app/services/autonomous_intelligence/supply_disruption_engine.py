"""Supply Disruption Engine for the Autonomous Procurement Brain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable


class DisruptionType(str, Enum):
    SUPPLIER_FAILURE = "Supplier Failure"
    CAPACITY_SHORTAGE = "Capacity Shortage"
    PORT_CONGESTION = "Port Congestion"
    SHIPPING_DELAY = "Shipping Delay"
    WEATHER = "Weather"
    GEOPOLITICAL = "Geopolitical"
    REGULATORY = "Regulatory"
    SANCTIONS = "Sanctions"
    CURRENCY = "Currency"
    QUALITY_FAILURE = "Quality Failure"
    DOCUMENT_FAILURE = "Document Failure"


class DisruptionRiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass(frozen=True)
class DisruptionFactor:
    factor_id: str
    disruption_type: DisruptionType
    probability: float
    impact_score: int
    confidence_score: int
    supplier_id: str | None = None
    route_id: str | None = None
    country: str | None = None
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class SupplyDisruptionAssessment:
    overall_risk_score: int
    risk_level: DisruptionRiskLevel
    disruption_probability: float
    expected_impact_score: int
    critical_factors: tuple[DisruptionFactor, ...]
    mitigation_actions: tuple[str, ...]
    sourcing_allowed: bool
    execution_allowed: bool
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class SupplyDisruptionEngine:
    def assess(
        self,
        factors: Iterable[DisruptionFactor],
    ) -> SupplyDisruptionAssessment:
        factor_list = list(factors)

        if not factor_list:
            return SupplyDisruptionAssessment(
                overall_risk_score=10,
                risk_level=DisruptionRiskLevel.LOW,
                disruption_probability=0.0,
                expected_impact_score=0,
                critical_factors=(),
                mitigation_actions=("Continue routine monitoring.",),
                sourcing_allowed=True,
                execution_allowed=False,
                explanation=(
                    "No disruption factors were supplied. "
                    "Execution remains subject to normal approvals."
                ),
            )

        weighted_risk = 0.0
        combined_non_occurrence = 1.0
        impact_values: list[int] = []

        for factor in factor_list:
            probability = max(
                0.0,
                min(1.0, factor.probability),
            )
            impact = max(
                0,
                min(100, factor.impact_score),
            )
            confidence = max(
                0,
                min(100, factor.confidence_score),
            )

            weighted_risk += (
                probability
                * impact
                * (0.5 + confidence / 200.0)
            )
            combined_non_occurrence *= 1.0 - probability
            impact_values.append(impact)

        disruption_probability = 1.0 - combined_non_occurrence

        overall_risk_score = max(
            0,
            min(
                100,
                round(
                    weighted_risk / max(1, len(factor_list))
                    + disruption_probability * 30
                ),
            ),
        )

        expected_impact_score = round(
            sum(impact_values) / len(impact_values)
        )
        risk_level = self._risk_level(overall_risk_score)

        critical_factors = tuple(
            factor
            for factor in factor_list
            if (
                factor.probability >= 0.50
                and factor.impact_score >= 70
            )
        )

        mitigation_actions = self._mitigations(factor_list)
        sourcing_allowed = (
            risk_level != DisruptionRiskLevel.CRITICAL
        )

        return SupplyDisruptionAssessment(
            overall_risk_score=overall_risk_score,
            risk_level=risk_level,
            disruption_probability=round(
                disruption_probability,
                4,
            ),
            expected_impact_score=expected_impact_score,
            critical_factors=critical_factors,
            mitigation_actions=tuple(mitigation_actions),
            sourcing_allowed=sourcing_allowed,
            execution_allowed=False,
            explanation=(
                f"Supply disruption risk is {overall_risk_score}/100 "
                f"with combined probability "
                f"{disruption_probability:.2%}. Execution remains blocked "
                "until mitigation and approval controls pass."
            ),
        )

    @staticmethod
    def _risk_level(
        score: int,
    ) -> DisruptionRiskLevel:
        if score >= 80:
            return DisruptionRiskLevel.CRITICAL
        if score >= 60:
            return DisruptionRiskLevel.HIGH
        if score >= 35:
            return DisruptionRiskLevel.MEDIUM
        return DisruptionRiskLevel.LOW

    @staticmethod
    def _mitigations(
        factors: list[DisruptionFactor],
    ) -> list[str]:
        actions: list[str] = []
        factor_types = {
            factor.disruption_type
            for factor in factors
        }

        if DisruptionType.SUPPLIER_FAILURE in factor_types:
            actions.append("Qualify at least one backup supplier.")

        if DisruptionType.CAPACITY_SHORTAGE in factor_types:
            actions.append(
                "Split demand across verified suppliers or reserve capacity."
            )

        if (
            DisruptionType.PORT_CONGESTION in factor_types
            or DisruptionType.SHIPPING_DELAY in factor_types
        ):
            actions.append(
                "Compare alternative ports, routes and shipping schedules."
            )

        if DisruptionType.WEATHER in factor_types:
            actions.append(
                "Increase safety stock and delivery buffers."
            )

        if (
            DisruptionType.GEOPOLITICAL in factor_types
            or DisruptionType.SANCTIONS in factor_types
            or DisruptionType.REGULATORY in factor_types
        ):
            actions.append(
                "Escalate to compliance and verify alternative sourcing countries."
            )

        if DisruptionType.CURRENCY in factor_types:
            actions.append(
                "Review foreign-exchange exposure and pricing validity."
            )

        if (
            DisruptionType.QUALITY_FAILURE in factor_types
            or DisruptionType.DOCUMENT_FAILURE in factor_types
        ):
            actions.append(
                "Require inspection, document verification and milestone holds."
            )

        return list(dict.fromkeys(actions)) or [
            "Continue enhanced monitoring."
        ]


_engine = SupplyDisruptionEngine()


def get_supply_disruption_engine() -> SupplyDisruptionEngine:
    return _engine