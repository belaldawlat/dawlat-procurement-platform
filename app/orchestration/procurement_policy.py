"""Deterministic policies for enterprise procurement workflows."""
from __future__ import annotations
from dataclasses import dataclass, field as dataclass_field
from typing import Any
from app.observability.redaction import redact_mapping
from app.orchestration.procurement_models import ProcurementCase, ProcurementStatus, QuotationCompliance

@dataclass(frozen=True)
class ProcurementPolicyViolation:
    code:str
    message:str
    field_name:str=""
    metadata:dict[str,Any]=dataclass_field(default_factory=dict)
    def __post_init__(self)->None:
        object.__setattr__(self,"code",str(self.code or "").strip())
        object.__setattr__(self,"message",str(self.message or "").strip())
        object.__setattr__(self,"field_name",str(self.field_name or "").strip())
        object.__setattr__(self,"metadata",redact_mapping(self.metadata))

@dataclass(frozen=True)
class ProcurementPolicy:
    policy_id:str
    name:str
    minimum_compliant_quotations:int=1
    require_buyer_commitment:bool=True
    require_commercial_approval:bool=True
    require_payment_clearance_before_po:bool=True
    require_selected_compliant_quotation:bool=True
    enabled:bool=True
    def __post_init__(self)->None:
        if not str(self.policy_id or "").strip(): raise ValueError("Procurement policy ID is required.")
        if not str(self.name or "").strip(): raise ValueError("Procurement policy name is required.")
        if self.minimum_compliant_quotations<1: raise ValueError("Minimum compliant quotations must be at least 1.")
        object.__setattr__(self,"policy_id",str(self.policy_id).strip())
        object.__setattr__(self,"name",str(self.name).strip())
    def validate_transition(self,case:ProcurementCase,target_status:ProcurementStatus)->tuple[ProcurementPolicyViolation,...]:
        v=[]
        if not self.enabled: v.append(ProcurementPolicyViolation("PROCUREMENT_POLICY_DISABLED","The procurement policy is disabled."))
        if case.is_terminal: v.append(ProcurementPolicyViolation("PROCUREMENT_CASE_TERMINAL","A terminal procurement case cannot transition."))
        if target_status is ProcurementStatus.REQUIREMENTS_CONFIRMED and self.require_buyer_commitment and case.demand.readiness.value!="committed":
            v.append(ProcurementPolicyViolation("BUYER_COMMITMENT_REQUIRED","Buyer commitment is required before confirming requirements.","demand.readiness"))
        if target_status is ProcurementStatus.COMMERCIAL_APPROVAL:
            count=sum(q.compliance is QuotationCompliance.COMPLIANT for q in case.quotations)
            if count<self.minimum_compliant_quotations:
                v.append(ProcurementPolicyViolation("INSUFFICIENT_COMPLIANT_QUOTATIONS","Not enough compliant quotations are available.",metadata={"required":self.minimum_compliant_quotations,"actual":count}))
        if target_status is ProcurementStatus.PAYMENT_PENDING and self.require_commercial_approval and not case.approval_request_id:
            v.append(ProcurementPolicyViolation("COMMERCIAL_APPROVAL_REQUIRED","Commercial approval is required before payment."))
        if target_status is ProcurementStatus.PURCHASE_ORDER_ISSUED:
            if self.require_payment_clearance_before_po and not case.payment_reference:
                v.append(ProcurementPolicyViolation("PAYMENT_CLEARANCE_REQUIRED","Buyer payment must clear before issuing a purchase order."))
            selected=case.selected_quotation
            if self.require_selected_compliant_quotation and (selected is None or selected.compliance is not QuotationCompliance.COMPLIANT):
                v.append(ProcurementPolicyViolation("COMPLIANT_QUOTATION_SELECTION_REQUIRED","A compliant supplier quotation must be selected."))
        return tuple(sorted(v,key=lambda x:(x.code,x.field_name)))