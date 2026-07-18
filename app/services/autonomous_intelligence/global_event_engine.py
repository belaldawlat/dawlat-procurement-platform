"""Global event impact mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GlobalEventType(str, Enum):
    WAR = "War"
    ELECTION = "Election"
    SANCTION = "Sanction"
    DROUGHT = "Drought"
    FLOOD = "Flood"
    PORT_CLOSURE = "Port Closure"
    STRIKE = "Strike"
    PANDEMIC = "Pandemic"
    EXPORT_BAN = "Export Ban"
    REGULATORY_CHANGE = "Regulatory Change"


@dataclass(frozen=True)
class GlobalEvent:
    event_id: str
    event_type: GlobalEventType
    title: str
    countries: tuple[str, ...]
    products: tuple[str, ...]
    routes: tuple[str, ...]
    severity_score: int
    confidence_score: int


@dataclass(frozen=True)
class GlobalEventImpact:
    event_id: str
    affected_entities: tuple[str, ...]
    impact_score: int
    blocking: bool
    recommended_actions: tuple[str, ...]
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class GlobalEventEngine:
    def evaluate(
        self,
        event: GlobalEvent,
    ) -> GlobalEventImpact:
        impact = round(
            event.severity_score * 0.70
            + event.confidence_score * 0.30
        )
        impact = max(0, min(100, impact))

        actions: list[str] = [
            "Revalidate affected suppliers and logistics routes.",
            "Refresh landed cost and delivery timing.",
            "Escalate compliance review where applicable.",
        ]

        if event.event_type in {
            GlobalEventType.SANCTION,
            GlobalEventType.EXPORT_BAN,
            GlobalEventType.PORT_CLOSURE,
        }:
            actions.append(
                "Block affected execution paths until cleared."
            )

        entities = tuple(
            dict.fromkeys(
                [
                    *event.countries,
                    *event.products,
                    *event.routes,
                ]
            )
        )

        return GlobalEventImpact(
            event_id=event.event_id,
            affected_entities=entities,
            impact_score=impact,
            blocking=impact >= 80,
            recommended_actions=tuple(actions),
            explanation=(
                f"Global event impact is {impact}/100 across "
                f"{len(entities)} affected entity reference(s)."
            ),
        )


_engine = GlobalEventEngine()


def get_global_event_engine() -> GlobalEventEngine:
    return _engine