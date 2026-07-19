"""Enterprise procurement workflow execution engine."""
from __future__ import annotations
from dataclasses import replace
from typing import Any
from app.observability.logging_config import get_logger
from app.orchestration.exceptions import WorkflowStateError, WorkflowValidationError
from app.orchestration.procurement_events import ProcurementEvent
from app.orchestration.procurement_models import BuyerDemand, BuyerReadiness, ProcurementCase, ProcurementStatus, QuotationCompliance, SupplierQuotation
from app.orchestration.procurement_policy import ProcurementPolicy
from app.orchestration.procurement_store import InMemoryProcurementStore
from app.orchestration.procurement_validator import ProcurementValidator

class ProcurementEngine:
    def __init__(self,*,store:InMemoryProcurementStore|None=None,policy:ProcurementPolicy|None=None,validator:ProcurementValidator|None=None)->None:
        self._store=store or InMemoryProcurementStore()
        self._policy=policy or ProcurementPolicy(policy_id="default-procurement",name="Default Procurement Policy")
        self._validator=validator or ProcurementValidator()
        self._logger=get_logger("orchestration.procurement_engine")
    @property
    def store(self)->InMemoryProcurementStore: return self._store
    def create_case(self,demand:BuyerDemand,*,metadata:dict[str,Any]|None=None)->ProcurementCase:
        case=ProcurementCase(demand=demand,metadata=metadata or {})
        result=self._validator.validate(case)
        if not result.valid: raise WorkflowValidationError(technical_message="Procurement case validation failed.")
        self._store.create(case); return case
    def set_buyer_readiness(self,case_id:str,readiness:BuyerReadiness,*,actor_id:str="")->ProcurementCase:
        case=self._store.get(case_id)
        updated=replace(case,demand=replace(case.demand,readiness=readiness),status=ProcurementStatus.BUYER_QUALIFICATION)
        return self._save_with_event(updated,"buyer_readiness_updated",actor_id,{"readiness":readiness.value})
    def transition(self,case_id:str,target_status:ProcurementStatus,*,actor_id:str="")->ProcurementCase:
        case=self._store.get(case_id)
        violations=self._policy.validate_transition(case,target_status)
        if violations:
            raise WorkflowStateError(
                technical_message="Procurement transition rejected.",
                metadata={"case_id":case.case_id,"target_status":target_status.value,"violations":[{"code":v.code,"message":v.message} for v in violations]},
            )
        return self._save_with_event(case.with_status(target_status),"status_changed",actor_id,{"from":case.status.value,"to":target_status.value})
    def add_quotation(self,case_id:str,quotation:SupplierQuotation,*,actor_id:str="")->ProcurementCase:
        case=self._store.get(case_id)
        return self._save_with_event(case.add_quotation(quotation),"quotation_added",actor_id,{"quotation_id":quotation.quotation_id})
    def mark_quotation_compliance(self,case_id:str,quotation_id:str,compliance:QuotationCompliance,*,actor_id:str="")->ProcurementCase:
        case=self._store.get(case_id); updated=[]; found=False
        for q in case.quotations:
            if q.quotation_id==quotation_id:
                updated.append(replace(q,compliance=compliance)); found=True
            else: updated.append(q)
        if not found: raise WorkflowValidationError(technical_message="Quotation was not found.")
        return self._save_with_event(replace(case,quotations=tuple(updated)),"quotation_compliance_updated",actor_id,{"quotation_id":quotation_id,"compliance":compliance.value})
    def select_quotation(self,case_id:str,quotation_id:str,*,actor_id:str="")->ProcurementCase:
        case=self._store.get(case_id)
        selected=next((q for q in case.quotations if q.quotation_id==quotation_id),None)
        if selected is None: raise WorkflowValidationError(technical_message="Selected quotation was not found.")
        if selected.compliance is not QuotationCompliance.COMPLIANT: raise WorkflowStateError(technical_message="Only compliant quotations may be selected.")
        return self._save_with_event(replace(case,selected_quotation_id=quotation_id),"quotation_selected",actor_id,{"quotation_id":quotation_id})
    def record_approval(self,case_id:str,approval_request_id:str,*,actor_id:str="")->ProcurementCase:
        case=self._store.get(case_id)
        updated=replace(case,approval_request_id=str(approval_request_id or "").strip())
        return self._save_with_event(updated,"commercial_approval_recorded",actor_id,{"approval_request_id":updated.approval_request_id})
    def record_payment_clearance(self,case_id:str,payment_reference:str,*,actor_id:str="")->ProcurementCase:
        case=self._store.get(case_id)
        updated=replace(case,payment_reference=str(payment_reference or "").strip(),status=ProcurementStatus.PAYMENT_CLEARED)
        return self._save_with_event(updated,"payment_cleared",actor_id,{"payment_reference":updated.payment_reference})
    def issue_purchase_order(self,case_id:str,purchase_order_id:str,*,actor_id:str="")->ProcurementCase:
        case=self._store.get(case_id)
        violations=self._policy.validate_transition(case,ProcurementStatus.PURCHASE_ORDER_ISSUED)
        if violations: raise WorkflowStateError(technical_message="Purchase order issuance rejected by policy.")
        updated=replace(case,purchase_order_id=str(purchase_order_id or "").strip(),status=ProcurementStatus.PURCHASE_ORDER_ISSUED)
        return self._save_with_event(updated,"purchase_order_issued",actor_id,{"purchase_order_id":updated.purchase_order_id})
    def handoff_to_shipment(self,case_id:str,shipment_reference:str,*,actor_id:str="")->ProcurementCase:
        case=self._store.get(case_id)
        if not case.purchase_order_id: raise WorkflowStateError(technical_message="Purchase order is required before shipment handoff.")
        updated=replace(case,shipment_reference=str(shipment_reference or "").strip(),status=ProcurementStatus.SHIPMENT_HANDOFF)
        return self._save_with_event(updated,"shipment_handoff",actor_id,{"shipment_reference":updated.shipment_reference})
    def _save_with_event(self,case:ProcurementCase,event_type:str,actor_id:str,data:dict[str,Any])->ProcurementCase:
        event=ProcurementEvent(event_type=event_type,case_id=case.case_id,actor_id=actor_id,data=data)
        updated=replace(case,events=(*case.events,event.as_dict()))
        self._store.save(updated); return updated

_default_procurement_engine=ProcurementEngine()
def get_procurement_engine()->ProcurementEngine: return _default_procurement_engine