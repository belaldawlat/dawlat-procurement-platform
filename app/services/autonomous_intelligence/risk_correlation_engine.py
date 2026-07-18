"""Compound enterprise risk correlation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations


@dataclass(frozen=True)
class RiskFactor:
    name: str
    category: str
    probability: float
    impact_score: int
    confidence_score: int


@dataclass(frozen=True)
class CorrelatedRisk:
    factors: tuple[str, ...]
    correlation_score: int
    compound_risk_score: int
    explanation: str


@dataclass(frozen=True)
class RiskCorrelationReport:
    overall_compound_risk: int
    correlated_risks: tuple[CorrelatedRisk, ...]
    execution_allowed: bool
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class RiskCorrelationEngine:
    def analyse(
        self,
        factors: tuple[RiskFactor, ...],
    ) -> RiskCorrelationReport:
        correlated: list[CorrelatedRisk] = []

        for left, right in combinations(factors, 2):
            category_bonus = (
                20
                if left.category != right.category
                else 10
            )
            correlation_score = min(
                100,
                round(
                    (
                        left.probability
                        + right.probability
                    )
                    * 35
                    + category_bonus
                ),
            )

            compound = min(
                100,
                round(
                    (
                        left.impact_score
                        + right.impact_score
                    )
                    / 2
                    * 0.70
                    + correlation_score * 0.30
                ),
            )

            if compound >= 50:
                correlated.append(
                    CorrelatedRisk(
                        factors=(
                            left.name,
                            right.name,
                        ),
                        correlation_score=correlation_score,
                        compound_risk_score=compound,
                        explanation=(
                            f"{left.name} and {right.name} create "
                            f"compound risk {compound}/100."
                        ),
                    )
                )

        overall = (
            max(
                (
                    item.compound_risk_score
                    for item in correlated
                ),
                default=0,
            )
        )

        return RiskCorrelationReport(
            overall_compound_risk=overall,
            correlated_risks=tuple(
                sorted(
                    correlated,
                    key=lambda item: -item.compound_risk_score,
                )
            ),
            execution_allowed=overall < 80,
        )


_engine = RiskCorrelationEngine()


def get_risk_correlation_engine() -> RiskCorrelationEngine:
    return _engine