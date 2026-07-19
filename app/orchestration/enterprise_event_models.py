"""Immutable models for the enterprise event bus."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class EnterpriseEventStatus(str, Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    REPLAYED = "replayed"


class EnterpriseEventPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class EnterpriseEvent:
    event_type: str
    aggregate_id: str
    payload: dict[str, Any]
    event_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    topic: str = "enterprise"
    version: str = "1.0.0"
    correlation_id: str = ""
    causation_id: str = ""
    priority: EnterpriseEventPriority = EnterpriseEventPriority.NORMAL
    status: EnterpriseEventStatus = EnterpriseEventStatus.PENDING
    occurred_at: str = dataclass_field(default_factory=utc_timestamp)
    attempts: int = 0
    maximum_attempts: int = 3
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        for label, value in {
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "event_id": self.event_id,
            "topic": self.topic,
            "version": self.version,
        }.items():
            if not str(value or "").strip():
                raise ValueError(f"{label} is required.")

        if self.attempts < 0:
            raise ValueError("Event attempts cannot be negative.")
        if self.maximum_attempts < 1:
            raise ValueError("Maximum attempts must be at least 1.")
        if self.attempts > self.maximum_attempts:
            raise ValueError("Event attempts cannot exceed maximum attempts.")

        object.__setattr__(self, "event_type", str(self.event_type).strip())
        object.__setattr__(self, "aggregate_id", str(self.aggregate_id).strip())
        object.__setattr__(self, "event_id", str(self.event_id).strip())
        object.__setattr__(self, "topic", str(self.topic).strip())
        object.__setattr__(self, "version", str(self.version).strip())
        object.__setattr__(self, "correlation_id", str(self.correlation_id or "").strip())
        object.__setattr__(self, "causation_id", str(self.causation_id or "").strip())
        object.__setattr__(self, "payload", redact_mapping(self.payload))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            EnterpriseEventStatus.DELIVERED,
            EnterpriseEventStatus.DEAD_LETTERED,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "topic": self.topic,
            "version": self.version,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "occurred_at": self.occurred_at,
            "attempts": self.attempts,
            "maximum_attempts": self.maximum_attempts,
            "payload": redact_mapping(self.payload),
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseEventSubscription:
    subscription_id: str
    event_type: str
    topic: str = "*"
    enabled: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.subscription_id or "").strip():
            raise ValueError("Subscription ID is required.")
        if not str(self.event_type or "").strip():
            raise ValueError("Subscription event type is required.")
        if not str(self.topic or "").strip():
            raise ValueError("Subscription topic is required.")

        object.__setattr__(self, "subscription_id", str(self.subscription_id).strip())
        object.__setattr__(self, "event_type", str(self.event_type).strip())
        object.__setattr__(self, "topic", str(self.topic).strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))