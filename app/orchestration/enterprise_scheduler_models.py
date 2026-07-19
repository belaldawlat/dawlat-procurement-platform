"""Immutable models for the enterprise procurement scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class SchedulerPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class SchedulerTaskStatus(str, Enum):
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class SchedulerTaskType(str, Enum):
    PROCUREMENT = "procurement"
    APPROVAL = "approval"
    SUPPLIER_REVIEW = "supplier_review"
    QUOTATION_REVIEW = "quotation_review"
    PAYMENT_CHECK = "payment_check"
    DOCUMENT_CHECK = "document_check"
    SHIPMENT = "shipment"
    INVENTORY = "inventory"
    COMPENSATION = "compensation"
    RISK_REVIEW = "risk_review"
    OPPORTUNITY_REVIEW = "opportunity_review"


@dataclass(frozen=True)
class SchedulerResource:
    resource_id: str
    name: str
    capacity: int
    supported_task_types: tuple[SchedulerTaskType, ...]
    active_load: int = 0
    enabled: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.resource_id or "").strip():
            raise ValueError("Scheduler resource ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Scheduler resource name is required.")
        if self.capacity < 1:
            raise ValueError("Scheduler resource capacity must be at least 1.")
        if self.active_load < 0:
            raise ValueError("Scheduler resource active load cannot be negative.")
        if self.active_load > self.capacity:
            raise ValueError("Scheduler resource active load cannot exceed capacity.")
        if not self.supported_task_types:
            raise ValueError("Scheduler resource must support at least one task type.")

        object.__setattr__(self, "resource_id", str(self.resource_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "supported_task_types", tuple(self.supported_task_types))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def available_capacity(self) -> int:
        return max(0, self.capacity - self.active_load)

    @property
    def utilisation_rate(self) -> float:
        return round((self.active_load / self.capacity) * 100.0, 2)


@dataclass(frozen=True)
class SchedulerTask:
    task_type: SchedulerTaskType
    entity_id: str
    priority: SchedulerPriority = SchedulerPriority.NORMAL
    task_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    status: SchedulerTaskStatus = SchedulerTaskStatus.QUEUED
    estimated_duration_seconds: int = 60
    required_capacity: int = 1
    deadline_at: str = ""
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    attempts: int = 0
    maximum_attempts: int = 3
    payload: dict[str, Any] = dataclass_field(default_factory=dict)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.task_id or "").strip():
            raise ValueError("Scheduler task ID is required.")
        if not str(self.entity_id or "").strip():
            raise ValueError("Scheduler task entity ID is required.")
        if self.estimated_duration_seconds < 1:
            raise ValueError("Estimated duration must be at least one second.")
        if self.required_capacity < 1:
            raise ValueError("Required capacity must be at least 1.")
        if self.attempts < 0:
            raise ValueError("Task attempts cannot be negative.")
        if self.maximum_attempts < 1:
            raise ValueError("Maximum attempts must be at least 1.")
        if self.attempts > self.maximum_attempts:
            raise ValueError("Task attempts cannot exceed maximum attempts.")

        object.__setattr__(self, "task_id", str(self.task_id).strip())
        object.__setattr__(self, "entity_id", str(self.entity_id).strip())
        object.__setattr__(self, "deadline_at", str(self.deadline_at or "").strip())
        object.__setattr__(self, "payload", redact_mapping(self.payload))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            SchedulerTaskStatus.COMPLETED,
            SchedulerTaskStatus.FAILED,
            SchedulerTaskStatus.CANCELLED,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "entity_id": self.entity_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "required_capacity": self.required_capacity,
            "deadline_at": self.deadline_at,
            "created_at": self.created_at,
            "attempts": self.attempts,
            "maximum_attempts": self.maximum_attempts,
            "payload": redact_mapping(self.payload),
            "metadata": redact_mapping(self.metadata),
        }