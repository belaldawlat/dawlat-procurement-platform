"""Immutable models for the enterprise AI agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class EnterpriseAgentStatus(str, Enum):
    REGISTERED = "registered"
    IDLE = "idle"
    RUNNING = "running"
    DEGRADED = "degraded"
    PAUSED = "paused"
    FAILED = "failed"
    DISABLED = "disabled"


class EnterpriseAgentTaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class EnterpriseAgentCapability(str, Enum):
    PROCUREMENT = "procurement"
    SUPPLIER_ANALYSIS = "supplier_analysis"
    QUOTATION_ANALYSIS = "quotation_analysis"
    RISK_ANALYSIS = "risk_analysis"
    SHIPMENT_MONITORING = "shipment_monitoring"
    INVENTORY_PLANNING = "inventory_planning"
    DOCUMENT_VALIDATION = "document_validation"
    PAYMENT_CONTROL = "payment_control"
    OPPORTUNITY_ANALYSIS = "opportunity_analysis"
    APPROVAL_COORDINATION = "approval_coordination"


@dataclass(frozen=True)
class EnterpriseAgentDefinition:
    agent_id: str
    name: str
    capabilities: tuple[EnterpriseAgentCapability, ...]
    maximum_concurrency: int = 1
    status: EnterpriseAgentStatus = EnterpriseAgentStatus.IDLE
    version: str = "1.0.0"
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.agent_id or "").strip():
            raise ValueError("Enterprise agent ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise agent name is required.")
        if not self.capabilities:
            raise ValueError("Enterprise agent requires at least one capability.")
        if self.maximum_concurrency < 1:
            raise ValueError("Maximum concurrency must be at least 1.")

        object.__setattr__(self, "agent_id", str(self.agent_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "version", str(self.version or "1.0.0").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))


@dataclass(frozen=True)
class EnterpriseAgentTask:
    capability: EnterpriseAgentCapability
    entity_id: str
    payload: dict[str, Any]
    task_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    status: EnterpriseAgentTaskStatus = EnterpriseAgentTaskStatus.PENDING
    priority: int = 50
    assigned_agent_id: str = ""
    attempts: int = 0
    maximum_attempts: int = 3
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    correlation_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.task_id or "").strip():
            raise ValueError("Enterprise agent task ID is required.")
        if not str(self.entity_id or "").strip():
            raise ValueError("Enterprise agent task entity ID is required.")
        if not 1 <= self.priority <= 100:
            raise ValueError("Enterprise agent task priority must be between 1 and 100.")
        if self.attempts < 0:
            raise ValueError("Task attempts cannot be negative.")
        if self.maximum_attempts < 1:
            raise ValueError("Maximum attempts must be at least 1.")
        if self.attempts > self.maximum_attempts:
            raise ValueError("Task attempts cannot exceed maximum attempts.")

        object.__setattr__(self, "task_id", str(self.task_id).strip())
        object.__setattr__(self, "entity_id", str(self.entity_id).strip())
        object.__setattr__(
            self,
            "assigned_agent_id",
            str(self.assigned_agent_id or "").strip(),
        )
        object.__setattr__(
            self,
            "correlation_id",
            str(self.correlation_id or "").strip(),
        )
        object.__setattr__(self, "payload", redact_mapping(self.payload))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            EnterpriseAgentTaskStatus.COMPLETED,
            EnterpriseAgentTaskStatus.FAILED,
            EnterpriseAgentTaskStatus.CANCELLED,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "capability": self.capability.value,
            "entity_id": self.entity_id,
            "status": self.status.value,
            "priority": self.priority,
            "assigned_agent_id": self.assigned_agent_id,
            "attempts": self.attempts,
            "maximum_attempts": self.maximum_attempts,
            "created_at": self.created_at,
            "correlation_id": self.correlation_id,
            "payload": redact_mapping(self.payload),
            "metadata": redact_mapping(self.metadata),
        }