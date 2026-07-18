"""Buyer relationship intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class BuyerRelationshipTier(str, Enum):
    RESTRICTED = "Restricted"
    STANDARD = "Standard"
    VALUED = "Valued"
    STRATEGIC = "Strategic"


@dataclass(frozen=True)
class BuyerRelationshipInput:
    buyer_id: str
    payment_reliability_score: int
    purchase_frequency_score: int
    lifetime_value_score: int
    growth_score: int
    satisfaction_score: int
    dispute_score: int


@dataclass(frozen=True)
class BuyerRelationshipResult:
    buyer_id: str
    score: int
    tier: BuyerRelationshipTier
    approved_for_priority_service: bool
    warnings: tuple[str, ...]
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class BuyerRelationshipEngine:
    def evaluate(
        self,
        item: BuyerRelationshipInput,
    ) -> BuyerRelationshipResult:
        score = round(
            item.payment_reliability_score * 0.25
            + item.purchase_frequency_score * 0.15
            + item.lifetime_value_score * 0.20
            + item.growth_score * 0.15
            + item.satisfaction_score * 0.15
            + (100 - item.dispute_score) * 0.10
        )
        score = max(0, min(100, score))

        warnings: list[str] = []

        if item.payment_reliability_score < 60:
            warnings.append("Buyer payment reliability is weak.")
        if item.dispute_score >= 60:
            warnings.append("Buyer dispute risk is elevated.")

        if score >= 85 and not warnings:
            tier = BuyerRelationshipTier.STRATEGIC
        elif score >= 70:
            tier = BuyerRelationshipTier.VALUED
        elif score >= 45:
            tier = BuyerRelationshipTier.STANDARD
        else:
            tier = BuyerRelationshipTier.RESTRICTED

        return BuyerRelationshipResult(
            buyer_id=item.buyer_id,
            score=score,
            tier=tier,
            approved_for_priority_service=(
                tier
                in {
                    BuyerRelationshipTier.VALUED,
                    BuyerRelationshipTier.STRATEGIC,
                }
                and not warnings
            ),
            warnings=tuple(warnings),
            explanation=(
                f"Buyer relationship score is {score}/100. "
                f"Tier: {tier.value}."
            ),
        )


_engine = BuyerRelationshipEngine()


def get_buyer_relationship_engine() -> BuyerRelationshipEngine:
    return _engine