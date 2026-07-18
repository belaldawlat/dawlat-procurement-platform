"""
Enterprise decision models for the Dawlat AI Procurement Intelligence Platform.

These models standardise buyer readiness, supplier commitment, payment release,
margin protection, risk, approvals, evidence and auditability.

Core rule:
No supplier commitment or payment release is allowed before buyer acceptance,
cleared funds, protected margin, verified supplier evidence and human approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DecisionType(str, Enum):
    BUYER_READINESS = "Buyer Readiness"
    SUPPLIER_MATCH = "Supplier Match"
    QUOTATION_APPROVAL = "Quotation Approval"
    DEAL_APPROVAL = "Deal Approval"
    PAYMENT_RELEASE = "Payment Release"
    SHIPMENT_RELEASE = "Shipment Release"
    DELIVERY_ACCEPTANCE = "Delivery Acceptance"
    EXECUTIVE_RECOMMENDATION = "Executive Recommendation"


class DecisionOutcome(str, Enum):
    APPROVED = "Approved"
    CONDITIONALLY_APPROVED = "Conditionally Approved"
    REJECTED = "Rejected"
    BLOCKED = "Blocked"
    PENDING_INFORMATION = "Pending Information"
    PENDING_APPROVAL = "Pending Approval"


class RiskSeverity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "Not Required"
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    REVOKED = "Revoked"


class BuyerReadinessStatus(str, Enum):
    UNQUALIFIED = "Unqualified"
    RESEARCHING = "Researching"
    QUALIFIED = "Qualified"
    QUOTATION_READY = "Quotation Ready"
    ACCEPTED = "Accepted"
    FUNDS_PENDING = "Funds Pending"
    FUNDS_CLEARED = "Funds Cleared"
    SUSPENDED = "Suspended"
    REJECTED = "Rejected"


class SupplierCommitmentStatus(str, Enum):
    NOT_SELECTED = "Not Selected"
    SHORTLISTED = "Shortlisted"
    SELECTED_PENDING_APPROVAL = "Selected Pending Approval"
    APPROVED = "Approved"
    CONTRACT_PENDING = "Contract Pending"
    COMMITTED = "Committed"
    SUSPENDED = "Suspended"
    CANCELLED = "Cancelled"


class PaymentStage(str, Enum):
    BUYER_DEPOSIT = "Buyer Deposit"
    BUYER_BALANCE = "Buyer Balance"
    SUPPLIER_DEPOSIT = "Supplier Deposit"
    PRODUCTION = "Production"
    PRE_SHIPMENT = "Pre-Shipment"
    SHIPPING_DOCUMENTS = "Shipping Documents"
    ARRIVAL = "Arrival"
    DELIVERY = "Delivery"
    FINAL_RECONCILIATION = "Final Reconciliation"


class PaymentStatus(str, Enum):
    NOT_DUE = "Not Due"
    PENDING = "Pending"
    RECEIVED_UNCLEARED = "Received Uncleared"
    CLEARED = "Cleared"
    APPROVED_FOR_RELEASE = "Approved for Release"
    RELEASED = "Released"
    HELD = "Held"
    FAILED = "Failed"
    REFUNDED = "Refunded"
    DISPUTED = "Disputed"


class EvidenceType(str, Enum):
    INTERNAL_RECORD = "Internal Record"
    BUYER_DOCUMENT = "Buyer Document"
    SUPPLIER_DOCUMENT = "Supplier Document"
    CONTRACT = "Contract"
    QUOTATION = "Quotation"
    PAYMENT_CONFIRMATION = "Payment Confirmation"
    CERTIFICATE = "Certificate"
    INSPECTION = "Inspection"
    SHIPPING_DOCUMENT = "Shipping Document"
    LIVE_SOURCE = "Live Source"
    HUMAN_VERIFICATION = "Human Verification"


@dataclass(frozen=True)
class EvidenceReference:
    evidence_type: EvidenceType
    source: str
    label: str
    details: str
    record_id: int | None = None
    url: str | None = None
    document_hash: str | None = None
    verified_by: str | None = None
    verified_at: str | None = None


@dataclass(frozen=True)
class RiskFinding:
    category: str
    severity: RiskSeverity
    description: str
    impact: str
    mitigation: str
    blocking: bool = False
    owner_role: str = ""


@dataclass(frozen=True)
class ApprovalRecord:
    approval_type: str
    status: ApprovalStatus
    requested_by: str
    requested_at: str
    approver_role: str
    approved_by: str | None = None
    approved_at: str | None = None
    reason: str = ""
    expires_at: str | None = None


@dataclass(frozen=True)
class BuyerCommercialCommitment:
    buyer_id: int | None
    buyer_name: str
    status: BuyerReadinessStatus
    product: str
    quantity: float
    unit: str
    specifications: str
    packaging: str
    required_certificates: tuple[str, ...]
    delivery_location: str
    required_delivery_date: str | None
    accepted_currency: str
    accepted_unit_price: float | None
    accepted_total_value: float | None
    payment_terms: str
    deposit_required: float | None
    deposit_received: float | None
    cleared_funds: float | None
    quotation_reference: str | None = None
    quotation_version: int | None = None
    accepted_in_writing: bool = False
    acceptance_reference: str | None = None
    identity_verified: bool = False
    credit_checked: bool = False
    sanctions_checked: bool = False
    notes: str = ""


@dataclass(frozen=True)
class SupplierCommercialOffer:
    supplier_id: int | None
    supplier_name: str
    commitment_status: SupplierCommitmentStatus
    product: str
    quantity: float
    unit: str
    currency: str
    unit_price: float
    total_goods_value: float
    incoterm: str
    origin: str
    destination: str
    lead_time_days: int
    validity_date: str | None
    payment_terms: str
    freight_included: bool
    insurance_included: bool
    customs_included: bool
    local_delivery_included: bool
    estimated_landed_cost: float | None
    certificates: tuple[str, ...] = ()
    documents: tuple[str, ...] = ()
    sample_approved: bool = False
    supplier_verified: bool = False
    bank_details_verified: bool = False
    notes: str = ""


@dataclass(frozen=True)
class MarginProtection:
    currency: str
    buyer_total_value: float
    supplier_total_cost: float
    freight_cost: float
    customs_and_duties: float
    warehouse_cost: float
    local_delivery_cost: float
    finance_cost: float
    contingency: float
    other_costs: float
    minimum_margin_percent: float
    expected_margin_percent: float
    expected_gross_profit: float
    margin_protected: bool
    approval_required: bool
    reason: str = ""


@dataclass(frozen=True)
class PaymentMilestone:
    stage: PaymentStage
    status: PaymentStatus
    payer: str
    payee: str
    currency: str
    amount: float
    due_date: str | None = None
    cleared_date: str | None = None
    released_date: str | None = None
    required_evidence: tuple[str, ...] = ()
    received_evidence: tuple[str, ...] = ()
    conditions_satisfied: bool = False
    finance_approval: ApprovalStatus = ApprovalStatus.PENDING
    management_approval: ApprovalStatus = ApprovalStatus.PENDING
    hold_reason: str = ""


@dataclass(frozen=True)
class DealControlGate:
    gate_name: str
    passed: bool
    blocking: bool
    reason: str
    required_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecommendedAction:
    priority: int
    action: str
    owner_role: str
    reason: str
    approval_required: bool = False
    blocking: bool = False
    due_at: str | None = None


@dataclass
class EnterpriseDecision:
    decision_id: str
    decision_type: DecisionType
    outcome: DecisionOutcome
    title: str
    executive_summary: str
    confidence_score: int
    created_by: str
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    buyer_commitment: BuyerCommercialCommitment | None = None
    supplier_offer: SupplierCommercialOffer | None = None
    margin_protection: MarginProtection | None = None
    control_gates: list[DealControlGate] = field(default_factory=list)
    payment_milestones: list[PaymentMilestone] = field(default_factory=list)
    risks: list[RiskFinding] = field(default_factory=list)
    approvals: list[ApprovalRecord] = field(default_factory=list)
    evidence: list[EvidenceReference] = field(default_factory=list)
    recommendations: list[RecommendedAction] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_blocking_failure(self) -> bool:
        return any(
            gate.blocking and not gate.passed
            for gate in self.control_gates
        ) or any(
            risk.blocking or risk.severity == RiskSeverity.CRITICAL
            for risk in self.risks
        )

    def buyer_funds_cleared(self) -> bool:
        return bool(
            self.buyer_commitment
            and self.buyer_commitment.status == BuyerReadinessStatus.FUNDS_CLEARED
            and (self.buyer_commitment.cleared_funds or 0) > 0
        )

    def supplier_commitment_allowed(self) -> bool:
        buyer = self.buyer_commitment
        margin = self.margin_protection
        approvals_ok = all(
            approval.status in {
                ApprovalStatus.APPROVED,
                ApprovalStatus.NOT_REQUIRED,
            }
            for approval in self.approvals
        )

        return bool(
            buyer
            and buyer.accepted_in_writing
            and buyer.identity_verified
            and self.buyer_funds_cleared()
            and margin
            and margin.margin_protected
            and approvals_ok
            and not self.has_blocking_failure()
        )

    def supplier_payment_release_allowed(
        self,
        stage: PaymentStage,
    ) -> bool:
        if not self.supplier_commitment_allowed():
            return False

        milestones = [
            item
            for item in self.payment_milestones
            if item.stage == stage
        ]
        return bool(
            milestones
            and all(
                item.conditions_satisfied
                and item.finance_approval == ApprovalStatus.APPROVED
                and item.management_approval == ApprovalStatus.APPROVED
                and item.status in {
                    PaymentStatus.CLEARED,
                    PaymentStatus.APPROVED_FOR_RELEASE,
                }
                for item in milestones
            )
        )

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "outcome": self.outcome.value,
            "title": self.title,
            "executive_summary": self.executive_summary,
            "confidence_score": self.confidence_score,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "has_blocking_failure": self.has_blocking_failure(),
            "supplier_commitment_allowed": self.supplier_commitment_allowed(),
            "risk_count": len(self.risks),
            "approval_count": len(self.approvals),
            "evidence_count": len(self.evidence),
            "data_gaps": list(self.data_gaps),
            "assumptions": list(self.assumptions),
            "metadata": dict(self.metadata),
        }


def default_deal_control_gates() -> list[DealControlGate]:
    return [
        DealControlGate(
            "Buyer identity verified",
            False,
            True,
            "Buyer legal identity and authorised contact must be verified.",
            ("Verify company identity.", "Verify authorised contact."),
        ),
        DealControlGate(
            "Buyer requirement confirmed",
            False,
            True,
            "Product, quantity, specifications and delivery terms must be final.",
            ("Confirm specifications.", "Confirm quantity and delivery date."),
        ),
        DealControlGate(
            "Buyer quotation accepted",
            False,
            True,
            "Written acceptance of the final quotation is required.",
            ("Issue version-controlled quotation.", "Capture written acceptance."),
        ),
        DealControlGate(
            "Buyer funds cleared",
            False,
            True,
            "Cleared buyer funds or approved payment security are required.",
            ("Verify cleared funds.", "Match payment to buyer and quotation."),
        ),
        DealControlGate(
            "Supplier verified",
            False,
            True,
            "Supplier identity, certificates and bank details must be verified.",
            ("Verify legal entity.", "Verify bank details independently."),
        ),
        DealControlGate(
            "Margin protected",
            False,
            True,
            "The approved minimum Dawlat Global margin must be preserved.",
            ("Complete landed cost.", "Confirm contingency and finance costs."),
        ),
        DealControlGate(
            "Contracts approved",
            False,
            True,
            "Buyer and supplier contracts must be approved.",
            ("Approve buyer agreement.", "Approve supplier purchase terms."),
        ),
        DealControlGate(
            "Payment milestones approved",
            False,
            True,
            "Supplier payments must be tied to evidence and milestones.",
            ("Define milestones.", "Assign finance and management approvals."),
        ),
    ]