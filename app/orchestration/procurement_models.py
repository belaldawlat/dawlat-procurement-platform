"""Immutable enterprise procurement workflow models."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field as dataclass_field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4
from app.observability.redaction import redact_mapping

def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

class ProcurementStatus(str, Enum):
    DRAFT="draft"; BUYER_QUALIFICATION="buyer_qualification"; REQUIREMENTS_CONFIRMED="requirements_confirmed"
    SUPPLIER_SOURCING="supplier_sourcing"; RFQ_OPEN="rfq_open"; QUOTATIONS_RECEIVED="quotations_received"
    COMPLIANCE_REVIEW="compliance_review"; COMMERCIAL_APPROVAL="commercial_approval"
    PAYMENT_PENDING="payment_pending"; PAYMENT_CLEARED="payment_cleared"
    PURCHASE_ORDER_ISSUED="purchase_order_issued"; SHIPMENT_HANDOFF="shipment_handoff"
    COMPLETED="completed"; FAILED="failed"; CANCELLED="cancelled"

class BuyerReadiness(str, Enum):
    UNVERIFIED="unverified"; QUALIFIED="qualified"; COMMITTED="committed"; REJECTED="rejected"

class QuotationCompliance(str, Enum):
    PENDING="pending"; COMPLIANT="compliant"; NON_COMPLIANT="non_compliant"

@dataclass(frozen=True)
class BuyerDemand:
    buyer_id: str
    product_name: str
    quantity: float
    unit: str
    destination_country: str
    target_delivery_date: str = ""
    budget_amount: float | None = None
    budget_currency: str = "AUD"
    readiness: BuyerReadiness = BuyerReadiness.UNVERIFIED
    requirements: dict[str, Any] = dataclass_field(default_factory=dict)
    def __post_init__(self) -> None:
        if not str(self.buyer_id or "").strip(): raise ValueError("Buyer ID is required.")
        if not str(self.product_name or "").strip(): raise ValueError("Product name is required.")
        if self.quantity <= 0: raise ValueError("Demand quantity must be greater than zero.")
        if not str(self.unit or "").strip(): raise ValueError("Demand unit is required.")
        if not str(self.destination_country or "").strip(): raise ValueError("Destination country is required.")
        if self.budget_amount is not None and self.budget_amount < 0: raise ValueError("Budget amount cannot be negative.")
        object.__setattr__(self,"buyer_id",str(self.buyer_id).strip())
        object.__setattr__(self,"product_name",str(self.product_name).strip())
        object.__setattr__(self,"unit",str(self.unit).strip())
        object.__setattr__(self,"destination_country",str(self.destination_country).strip().upper())
        object.__setattr__(self,"budget_currency",str(self.budget_currency or "AUD").strip().upper())
        object.__setattr__(self,"requirements",redact_mapping(self.requirements))

@dataclass(frozen=True)
class SupplierQuotation:
    supplier_id: str
    quotation_id: str
    unit_price: float
    currency: str
    incoterm: str
    lead_time_days: int
    landed_cost: float | None = None
    compliance: QuotationCompliance = QuotationCompliance.PENDING
    score: float = 0.0
    notes: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    def __post_init__(self) -> None:
        if not str(self.supplier_id or "").strip(): raise ValueError("Supplier ID is required.")
        if not str(self.quotation_id or "").strip(): raise ValueError("Quotation ID is required.")
        if self.unit_price < 0: raise ValueError("Unit price cannot be negative.")
        if self.lead_time_days < 0: raise ValueError("Lead time cannot be negative.")
        if self.landed_cost is not None and self.landed_cost < 0: raise ValueError("Landed cost cannot be negative.")
        object.__setattr__(self,"supplier_id",str(self.supplier_id).strip())
        object.__setattr__(self,"quotation_id",str(self.quotation_id).strip())
        object.__setattr__(self,"currency",str(self.currency or "").strip().upper())
        object.__setattr__(self,"incoterm",str(self.incoterm or "").strip().upper())
        object.__setattr__(self,"notes",str(self.notes or "").strip())
        object.__setattr__(self,"metadata",redact_mapping(self.metadata))

@dataclass(frozen=True)
class ProcurementCase:
    demand: BuyerDemand
    case_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    status: ProcurementStatus = ProcurementStatus.DRAFT
    quotations: tuple[SupplierQuotation,...] = ()
    selected_quotation_id: str = ""
    approval_request_id: str = ""
    payment_reference: str = ""
    purchase_order_id: str = ""
    shipment_reference: str = ""
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    updated_at: str = dataclass_field(default_factory=utc_timestamp)
    events: tuple[dict[str,Any],...] = ()
    metadata: dict[str,Any] = dataclass_field(default_factory=dict)
    def __post_init__(self) -> None:
        object.__setattr__(self,"case_id",str(self.case_id or uuid4().hex).strip())
        object.__setattr__(self,"quotations",tuple(self.quotations))
        object.__setattr__(self,"events",tuple(self.events))
        object.__setattr__(self,"metadata",redact_mapping(self.metadata))
    @property
    def selected_quotation(self) -> SupplierQuotation | None:
        return next((q for q in self.quotations if q.quotation_id==self.selected_quotation_id),None)
    @property
    def is_terminal(self) -> bool:
        return self.status in {ProcurementStatus.COMPLETED,ProcurementStatus.FAILED,ProcurementStatus.CANCELLED}
    def with_status(self,status:ProcurementStatus)->"ProcurementCase":
        return replace(self,status=status,updated_at=utc_timestamp())
    def add_quotation(self,quotation:SupplierQuotation)->"ProcurementCase":
        if any(q.quotation_id==quotation.quotation_id for q in self.quotations): raise ValueError("Quotation ID already exists in this procurement case.")
        return replace(self,quotations=(*self.quotations,quotation),updated_at=utc_timestamp())
    def as_dict(self)->dict[str,Any]:
        payload=asdict(self); payload["status"]=self.status.value; payload["demand"]["readiness"]=self.demand.readiness.value
        for q in payload["quotations"]: q["compliance"]=q["compliance"].value
        return payload