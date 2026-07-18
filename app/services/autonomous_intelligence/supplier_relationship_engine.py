"""Supplier relationship intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SupplierRelationshipTier(str, Enum):
    RESTRICTED = "Restricted"
    TRANSACTIONAL = "Transactional"
    PREFERRED = "Preferred"
    STRATEGIC = "Strategic"


@dataclass(frozen=True)
class SupplierRelationshipInput:
    supplier_id: str
    responsiveness_score: int
    delivery_score: int
    quality_score: int
    pricing_stability_score: int
    communication_score: int
    dispute_score: int
    strategic_importance_score: int


@dataclass(frozen=True)
class SupplierRelationshipResult:
    supplier_id: str
    score: int
    tier: SupplierRelationshipTier
    approved_for_preferred_status: bool
    warnings: tuple[str, ...]
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class SupplierRelationshipEngine:
    def evaluate(
        self,
        item: SupplierRelationshipInput,
    ) -> SupplierRelationshipResult:
        score = round(
            item.responsiveness_score * 0.15
            + item.delivery_score * 0.20
            + item.quality_score * 0.20
            + item.pricing_stability_score * 0.15
            + item.communication_score * 0.10
            + (100 - item.dispute_score) * 0.10
            + item.strategic_importance_score * 0.10
        )
        score = max(0, min(100, score))

        warnings: list[str] = []

        if item.dispute_score >= 60:
            warnings.append("Supplier dispute risk is elevated.")
        if item.quality_score < 60:
            warnings.append("Supplier quality performance is weak.")

        if score >= 85 and not warnings:
            tier = SupplierRelationshipTier.STRATEGIC
        elif score >= 70:
            tier = SupplierRelationshipTier.PREFERRED
        elif score >= 45:
            tier = SupplierRelationshipTier.TRANSACTIONAL
        else:
            tier = SupplierRelationshipTier.RESTRICTED

        return SupplierRelationshipResult(
            supplier_id=item.supplier_id,
            score=score,
            tier=tier,
            approved_for_preferred_status=(
                tier
                in {
                    SupplierRelationshipTier.PREFERRED,
                    SupplierRelationshipTier.STRATEGIC,
                }
                and not warnings
            ),
            warnings=tuple(warnings),
            explanation=(
                f"Supplier relationship score is {score}/100. "
                f"Tier: {tier.value}."
            ),
        )


_engine = SupplierRelationshipEngine()


def get_supplier_relationship_engine() -> SupplierRelationshipEngine:
    return _engine