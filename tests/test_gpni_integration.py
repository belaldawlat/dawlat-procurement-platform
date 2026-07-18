"""Integration tests for GPNI safeguards."""
from __future__ import annotations
from services.network_intelligence.commercial_safeguards_engine import (
    SafeguardDecision,
    get_commercial_safeguards_engine,
)
from services.network_intelligence.contract_readiness_engine import (
    ContractReadinessDecision,
    get_contract_readiness_engine,
)
from services.network_intelligence.payment_protection_engine import (
    PaymentDecision,
    get_payment_protection_engine,
)

def test_supplier_payment_is_blocked_without_cleared_buyer_funds() -> None:
    result = get_payment_protection_engine().evaluate({
        "buyer_funds_cleared": 0,
        "requested_supplier_release": 10000,
        "protected_profit": 1500,
        "protected_cost_buffer": 1000,
        "total_supplier_obligation": 10000,
        "bank_clearance_confirmed": False,
        "buyer_final_approval": True,
        "supplier_milestone_confirmed": True,
        "documents_verified": True,
        "compliance_cleared": True,
        "authorised_payment_approval": True,
    })
    assert result.decision == PaymentDecision.BLOCKED
    assert result.releasable_amount == 0

def test_low_margin_case_is_blocked() -> None:
    result = get_commercial_safeguards_engine().evaluate({
        "buyer_sale_value": 10000,
        "landed_cost": 9500,
        "supplier_commitment": 9000,
        "cleared_buyer_funds": 10000,
        "minimum_margin_percent": 15,
        "buyer_final_quotation_approved": True,
        "supplier_final_terms_confirmed": True,
        "compliance_cleared": True,
        "required_documents_confirmed": True,
        "currency_risk_reviewed": True,
        "insurance_reviewed": True,
        "protected_cost_buffer": 300,
        "minimum_profit_amount": 1500,
        "relationship_conflict_detected": False,
    })
    assert result.decision == SafeguardDecision.BLOCK

def test_contract_cannot_activate_without_signatures() -> None:
    required = {
        key: True
        for key in get_contract_readiness_engine().REQUIRED_ITEMS
    }
    required.update({
        "commercial_safeguards_passed": True,
        "payment_protection_passed": True,
        "sanctions_or_compliance_hold": False,
        "unresolved_material_risk": False,
        "relationship_conflict_detected": False,
        "authorised_buyer_signatory": True,
        "authorised_supplier_signatory": True,
        "buyer_signed": False,
        "supplier_signed": False,
        "cleared_funds_or_approved_credit": True,
    })
    result = get_contract_readiness_engine().evaluate(required)
    assert result.decision == ContractReadinessDecision.READY_FOR_SIGNATURE
    assert result.activation_allowed is False