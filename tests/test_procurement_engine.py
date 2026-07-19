"""Tests for Phase 21 Package F procurement engine."""
from __future__ import annotations
import pytest
from app.orchestration import BuyerDemand, BuyerReadiness, ProcurementEngine, ProcurementPolicy, ProcurementStatus, QuotationCompliance, SupplierQuotation, WorkflowStateError

def build_engine()->ProcurementEngine:
    return ProcurementEngine(policy=ProcurementPolicy(policy_id="procurement",name="Procurement",minimum_compliant_quotations=1))
def build_demand(readiness:BuyerReadiness=BuyerReadiness.UNVERIFIED)->BuyerDemand:
    return BuyerDemand(buyer_id="BUY-100",product_name="Premium Basmati Rice",quantity=1000,unit="kg",destination_country="au",readiness=readiness)
def build_quotation(quotation_id:str="Q-100",compliance:QuotationCompliance=QuotationCompliance.PENDING)->SupplierQuotation:
    return SupplierQuotation(supplier_id="SUP-100",quotation_id=quotation_id,unit_price=2.5,currency="usd",incoterm="cif",lead_time_days=30,landed_cost=3.2,compliance=compliance,score=92)

def test_create_case()->None:
    engine=build_engine(); case=engine.create_case(build_demand())
    assert case.status is ProcurementStatus.DRAFT
def test_buyer_readiness_update()->None:
    engine=build_engine(); case=engine.create_case(build_demand())
    updated=engine.set_buyer_readiness(case.case_id,BuyerReadiness.COMMITTED)
    assert updated.demand.readiness is BuyerReadiness.COMMITTED
def test_requirements_confirmation_requires_commitment()->None:
    engine=build_engine(); case=engine.create_case(build_demand())
    with pytest.raises(WorkflowStateError): engine.transition(case.case_id,ProcurementStatus.REQUIREMENTS_CONFIRMED)
def test_requirements_confirmation_after_commitment()->None:
    engine=build_engine(); case=engine.create_case(build_demand())
    case=engine.set_buyer_readiness(case.case_id,BuyerReadiness.COMMITTED)
    assert engine.transition(case.case_id,ProcurementStatus.REQUIREMENTS_CONFIRMED).status is ProcurementStatus.REQUIREMENTS_CONFIRMED
def test_add_quotation()->None:
    engine=build_engine(); case=engine.create_case(build_demand())
    assert len(engine.add_quotation(case.case_id,build_quotation()).quotations)==1
def test_select_only_compliant_quotation()->None:
    engine=build_engine(); case=engine.create_case(build_demand()); case=engine.add_quotation(case.case_id,build_quotation())
    with pytest.raises(WorkflowStateError): engine.select_quotation(case.case_id,"Q-100")
def test_select_compliant_quotation()->None:
    engine=build_engine(); case=engine.create_case(build_demand())
    case=engine.add_quotation(case.case_id,build_quotation(compliance=QuotationCompliance.COMPLIANT))
    assert engine.select_quotation(case.case_id,"Q-100").selected_quotation_id=="Q-100"
def test_purchase_order_requires_payment_and_selection()->None:
    engine=build_engine(); case=engine.create_case(build_demand())
    with pytest.raises(WorkflowStateError): engine.issue_purchase_order(case.case_id,"PO-100")
def test_full_procurement_control_flow()->None:
    engine=build_engine(); case=engine.create_case(build_demand())
    case=engine.set_buyer_readiness(case.case_id,BuyerReadiness.COMMITTED)
    case=engine.transition(case.case_id,ProcurementStatus.REQUIREMENTS_CONFIRMED)
    case=engine.add_quotation(case.case_id,build_quotation(compliance=QuotationCompliance.COMPLIANT))
    case=engine.select_quotation(case.case_id,"Q-100")
    case=engine.record_approval(case.case_id,"APR-100")
    case=engine.record_payment_clearance(case.case_id,"PAY-100")
    case=engine.issue_purchase_order(case.case_id,"PO-100")
    case=engine.handoff_to_shipment(case.case_id,"SHP-100")
    assert case.status is ProcurementStatus.SHIPMENT_HANDOFF
    assert len(case.events)>=7