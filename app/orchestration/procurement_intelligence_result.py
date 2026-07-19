"""Results returned by the procurement intelligence engine."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.procurement_intelligence_models import (
    ProcurementRecommendation,
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SupplierRanking:
    rank: int
    supplier_id: str
    supplier_name: str
    quotation_id: str
    score: float
    landed_cost: float
    risk_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "quotation_id": self.quotation_id,
            "score": self.score,
            "landed_cost": self.landed_cost,
            "risk_score": self.risk_score,
        }


@dataclass(frozen=True)
class ProcurementIntelligenceResult:
    case_id: str
    rankings: tuple[SupplierRanking, ...]
    recommendations: tuple[ProcurementRecommendation, ...]
    evaluated_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise ValueError("Procurement case ID is required.")

        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "rankings", tuple(self.rankings))
        object.__setattr__(self, "recommendations", tuple(self.recommendations))
        object.__setattr__(self, "policy_id", str(self.policy_id or "").strip())
        object.__setattr__(self, "policy_version", str(self.policy_version or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def best_supplier(self) -> SupplierRanking | None:
        return self.rankings[0] if self.rankings else None

    @property
    def urgent_recommendations(self) -> tuple[ProcurementRecommendation, ...]:
        return tuple(
            recommendation
            for recommendation in self.recommendations
            if recommendation.priority.value in {"high", "critical"}
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "best_supplier": (
                self.best_supplier.as_dict()
                if self.best_supplier
                else None
            ),
            "metadata": redact_mapping(self.metadata),
            "rankings": [ranking.as_dict() for ranking in self.rankings],
            "recommendations": [
                recommendation.as_dict()
                for recommendation in self.recommendations
            ],
        }