"""Immutable models for enterprise procurement intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping


class IntelligencePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IntelligenceCategory(str, Enum):
    BUYER = "buyer"
    SUPPLIER = "supplier"
    QUOTATION = "quotation"
    LANDED_COST = "landed_cost"
    RISK = "risk"
    SHIPMENT = "shipment"
    INVENTORY = "inventory"
    OPPORTUNITY = "opportunity"
    CASH_FLOW = "cash_flow"
    COMPLIANCE = "compliance"


class RecommendationType(str, Enum):
    SELECT_SUPPLIER = "select_supplier"
    NEGOTIATE_PRICE = "negotiate_price"
    HOLD_PROCUREMENT = "hold_procurement"
    ESCALATE_RISK = "escalate_risk"
    COMPLETE_DOCUMENTS = "complete_documents"
    SECURE_PAYMENT = "secure_payment"
    EXPEDITE_SHIPMENT = "expedite_shipment"
    REPLENISH_INVENTORY = "replenish_inventory"
    PRIORITISE_BUYER = "prioritise_buyer"
    PURSUE_OPPORTUNITY = "pursue_opportunity"
    NO_ACTION = "no_action"


@dataclass(frozen=True)
class SupplierIntelligenceInput:
    supplier_id: str
    supplier_name: str
    quotation_id: str
    landed_cost: float
    quality_score: float
    reliability_score: float
    compliance_score: float
    risk_score: float
    lead_time_days: int
    currency: str = "AUD"
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.supplier_id or "").strip():
            raise ValueError("Supplier ID is required.")
        if not str(self.supplier_name or "").strip():
            raise ValueError("Supplier name is required.")
        if not str(self.quotation_id or "").strip():
            raise ValueError("Quotation ID is required.")
        if self.landed_cost < 0:
            raise ValueError("Landed cost cannot be negative.")
        if self.lead_time_days < 0:
            raise ValueError("Lead time cannot be negative.")

        for name, value in {
            "quality_score": self.quality_score,
            "reliability_score": self.reliability_score,
            "compliance_score": self.compliance_score,
            "risk_score": self.risk_score,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100.")

        object.__setattr__(self, "supplier_id", str(self.supplier_id).strip())
        object.__setattr__(self, "supplier_name", str(self.supplier_name).strip())
        object.__setattr__(self, "quotation_id", str(self.quotation_id).strip())
        object.__setattr__(self, "currency", str(self.currency or "AUD").strip().upper())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))


@dataclass(frozen=True)
class ProcurementIntelligenceContext:
    buyer_priority_score: float = 50.0
    buyer_payment_cleared: bool = False
    documents_complete: bool = True
    shipment_delay_days: int = 0
    inventory_days_remaining: float | None = None
    opportunity_score: float = 0.0
    margin_percentage: float | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in {
            "buyer_priority_score": self.buyer_priority_score,
            "opportunity_score": self.opportunity_score,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100.")

        if self.shipment_delay_days < 0:
            raise ValueError("Shipment delay days cannot be negative.")
        if (
            self.inventory_days_remaining is not None
            and self.inventory_days_remaining < 0
        ):
            raise ValueError("Inventory days remaining cannot be negative.")

        object.__setattr__(self, "metadata", redact_mapping(self.metadata))


@dataclass(frozen=True)
class ProcurementRecommendation:
    recommendation_type: RecommendationType
    title: str
    rationale: str
    priority: IntelligencePriority
    category: IntelligenceCategory
    expected_value_score: float
    action_required: bool = True
    supplier_id: str = ""
    quotation_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.title or "").strip():
            raise ValueError("Recommendation title is required.")
        if not str(self.rationale or "").strip():
            raise ValueError("Recommendation rationale is required.")
        if not 0 <= self.expected_value_score <= 100:
            raise ValueError("Expected value score must be between 0 and 100.")

        object.__setattr__(self, "title", str(self.title).strip())
        object.__setattr__(self, "rationale", str(self.rationale).strip())
        object.__setattr__(self, "supplier_id", str(self.supplier_id or "").strip())
        object.__setattr__(self, "quotation_id", str(self.quotation_id or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "recommendation_type": self.recommendation_type.value,
            "title": self.title,
            "rationale": self.rationale,
            "priority": self.priority.value,
            "category": self.category.value,
            "expected_value_score": self.expected_value_score,
            "action_required": self.action_required,
            "supplier_id": self.supplier_id,
            "quotation_id": self.quotation_id,
            "metadata": redact_mapping(self.metadata),
        }