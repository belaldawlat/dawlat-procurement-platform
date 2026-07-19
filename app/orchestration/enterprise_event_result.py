"""Results produced by the enterprise event bus."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_event_models import EnterpriseEvent


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseEventDelivery:
    event_id: str
    subscription_id: str
    successful: bool
    attempts: int
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "subscription_id": self.subscription_id,
            "successful": self.successful,
            "attempts": self.attempts,
            "error": self.error,
        }


@dataclass(frozen=True)
class EnterpriseEventBusResult:
    event: EnterpriseEvent
    deliveries: tuple[EnterpriseEventDelivery, ...]
    dead_lettered: bool
    published_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "deliveries", tuple(self.deliveries))
        object.__setattr__(self, "policy_id", str(self.policy_id or "").strip())
        object.__setattr__(self, "policy_version", str(self.policy_version or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def delivered_count(self) -> int:
        return sum(1 for delivery in self.deliveries if delivery.successful)

    @property
    def failed_count(self) -> int:
        return sum(1 for delivery in self.deliveries if not delivery.successful)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event": self.event.as_dict(),
            "deliveries": [delivery.as_dict() for delivery in self.deliveries],
            "dead_lettered": self.dead_lettered,
            "published_at": self.published_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "delivered_count": self.delivered_count,
            "failed_count": self.failed_count,
            "metadata": redact_mapping(self.metadata),
        }