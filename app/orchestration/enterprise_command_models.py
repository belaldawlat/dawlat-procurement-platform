"""Immutable models for the enterprise command center."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping


class CommandCenterHealth(str, Enum):
    """Executive health states."""

    HEALTHY = "healthy"
    WATCH = "watch"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class CommandCenterPriority(str, Enum):
    """Priority assigned to executive actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CommandCenterDomain(str, Enum):
    """Enterprise domains represented in the command center."""

    PROCUREMENT = "procurement"
    SUPPLIER = "supplier"
    SHIPMENT = "shipment"
    FINANCIAL = "financial"
    INVENTORY = "inventory"
    RISK = "risk"
    COMPLIANCE = "compliance"
    OPPORTUNITY = "opportunity"
    EXECUTION = "execution"
    AUTONOMY = "autonomy"


class ExecutiveAction(str, Enum):
    """Executive actions emitted by the command center."""

    NO_ACTION = "no_action"
    MONITOR = "monitor"
    INVESTIGATE = "investigate"
    ESCALATE = "escalate"
    PAUSE_EXECUTION = "pause_execution"
    REQUEST_APPROVAL = "request_approval"
    SECURE_PAYMENT = "secure_payment"
    COMPLETE_DOCUMENTS = "complete_documents"
    EXPEDITE_SHIPMENT = "expedite_shipment"
    REPLENISH_INVENTORY = "replenish_inventory"
    START_COMPENSATION = "start_compensation"
    PRIORITISE_OPPORTUNITY = "prioritise_opportunity"


@dataclass(frozen=True)
class ExecutiveKPI:
    """One command-center KPI."""

    kpi_id: str
    name: str
    domain: CommandCenterDomain
    value: float
    unit: str = ""
    target: float | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.kpi_id or "").strip():
            raise ValueError("Executive KPI ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Executive KPI name is required.")

        object.__setattr__(self, "kpi_id", str(self.kpi_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "unit", str(self.unit or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "kpi_id": self.kpi_id,
            "name": self.name,
            "domain": self.domain.value,
            "value": self.value,
            "unit": self.unit,
            "target": self.target,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class ExecutiveDirective:
    """One executive directive."""

    code: str
    title: str
    rationale: str
    domain: CommandCenterDomain
    priority: CommandCenterPriority
    action: ExecutiveAction
    blocking: bool = False
    entity_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("Executive directive code is required.")
        if not str(self.title or "").strip():
            raise ValueError("Executive directive title is required.")
        if not str(self.rationale or "").strip():
            raise ValueError("Executive directive rationale is required.")

        object.__setattr__(self, "code", str(self.code).strip())
        object.__setattr__(self, "title", str(self.title).strip())
        object.__setattr__(self, "rationale", str(self.rationale).strip())
        object.__setattr__(self, "entity_id", str(self.entity_id or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "rationale": self.rationale,
            "domain": self.domain.value,
            "priority": self.priority.value,
            "action": self.action.value,
            "blocking": self.blocking,
            "entity_id": self.entity_id,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseCommandSnapshot:
    """Enterprise-wide inputs consumed by the command center."""

    portfolio_id: str
    active_procurements: int
    blocked_procurements: int
    pending_approvals: int
    delayed_shipments: int
    critical_risks: int
    compensation_cases: int
    low_inventory_items: int
    high_value_opportunities: int
    procurement_value: float
    financial_exposure: float
    average_decision_score: float
    average_autonomous_confidence: float
    payment_clearance_rate: float
    document_completeness_rate: float
    on_time_shipment_rate: float
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.portfolio_id or "").strip():
            raise ValueError("Portfolio ID is required.")

        for name, value in {
            "active_procurements": self.active_procurements,
            "blocked_procurements": self.blocked_procurements,
            "pending_approvals": self.pending_approvals,
            "delayed_shipments": self.delayed_shipments,
            "critical_risks": self.critical_risks,
            "compensation_cases": self.compensation_cases,
            "low_inventory_items": self.low_inventory_items,
            "high_value_opportunities": self.high_value_opportunities,
        }.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative.")

        for name, value in {
            "average_decision_score": self.average_decision_score,
            "average_autonomous_confidence": self.average_autonomous_confidence,
            "payment_clearance_rate": self.payment_clearance_rate,
            "document_completeness_rate": self.document_completeness_rate,
            "on_time_shipment_rate": self.on_time_shipment_rate,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100.")

        if self.procurement_value < 0:
            raise ValueError("Procurement value cannot be negative.")

        if self.financial_exposure < 0:
            raise ValueError("Financial exposure cannot be negative.")

        object.__setattr__(
            self,
            "portfolio_id",
            str(self.portfolio_id).strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )