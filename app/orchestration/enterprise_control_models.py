"""Immutable models for the enterprise control tower."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping


class ControlHealth(str, Enum):
    """Operational health states for enterprise control views."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ControlPriority(str, Enum):
    """Priority assigned to enterprise control alerts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ControlDomain(str, Enum):
    """Enterprise domains monitored by the control tower."""

    PROCUREMENT = "procurement"
    APPROVAL = "approval"
    EXECUTION = "execution"
    SUPPLIER = "supplier"
    SHIPMENT = "shipment"
    INVENTORY = "inventory"
    FINANCIAL = "financial"
    RISK = "risk"
    COMPLIANCE = "compliance"
    OPPORTUNITY = "opportunity"
    AUTONOMY = "autonomy"


class ControlAction(str, Enum):
    """Actions recommended by the enterprise control tower."""

    MONITOR = "monitor"
    INVESTIGATE = "investigate"
    ESCALATE = "escalate"
    REQUEST_APPROVAL = "request_approval"
    PAUSE_EXECUTION = "pause_execution"
    RESUME_EXECUTION = "resume_execution"
    START_COMPENSATION = "start_compensation"
    COMPLETE_DOCUMENTS = "complete_documents"
    SECURE_PAYMENT = "secure_payment"
    EXPEDITE_SHIPMENT = "expedite_shipment"
    REPLENISH_INVENTORY = "replenish_inventory"
    NO_ACTION = "no_action"


@dataclass(frozen=True)
class EnterpriseControlMetric:
    """One normalised enterprise control metric."""

    metric_id: str
    name: str
    domain: ControlDomain
    value: float
    unit: str = ""
    target: float | None = None
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    higher_is_better: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        metric_id = str(self.metric_id or "").strip()
        name = str(self.name or "").strip()

        if not metric_id:
            raise ValueError("Control metric ID is required.")

        if not name:
            raise ValueError("Control metric name is required.")

        object.__setattr__(self, "metric_id", metric_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "unit",
            str(self.unit or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "domain": self.domain.value,
            "value": self.value,
            "unit": self.unit,
            "target": self.target,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "higher_is_better": self.higher_is_better,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseControlAlert:
    """One enterprise control alert."""

    code: str
    title: str
    message: str
    domain: ControlDomain
    priority: ControlPriority
    action: ControlAction
    blocking: bool = False
    entity_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("Control alert code is required.")

        if not str(self.title or "").strip():
            raise ValueError("Control alert title is required.")

        if not str(self.message or "").strip():
            raise ValueError("Control alert message is required.")

        object.__setattr__(self, "code", str(self.code).strip())
        object.__setattr__(self, "title", str(self.title).strip())
        object.__setattr__(self, "message", str(self.message).strip())
        object.__setattr__(
            self,
            "entity_id",
            str(self.entity_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "code": self.code,
            "title": self.title,
            "message": self.message,
            "domain": self.domain.value,
            "priority": self.priority.value,
            "action": self.action.value,
            "blocking": self.blocking,
            "entity_id": self.entity_id,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseControlSnapshot:
    """Operational inputs consumed by the control tower."""

    case_id: str
    procurement_status: str
    approval_satisfied: bool
    execution_allowed: bool
    compensation_required: bool
    autonomous_confidence: float
    decision_score: float
    supplier_risk_score: float = 0.0
    shipment_delay_days: int = 0
    inventory_days_remaining: float | None = None
    buyer_payment_cleared: bool = False
    documents_complete: bool = True
    opportunity_score: float = 0.0
    margin_percentage: float | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise ValueError("Control snapshot case ID is required.")

        for name, value in {
            "autonomous_confidence": self.autonomous_confidence,
            "decision_score": self.decision_score,
            "supplier_risk_score": self.supplier_risk_score,
            "opportunity_score": self.opportunity_score,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(
                    f"{name} must be between 0 and 100."
                )

        if self.shipment_delay_days < 0:
            raise ValueError(
                "Shipment delay days cannot be negative."
            )

        if (
            self.inventory_days_remaining is not None
            and self.inventory_days_remaining < 0
        ):
            raise ValueError(
                "Inventory days remaining cannot be negative."
            )

        object.__setattr__(
            self,
            "case_id",
            str(self.case_id).strip(),
        )
        object.__setattr__(
            self,
            "procurement_status",
            str(self.procurement_status or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )