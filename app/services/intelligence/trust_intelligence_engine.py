"""
Enterprise Trust Intelligence Engine.

This module is the final commercial trust gate for the Dawlat AI Procurement
& Global Trade Intelligence Platform.

It evaluates whether Dawlat Global may safely proceed with:
- supplier commitment;
- buyer quotation acceptance;
- supplier payment release;
- shipment instruction;
- delivery acceptance;
- final reconciliation.

Core principle:
No supplier commitment or payment release is allowed before buyer acceptance,
cleared buyer funds, protected margin, verified supplier identity and bank
details, approved contracts, complete compliance evidence and authorised human
approval.

The engine is deterministic, explainable and read-only. It never executes a
commercial, legal, financial or logistics action automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from models.decision import (
    ApprovalStatus,
    BuyerReadinessStatus,
    EnterpriseDecision,
    PaymentStage,
    PaymentStatus,
    RiskSeverity,
    SupplierCommitmentStatus,
)
from services.intelligence.risk_intelligence_engine import (
    RiskAssessment,
    assess_enterprise_risk,
)


class TrustDecision(str, Enum):
    APPROVE = "Approve"
    APPROVE_WITH_CONDITIONS = "Approve With Conditions"
    HOLD = "Hold"
    BLOCK = "Block"
    REJECT = "Reject"


class TrustDomain(str, Enum):
    BUYER = "Buyer Trust"
    SUPPLIER = "Supplier Trust"
    COMMERCIAL = "Commercial Trust"
    PAYMENT = "Payment Trust"
    OPERATIONAL = "Operational Trust"
    COMPLIANCE = "Compliance Trust"
    DOCUMENTATION = "Documentation Trust"
    RELATIONSHIP = "Relationship Trust"
    CYBER = "Cyber & Fraud Trust"
    GOVERNANCE = "Governance Trust"


@dataclass(frozen=True)
class TrustControl:
    domain: TrustDomain
    control_name: str
    passed: bool
    blocking: bool
    score: int
    maximum: int
    reason: str
    required_action: str
    owner_role: str
    evidence_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrustDomainScore:
    domain: TrustDomain
    score: int
    maximum: int
    percentage: int
    status: str
    blocking_failures: int
    control_count: int


@dataclass(frozen=True)
class TrustAction:
    priority: int
    action: str
    owner_role: str
    reason: str
    blocking: bool
    approval_required: bool = False


@dataclass
class TrustAssessment:
    decision_id: str
    overall_score: int
    trust_decision: TrustDecision
    executive_summary: str
    controls: list[TrustControl] = field(default_factory=list)
    domain_scores: list[TrustDomainScore] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    outstanding_actions: list[TrustAction] = field(default_factory=list)
    evidence_summary: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    confidence_score: int = 0
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocking_reasons)

    def supplier_commitment_allowed(self) -> bool:
        return (
            self.trust_decision
            in {
                TrustDecision.APPROVE,
                TrustDecision.APPROVE_WITH_CONDITIONS,
            }
            and not self.is_blocked
        )

    def supplier_payment_allowed(
        self,
        decision: EnterpriseDecision,
        *,
        stage: PaymentStage,
    ) -> bool:
        if not self.supplier_commitment_allowed():
            return False

        return decision.supplier_payment_release_allowed(stage)


class TrustIntelligenceEngine:
    """Final enterprise trust and commercial protection gate."""

    def assess(
        self,
        decision: EnterpriseDecision,
        *,
        risk_assessment: RiskAssessment | None = None,
    ) -> TrustAssessment:
        risk = risk_assessment or assess_enterprise_risk(decision)

        controls: list[TrustControl] = []
        controls.extend(self._buyer_controls(decision))
        controls.extend(self._supplier_controls(decision))
        controls.extend(self._commercial_controls(decision))
        controls.extend(self._payment_controls(decision))
        controls.extend(self._operational_controls(decision))
        controls.extend(self._compliance_controls(decision))
        controls.extend(self._documentation_controls(decision))
        controls.extend(self._relationship_controls(decision))
        controls.extend(self._cyber_controls(decision))
        controls.extend(self._governance_controls(decision))

        domain_scores = self._domain_scores(controls)
        overall_score = self._overall_score(domain_scores)

        blocking_reasons = [
            control.reason
            for control in controls
            if control.blocking and not control.passed
        ]

        blocking_reasons.extend(
            reason
            for reason in risk.blocking_reasons
            if reason not in blocking_reasons
        )

        trust_decision = self._decision(
            overall_score=overall_score,
            blocking_reasons=blocking_reasons,
            controls=controls,
            risk=risk,
        )

        actions = self._actions(controls, risk)

        confidence_score = self._confidence(
            decision=decision,
            risk=risk,
            controls=controls,
        )

        return TrustAssessment(
            decision_id=decision.decision_id,
            overall_score=overall_score,
            trust_decision=trust_decision,
            executive_summary=self._summary(
                decision=decision,
                trust_decision=trust_decision,
                overall_score=overall_score,
                blocking_reasons=blocking_reasons,
                risk=risk,
            ),
            controls=controls,
            domain_scores=domain_scores,
            blocking_reasons=list(dict.fromkeys(blocking_reasons)),
            outstanding_actions=actions,
            evidence_summary=[
                f"{item.source}: {item.label}"
                for item in decision.evidence[:20]
            ],
            assumptions=list(decision.assumptions),
            confidence_score=confidence_score,
        )

    @staticmethod
    def _buyer_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        buyer = decision.buyer_commitment

        if buyer is None:
            return [
                _control(
                    TrustDomain.BUYER,
                    "Buyer commitment exists",
                    False,
                    True,
                    0,
                    20,
                    "No buyer commitment record exists.",
                    "Create and verify the buyer commitment record.",
                    "Customer Acquisition Manager",
                )
            ]

        return [
            _control(
                TrustDomain.BUYER,
                "Buyer legal identity verified",
                buyer.identity_verified,
                True,
                20 if buyer.identity_verified else 0,
                20,
                (
                    "Buyer identity is verified."
                    if buyer.identity_verified
                    else "Buyer identity is not verified."
                ),
                "Verify company registration and authorised representative.",
                "Compliance Manager",
            ),
            _control(
                TrustDomain.BUYER,
                "Buyer requirement confirmed",
                bool(
                    buyer.product
                    and buyer.quantity > 0
                    and buyer.delivery_location
                ),
                True,
                20
                if (
                    buyer.product
                    and buyer.quantity > 0
                    and buyer.delivery_location
                )
                else 0,
                20,
                "Buyer requirement must be complete and final.",
                "Confirm product, quantity, specifications and delivery terms.",
                "Sales Manager",
            ),
            _control(
                TrustDomain.BUYER,
                "Final quotation accepted in writing",
                buyer.accepted_in_writing,
                True,
                25 if buyer.accepted_in_writing else 0,
                25,
                (
                    "Buyer accepted the final quotation."
                    if buyer.accepted_in_writing
                    else "Buyer has not accepted the final quotation in writing."
                ),
                "Capture written acceptance of the exact quotation version.",
                "Sales Manager",
            ),
            _control(
                TrustDomain.BUYER,
                "Buyer funds cleared",
                (
                    buyer.status == BuyerReadinessStatus.FUNDS_CLEARED
                    and (buyer.cleared_funds or 0) > 0
                ),
                True,
                25
                if (
                    buyer.status == BuyerReadinessStatus.FUNDS_CLEARED
                    and (buyer.cleared_funds or 0) > 0
                )
                else 0,
                25,
                (
                    "Buyer funds are cleared."
                    if buyer.status == BuyerReadinessStatus.FUNDS_CLEARED
                    else "Buyer funds are not cleared."
                ),
                "Confirm cleared funds or approved payment security.",
                "Finance Approver",
            ),
            _control(
                TrustDomain.BUYER,
                "Buyer credit and sanctions checks complete",
                buyer.credit_checked and buyer.sanctions_checked,
                True,
                10
                if buyer.credit_checked and buyer.sanctions_checked
                else 0,
                10,
                "Buyer credit and compliance screening must be complete.",
                "Complete credit, sanctions and adverse-media checks.",
                "Compliance Manager",
            ),
        ]

    @staticmethod
    def _supplier_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        supplier = decision.supplier_offer

        if supplier is None:
            return [
                _control(
                    TrustDomain.SUPPLIER,
                    "Supplier selected",
                    False,
                    True,
                    0,
                    20,
                    "No supplier offer is selected.",
                    "Select and compare verified supplier offers.",
                    "Global Sourcing Specialist",
                )
            ]

        status_allowed = supplier.commitment_status in {
            SupplierCommitmentStatus.APPROVED,
            SupplierCommitmentStatus.CONTRACT_PENDING,
            SupplierCommitmentStatus.COMMITTED,
        }

        return [
            _control(
                TrustDomain.SUPPLIER,
                "Supplier identity and capability verified",
                supplier.supplier_verified,
                True,
                30 if supplier.supplier_verified else 0,
                30,
                (
                    "Supplier is verified."
                    if supplier.supplier_verified
                    else "Supplier identity or capability is not verified."
                ),
                "Verify legal entity, factory, capacity and export history.",
                "Global Sourcing Specialist",
            ),
            _control(
                TrustDomain.SUPPLIER,
                "Supplier bank details verified",
                supplier.bank_details_verified,
                True,
                25 if supplier.bank_details_verified else 0,
                25,
                (
                    "Supplier bank details are verified."
                    if supplier.bank_details_verified
                    else "Supplier bank details are not independently verified."
                ),
                "Verify bank details using an independent trusted channel.",
                "Finance Approver",
            ),
            _control(
                TrustDomain.SUPPLIER,
                "Supplier certificates recorded",
                bool(supplier.certificates),
                True,
                15 if supplier.certificates else 0,
                15,
                (
                    "Supplier certificates are recorded."
                    if supplier.certificates
                    else "Supplier certificates are missing."
                ),
                "Obtain and validate all required certificates.",
                "Compliance Manager",
            ),
            _control(
                TrustDomain.SUPPLIER,
                "Supplier lead time confirmed",
                supplier.lead_time_days > 0,
                True,
                10 if supplier.lead_time_days > 0 else 0,
                10,
                "Supplier lead time must be confirmed.",
                "Obtain written production and dispatch lead time.",
                "Procurement Specialist",
            ),
            _control(
                TrustDomain.SUPPLIER,
                "Supplier commitment status approved",
                status_allowed,
                True,
                10 if status_allowed else 0,
                10,
                "Supplier commitment status is not approved.",
                "Complete supplier approval before commitment.",
                "Managing Director",
            ),
            _control(
                TrustDomain.SUPPLIER,
                "Product sample approved",
                supplier.sample_approved,
                False,
                10 if supplier.sample_approved else 0,
                10,
                (
                    "Product sample is approved."
                    if supplier.sample_approved
                    else "Product sample is not approved."
                ),
                "Approve a representative product sample.",
                "Quality Manager",
            ),
        ]

    @staticmethod
    def _commercial_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        margin = decision.margin_protection

        if margin is None:
            return [
                _control(
                    TrustDomain.COMMERCIAL,
                    "Margin analysis complete",
                    False,
                    True,
                    0,
                    40,
                    "Margin protection analysis is missing.",
                    "Complete and approve full landed-cost analysis.",
                    "Commercial Manager",
                )
            ]

        contingency_ok = margin.contingency > 0
        finance_cost_ok = margin.finance_cost >= 0

        return [
            _control(
                TrustDomain.COMMERCIAL,
                "Minimum margin protected",
                margin.margin_protected,
                True,
                45 if margin.margin_protected else 0,
                45,
                (
                    "Approved minimum margin is protected."
                    if margin.margin_protected
                    else "Expected margin is below the approved minimum."
                ),
                "Reprice, renegotiate or stop the deal.",
                "Commercial Manager",
            ),
            _control(
                TrustDomain.COMMERCIAL,
                "Landed cost approved",
                margin.buyer_total_value > 0
                and margin.supplier_total_cost >= 0,
                True,
                25
                if (
                    margin.buyer_total_value > 0
                    and margin.supplier_total_cost >= 0
                )
                else 0,
                25,
                "Buyer value and supplier cost must be confirmed.",
                "Complete the approved landed-cost calculation.",
                "Cost & Profit Analyst",
            ),
            _control(
                TrustDomain.COMMERCIAL,
                "Contingency included",
                contingency_ok,
                False,
                15 if contingency_ok else 0,
                15,
                (
                    "Commercial contingency is included."
                    if contingency_ok
                    else "No commercial contingency is included."
                ),
                "Add an approved contingency allowance.",
                "Commercial Manager",
            ),
            _control(
                TrustDomain.COMMERCIAL,
                "Finance costs considered",
                finance_cost_ok,
                False,
                15 if finance_cost_ok else 0,
                15,
                "Finance cost calculation must be reviewed.",
                "Confirm FX, bank and transaction costs.",
                "Finance Approver",
            ),
        ]

    @staticmethod
    def _payment_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        if not decision.payment_milestones:
            return [
                _control(
                    TrustDomain.PAYMENT,
                    "Payment milestones defined",
                    False,
                    True,
                    0,
                    40,
                    "Supplier payment milestones are not defined.",
                    "Create evidence-based payment milestones.",
                    "Finance Approver",
                )
            ]

        milestones_valid = all(
            item.amount > 0
            and item.required_evidence
            for item in decision.payment_milestones
        )

        approvals_valid = all(
            item.finance_approval == ApprovalStatus.APPROVED
            and item.management_approval == ApprovalStatus.APPROVED
            for item in decision.payment_milestones
        )

        no_unsafe_release = all(
            not (
                item.status == PaymentStatus.RELEASED
                and (
                    not item.conditions_satisfied
                    or item.finance_approval != ApprovalStatus.APPROVED
                    or item.management_approval != ApprovalStatus.APPROVED
                )
            )
            for item in decision.payment_milestones
        )

        return [
            _control(
                TrustDomain.PAYMENT,
                "Payment milestones complete",
                milestones_valid,
                True,
                35 if milestones_valid else 0,
                35,
                "Each payment milestone must have a valid amount and evidence.",
                "Complete milestone amounts and evidence requirements.",
                "Finance Approver",
            ),
            _control(
                TrustDomain.PAYMENT,
                "Milestone approvals complete",
                approvals_valid,
                True,
                35 if approvals_valid else 0,
                35,
                "Finance and management approvals are required.",
                "Obtain finance and management approval.",
                "Managing Director",
            ),
            _control(
                TrustDomain.PAYMENT,
                "No unsafe payment release detected",
                no_unsafe_release,
                True,
                30 if no_unsafe_release else 0,
                30,
                (
                    "No unsafe payment release detected."
                    if no_unsafe_release
                    else "A payment was released without all controls."
                ),
                "Freeze the deal and investigate the payment.",
                "Managing Director",
            ),
        ]

    @staticmethod
    def _operational_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        metadata = decision.metadata

        return [
            _control(
                TrustDomain.OPERATIONAL,
                "Logistics confirmed",
                bool(metadata.get("logistics_confirmed", False)),
                True,
                30 if metadata.get("logistics_confirmed", False) else 0,
                30,
                "Logistics route and capacity must be confirmed.",
                "Obtain a valid freight quotation and booking plan.",
                "Logistics Coordinator",
            ),
            _control(
                TrustDomain.OPERATIONAL,
                "Shipment readiness confirmed",
                bool(metadata.get("shipment_ready", False)),
                True,
                25 if metadata.get("shipment_ready", False) else 0,
                25,
                "Shipment readiness is not confirmed.",
                "Confirm production, booking, documents and dispatch readiness.",
                "Logistics Coordinator",
            ),
            _control(
                TrustDomain.OPERATIONAL,
                "Warehouse and delivery capacity confirmed",
                bool(metadata.get("warehouse_confirmed", False)),
                False,
                20 if metadata.get("warehouse_confirmed", False) else 0,
                20,
                "Warehouse or delivery capacity is not confirmed.",
                "Confirm receiving, storage and local delivery capacity.",
                "Warehouse Manager",
            ),
            _control(
                TrustDomain.OPERATIONAL,
                "No active shipment hold",
                not bool(metadata.get("shipment_delayed", False)),
                False,
                25 if not metadata.get("shipment_delayed", False) else 0,
                25,
                (
                    "No active shipment hold detected."
                    if not metadata.get("shipment_delayed", False)
                    else "A shipment delay or hold is active."
                ),
                "Create and approve a recovery plan.",
                "Logistics Coordinator",
            ),
        ]

    @staticmethod
    def _compliance_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        metadata = decision.metadata

        return [
            _control(
                TrustDomain.COMPLIANCE,
                "Import and biosecurity requirements verified",
                bool(
                    metadata.get(
                        "import_requirements_verified",
                        False,
                    )
                ),
                True,
                35
                if metadata.get(
                    "import_requirements_verified",
                    False,
                )
                else 0,
                35,
                "Import and biosecurity requirements are not verified.",
                "Confirm current customs, DAFF and biosecurity requirements.",
                "Compliance Manager",
            ),
            _control(
                TrustDomain.COMPLIANCE,
                "Required certificates valid",
                not bool(
                    metadata.get(
                        "certificate_expiry_detected",
                        False,
                    )
                ),
                True,
                30
                if not metadata.get(
                    "certificate_expiry_detected",
                    False,
                )
                else 0,
                30,
                (
                    "No certificate expiry detected."
                    if not metadata.get(
                        "certificate_expiry_detected",
                        False,
                    )
                    else "A required certificate is expired or near expiry."
                ),
                "Obtain and independently verify valid certificates.",
                "Compliance Manager",
            ),
            _control(
                TrustDomain.COMPLIANCE,
                "Country and sanctions screening complete",
                bool(
                    metadata.get(
                        "country_risk_verified",
                        False,
                    )
                ),
                True,
                20
                if metadata.get(
                    "country_risk_verified",
                    False,
                )
                else 0,
                20,
                "Country and sanctions screening is incomplete.",
                "Complete country, sanctions and trade-restriction checks.",
                "Compliance Manager",
            ),
            _control(
                TrustDomain.COMPLIANCE,
                "Insurance confirmed",
                bool(metadata.get("insurance_active", False)),
                False,
                15 if metadata.get("insurance_active", False) else 0,
                15,
                "Cargo or transaction insurance is not confirmed.",
                "Confirm appropriate insurance coverage.",
                "Risk Manager",
            ),
        ]

    @staticmethod
    def _documentation_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        evidence_count = len(decision.evidence)
        document_hashes = [
            item.document_hash
            for item in decision.evidence
            if item.document_hash
        ]

        return [
            _control(
                TrustDomain.DOCUMENTATION,
                "Supporting evidence attached",
                evidence_count > 0,
                True,
                min(60, evidence_count * 10),
                60,
                (
                    f"{evidence_count} evidence record(s) attached."
                    if evidence_count
                    else "No supporting evidence is attached."
                ),
                "Attach quotations, contracts, certificates and payment evidence.",
                "Documentation Specialist",
                evidence_labels=tuple(
                    item.label
                    for item in decision.evidence[:10]
                ),
            ),
            _control(
                TrustDomain.DOCUMENTATION,
                "Critical documents integrity protected",
                bool(document_hashes),
                False,
                40 if document_hashes else 0,
                40,
                (
                    "Document integrity hashes are recorded."
                    if document_hashes
                    else "Document integrity hashes are not recorded."
                ),
                "Store immutable hashes for critical documents.",
                "Security Administrator",
            ),
        ]

    @staticmethod
    def _relationship_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        metadata = decision.metadata

        bypass_risk = bool(
            metadata.get("relationship_bypass_risk", False)
        )
        nda_active = bool(metadata.get("nda_active", False))
        non_circumvention_active = bool(
            metadata.get("non_circumvention_active", False)
        )

        return [
            _control(
                TrustDomain.RELATIONSHIP,
                "No active bypass risk",
                not bypass_risk,
                True,
                35 if not bypass_risk else 0,
                35,
                (
                    "No bypass risk detected."
                    if not bypass_risk
                    else "Buyer or supplier bypass risk is detected."
                ),
                "Use controlled communication and commercial safeguards.",
                "Commercial Manager",
            ),
            _control(
                TrustDomain.RELATIONSHIP,
                "Confidentiality protection active",
                nda_active,
                False,
                30 if nda_active else 0,
                30,
                "Confidentiality protection should be active.",
                "Execute an appropriate confidentiality agreement.",
                "Commercial Manager",
            ),
            _control(
                TrustDomain.RELATIONSHIP,
                "Non-circumvention protection active",
                non_circumvention_active,
                False,
                35 if non_circumvention_active else 0,
                35,
                "Non-circumvention protection should be active.",
                "Use approved non-circumvention terms where appropriate.",
                "Commercial Manager",
            ),
        ]

    @staticmethod
    def _cyber_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        metadata = decision.metadata

        bank_changed = bool(metadata.get("bank_details_changed", False))
        email_mismatch = bool(metadata.get("email_domain_mismatch", False))
        duplicate_invoice = bool(
            metadata.get("duplicate_invoice_detected", False)
        )
        secure_channel = bool(
            metadata.get("secure_communication_verified", False)
        )

        return [
            _control(
                TrustDomain.CYBER,
                "No bank-detail change alert",
                not bank_changed,
                True,
                30 if not bank_changed else 0,
                30,
                (
                    "No bank-detail change alert."
                    if not bank_changed
                    else "Supplier bank details changed during the deal."
                ),
                "Freeze payment and reverify through a trusted channel.",
                "Finance Approver",
            ),
            _control(
                TrustDomain.CYBER,
                "Verified company email domain",
                not email_mismatch,
                True,
                25 if not email_mismatch else 0,
                25,
                (
                    "No email-domain mismatch detected."
                    if not email_mismatch
                    else "Email domain does not match the verified company."
                ),
                "Stop communication and verify the sender independently.",
                "Security Administrator",
            ),
            _control(
                TrustDomain.CYBER,
                "No duplicate invoice alert",
                not duplicate_invoice,
                True,
                25 if not duplicate_invoice else 0,
                25,
                (
                    "No duplicate invoice detected."
                    if not duplicate_invoice
                    else "A possible duplicate invoice was detected."
                ),
                "Block payment and reconcile invoice references.",
                "Finance Approver",
            ),
            _control(
                TrustDomain.CYBER,
                "Secure communication channel verified",
                secure_channel,
                False,
                20 if secure_channel else 0,
                20,
                "Secure communication channel should be verified.",
                "Use approved accounts and verified contact channels.",
                "Security Administrator",
            ),
        ]

    @staticmethod
    def _governance_controls(
        decision: EnterpriseDecision,
    ) -> list[TrustControl]:
        approvals_exist = bool(decision.approvals)
        approvals_complete = bool(
            decision.approvals
            and all(
                item.status in {
                    ApprovalStatus.APPROVED,
                    ApprovalStatus.NOT_REQUIRED,
                }
                for item in decision.approvals
            )
        )
        no_rejected = not any(
            item.status == ApprovalStatus.REJECTED
            for item in decision.approvals
        )
        no_expired = not any(
            item.status in {
                ApprovalStatus.EXPIRED,
                ApprovalStatus.REVOKED,
            }
            for item in decision.approvals
        )

        return [
            _control(
                TrustDomain.GOVERNANCE,
                "Approval workflow exists",
                approvals_exist,
                True,
                20 if approvals_exist else 0,
                20,
                "Approval workflow must exist.",
                "Create the required approval records.",
                "Managing Director",
            ),
            _control(
                TrustDomain.GOVERNANCE,
                "Required approvals complete",
                approvals_complete,
                True,
                40 if approvals_complete else 0,
                40,
                "Required approvals are incomplete.",
                "Obtain all required authorised approvals.",
                "Managing Director",
            ),
            _control(
                TrustDomain.GOVERNANCE,
                "No rejected approval",
                no_rejected,
                True,
                20 if no_rejected else 0,
                20,
                (
                    "No rejected approval."
                    if no_rejected
                    else "A mandatory approval was rejected."
                ),
                "Resolve the rejection before proceeding.",
                "Managing Director",
            ),
            _control(
                TrustDomain.GOVERNANCE,
                "No expired or revoked approval",
                no_expired,
                True,
                20 if no_expired else 0,
                20,
                (
                    "No expired or revoked approval."
                    if no_expired
                    else "A required approval is expired or revoked."
                ),
                "Request a new authorised approval.",
                "Managing Director",
            ),
        ]

    @staticmethod
    def _domain_scores(
        controls: list[TrustControl],
    ) -> list[TrustDomainScore]:
        result = []

        for domain in TrustDomain:
            items = [
                item
                for item in controls
                if item.domain == domain
            ]

            maximum = sum(item.maximum for item in items)
            score = sum(item.score for item in items)
            percentage = round(
                score / maximum * 100
                if maximum
                else 0
            )
            blocking_failures = sum(
                1
                for item in items
                if item.blocking and not item.passed
            )

            if blocking_failures:
                status = "Blocked"
            elif percentage >= 85:
                status = "Strong"
            elif percentage >= 70:
                status = "Acceptable"
            elif percentage >= 50:
                status = "Weak"
            else:
                status = "Critical"

            result.append(
                TrustDomainScore(
                    domain=domain,
                    score=score,
                    maximum=maximum,
                    percentage=percentage,
                    status=status,
                    blocking_failures=blocking_failures,
                    control_count=len(items),
                )
            )

        return result

    @staticmethod
    def _overall_score(
        domain_scores: list[TrustDomainScore],
    ) -> int:
        if not domain_scores:
            return 0

        weighted = {
            TrustDomain.BUYER: 15,
            TrustDomain.SUPPLIER: 15,
            TrustDomain.COMMERCIAL: 15,
            TrustDomain.PAYMENT: 15,
            TrustDomain.OPERATIONAL: 10,
            TrustDomain.COMPLIANCE: 10,
            TrustDomain.DOCUMENTATION: 5,
            TrustDomain.RELATIONSHIP: 5,
            TrustDomain.CYBER: 5,
            TrustDomain.GOVERNANCE: 5,
        }

        score = sum(
            item.percentage
            * weighted[item.domain]
            / 100
            for item in domain_scores
        )

        return max(0, min(100, round(score)))

    @staticmethod
    def _decision(
        *,
        overall_score: int,
        blocking_reasons: list[str],
        controls: list[TrustControl],
        risk: RiskAssessment,
    ) -> TrustDecision:
        if blocking_reasons:
            return TrustDecision.BLOCK

        if risk.overall_severity == RiskSeverity.CRITICAL:
            return TrustDecision.REJECT

        if overall_score >= 90:
            return TrustDecision.APPROVE

        if overall_score >= 75:
            return TrustDecision.APPROVE_WITH_CONDITIONS

        if overall_score >= 55:
            return TrustDecision.HOLD

        return TrustDecision.REJECT

    @staticmethod
    def _actions(
        controls: list[TrustControl],
        risk: RiskAssessment,
    ) -> list[TrustAction]:
        actions = []
        priority = 1

        failed = [
            item
            for item in controls
            if not item.passed
        ]

        failed.sort(
            key=lambda item: (
                not item.blocking,
                item.domain.value,
                item.control_name,
            )
        )

        for item in failed:
            actions.append(
                TrustAction(
                    priority=priority,
                    action=item.required_action,
                    owner_role=item.owner_role,
                    reason=item.reason,
                    blocking=item.blocking,
                    approval_required=item.blocking,
                )
            )
            priority += 1

        for mitigation in risk.mitigations:
            if any(
                action.action == mitigation
                for action in actions
            ):
                continue

            actions.append(
                TrustAction(
                    priority=priority,
                    action=mitigation,
                    owner_role="Risk Manager",
                    reason="Risk mitigation required.",
                    blocking=False,
                    approval_required=False,
                )
            )
            priority += 1

        return actions[:30]

    @staticmethod
    def _confidence(
        *,
        decision: EnterpriseDecision,
        risk: RiskAssessment,
        controls: list[TrustControl],
    ) -> int:
        evidence_score = min(
            25,
            len(decision.evidence) * 3,
        )
        control_coverage = round(
            sum(
                1
                for item in controls
                if item.passed
            )
            / len(controls)
            * 35
            if controls
            else 0
        )
        decision_score = round(
            decision.confidence_score * 0.25
        )
        risk_score = round(
            risk.confidence_score * 0.15
        )

        score = (
            evidence_score
            + control_coverage
            + decision_score
            + risk_score
        )

        score -= min(
            25,
            len(decision.data_gaps) * 5,
        )

        return max(0, min(100, score))

    @staticmethod
    def _summary(
        *,
        decision: EnterpriseDecision,
        trust_decision: TrustDecision,
        overall_score: int,
        blocking_reasons: list[str],
        risk: RiskAssessment,
    ) -> str:
        supplier_name = (
            decision.supplier_offer.supplier_name
            if decision.supplier_offer
            else "No supplier selected"
        )
        buyer_name = (
            decision.buyer_commitment.buyer_name
            if decision.buyer_commitment
            else "No buyer confirmed"
        )

        return (
            f"Trust decision: {trust_decision.value}. "
            f"Overall trust score: {overall_score}/100. "
            f"Buyer: {buyer_name}. Supplier: {supplier_name}. "
            f"Risk score: {risk.overall_score}/100. "
            f"Blocking issue(s): {len(blocking_reasons)}. "
            "No supplier commitment or payment release is permitted "
            "unless all blocking controls are resolved."
        )


def _control(
    domain: TrustDomain,
    control_name: str,
    passed: bool,
    blocking: bool,
    score: int,
    maximum: int,
    reason: str,
    required_action: str,
    owner_role: str,
    *,
    evidence_labels: tuple[str, ...] = (),
) -> TrustControl:
    return TrustControl(
        domain=domain,
        control_name=control_name,
        passed=passed,
        blocking=blocking,
        score=max(0, min(maximum, score)),
        maximum=maximum,
        reason=reason,
        required_action=required_action,
        owner_role=owner_role,
        evidence_labels=evidence_labels,
    )


_engine = TrustIntelligenceEngine()


def assess_enterprise_trust(
    decision: EnterpriseDecision,
    *,
    risk_assessment: RiskAssessment | None = None,
) -> TrustAssessment:
    """Public trust-assessment entry point."""

    return _engine.assess(
        decision,
        risk_assessment=risk_assessment,
    )