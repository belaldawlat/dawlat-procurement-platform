"""Unified enterprise risk command service."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable

class EnterpriseRiskLevel(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    CRITICAL = "Critical"

@dataclass(frozen=True)
class RiskCommandItem:
    case_id: str
    category: str
    title: str
    probability: float
    impact_score: int
    confidence_score: int
    blocking: bool
    evidence: tuple[str, ...] = ()

@dataclass(frozen=True)
class RiskCommandSnapshot:
    overall_risk_score: int
    risk_level: EnterpriseRiskLevel
    critical_risk_count: int
    blocking_case_ids: tuple[str, ...]
    category_scores: dict[str, int]
    top_risks: tuple[RiskCommandItem, ...]
    evidence_count: int
    execution_allowed: bool
    warnings: tuple[str, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

class RiskCommandService:
    def evaluate(
        self,
        risks: Iterable[RiskCommandItem],
    ) -> RiskCommandSnapshot:
        items = list(risks)
        warnings: list[str] = []

        if not items:
            return RiskCommandSnapshot(
                overall_risk_score=0,
                risk_level=EnterpriseRiskLevel.LOW,
                critical_risk_count=0,
                blocking_case_ids=(),
                category_scores={},
                top_risks=(),
                evidence_count=0,
                execution_allowed=True,
                warnings=(),
            )

        category_values: dict[str, list[int]] = {}
        scored_items: list[tuple[RiskCommandItem, int]] = []

        for item in items:
            probability = max(0.0, min(1.0, item.probability))
            impact = max(0, min(100, item.impact_score))
            confidence = max(0, min(100, item.confidence_score))
            score = max(
                0,
                min(
                    100,
                    round(
                        probability * impact * 0.70
                        + confidence * 0.30
                    ),
                ),
            )
            category_values.setdefault(item.category, []).append(score)
            scored_items.append((item, score))

        category_scores = {
            category: round(sum(values) / len(values))
            for category, values in category_values.items()
        }

        highest_category = max(category_scores.values(), default=0)
        blocking_bonus = min(
            20,
            sum(1 for item in items if item.blocking) * 5,
        )
        overall = min(100, highest_category + blocking_bonus)

        if overall >= 80:
            level = EnterpriseRiskLevel.CRITICAL
        elif overall >= 60:
            level = EnterpriseRiskLevel.HIGH
        elif overall >= 35:
            level = EnterpriseRiskLevel.MODERATE
        else:
            level = EnterpriseRiskLevel.LOW

        ranked = sorted(
            scored_items,
            key=lambda pair: (
                pair[0].blocking,
                pair[1],
                pair[0].confidence_score,
            ),
            reverse=True,
        )

        critical_count = sum(
            1
            for _, score in scored_items
            if score >= 80
        )

        blocking_cases = tuple(
            dict.fromkeys(
                item.case_id
                for item in items
                if item.blocking
            )
        )

        if blocking_cases:
            warnings.append(
                "One or more procurement cases are blocked by risk controls."
            )
        if critical_count:
            warnings.append(
                "Critical risk events require immediate review."
            )

        return RiskCommandSnapshot(
            overall_risk_score=overall,
            risk_level=level,
            critical_risk_count=critical_count,
            blocking_case_ids=blocking_cases,
            category_scores=category_scores,
            top_risks=tuple(item for item, _ in ranked[:10]),
            evidence_count=sum(len(item.evidence) for item in items),
            execution_allowed=(
                not blocking_cases
                and level != EnterpriseRiskLevel.CRITICAL
            ),
            warnings=tuple(warnings),
        )

_service = RiskCommandService()

def get_risk_command_service() -> RiskCommandService:
    return _service