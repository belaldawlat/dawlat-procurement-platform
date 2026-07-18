"""Autonomous Priority Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable


class PriorityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass(frozen=True)
class PriorityItem:
    item_id: str
    item_type: str
    title: str
    business_value_score: int
    urgency_score: int
    risk_score: int
    confidence_score: int
    margin_score: int
    strategic_fit_score: int
    dependency_blocker_count: int = 0
    deadline_days: int | None = None


@dataclass(frozen=True)
class PriorityAssessment:
    item_id: str
    priority_score: int
    level: PriorityLevel
    queue_position: int
    reasons: tuple[str, ...]
    recommended_action: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class AutonomousPriorityEngine:
    """Rank work by value, urgency, risk and confidence."""

    def assess(
        self,
        item: PriorityItem,
        *,
        queue_position: int = 0,
    ) -> PriorityAssessment:
        deadline_score = 40

        if item.deadline_days is not None:
            if item.deadline_days <= 1:
                deadline_score = 100
            elif item.deadline_days <= 3:
                deadline_score = 90
            elif item.deadline_days <= 7:
                deadline_score = 75
            elif item.deadline_days <= 30:
                deadline_score = 55
            else:
                deadline_score = 35

        blocker_penalty = min(
            35,
            item.dependency_blocker_count * 10,
        )

        priority_score = round(
            item.business_value_score * 0.22
            + item.urgency_score * 0.18
            + item.risk_score * 0.15
            + item.confidence_score * 0.10
            + item.margin_score * 0.15
            + item.strategic_fit_score * 0.10
            + deadline_score * 0.10
            - blocker_penalty
        )

        priority_score = max(
            0,
            min(100, priority_score),
        )

        if priority_score >= 85:
            level = PriorityLevel.CRITICAL
        elif priority_score >= 70:
            level = PriorityLevel.HIGH
        elif priority_score >= 50:
            level = PriorityLevel.MEDIUM
        else:
            level = PriorityLevel.LOW

        reasons: list[str] = []

        if item.business_value_score >= 75:
            reasons.append("Business value is high.")
        if item.urgency_score >= 75:
            reasons.append("Urgency is high.")
        if item.risk_score >= 70:
            reasons.append("Risk exposure requires attention.")
        if item.margin_score >= 75:
            reasons.append("Margin potential is strong.")
        if item.dependency_blocker_count:
            reasons.append(
                "Dependencies reduce immediate executability."
            )

        action = {
            PriorityLevel.CRITICAL: (
                "Escalate immediately for authorised review."
            ),
            PriorityLevel.HIGH: (
                "Schedule same-day review and resolve blockers."
            ),
            PriorityLevel.MEDIUM: (
                "Place in the active work queue."
            ),
            PriorityLevel.LOW: (
                "Monitor and reassess when evidence changes."
            ),
        }[level]

        return PriorityAssessment(
            item_id=item.item_id,
            priority_score=priority_score,
            level=level,
            queue_position=queue_position,
            reasons=tuple(reasons),
            recommended_action=action,
        )

    def rank(
        self,
        items: Iterable[PriorityItem],
    ) -> list[PriorityAssessment]:
        preliminary = [
            self.assess(item)
            for item in items
        ]

        preliminary.sort(
            key=lambda item: -item.priority_score
        )

        return [
            PriorityAssessment(
                **{
                    **item.__dict__,
                    "queue_position": index,
                }
            )
            for index, item in enumerate(
                preliminary,
                start=1,
            )
        ]


_engine = AutonomousPriorityEngine()


def get_autonomous_priority_engine() -> AutonomousPriorityEngine:
    return _engine