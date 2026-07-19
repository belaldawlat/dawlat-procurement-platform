"""Confidence calculation for enterprise decisions."""

from __future__ import annotations

from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionFactor,
)


class EnterpriseConfidenceEngine:
    """Calculate deterministic confidence from factor agreement."""

    def calculate(
        self,
        factors: tuple[EnterpriseDecisionFactor, ...],
        score: float,
    ) -> float:
        if not factors:
            raise ValueError(
                "At least one decision factor is required."
            )

        total_weight = sum(factor.weight for factor in factors)

        if total_weight <= 0:
            raise ValueError(
                "Decision factor weights must total more than zero."
            )

        weighted_dispersion = sum(
            abs(factor.effective_score - score) * factor.weight
            for factor in factors
        ) / total_weight

        coverage = min(1.0, total_weight)
        confidence = (
            max(0.0, 100.0 - weighted_dispersion)
            * coverage
        )

        return round(max(0.0, min(100.0, confidence)), 2)