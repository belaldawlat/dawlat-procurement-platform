"""Approval Policy Engine for the Autonomous Procurement Brain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ApprovalDecision(str, Enum):
    DENY = "Deny"
    HOLD = "Hold"
    REQUIRE_APPROVAL = "Require Approval"
    ALLOW = "Allow"


class ActionType(str, Enum):
    CONTACT_SUPPLIER = "Contact Supplier"
    SEND_BUYER_QUOTATION = "Send Buyer Quotation"
    START_NEGOTIATION = "Start Negotiation"
    ISSUE_PURCHASE_ORDER = "Issue Purchase Order"
    RELEASE_PAYMENT = "Release Payment"
    BOOK_SHIPMENT = "Book Shipment"
    ACTIVATE_CONTRACT = "Activate Contract"
    RESERVE_INVENTORY = "Reserve Inventory"


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    action_type: ActionType
    actor_role: str
    case_id: str
    buyer_verified: bool
    supplier_verified: bool
    compliance_cleared: bool
    buyer_final_approval: bool
    funds_cleared: bool
    documents_verified: bool
    contract_ready: bool
    margin_protected: bool
    authorised_human_approval: bool
    risk_score: int
    trust_score: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalResult:
    request_id: str
    decision: ApprovalDecision
    action_type: ActionType
    allowed: bool
    blockers: tuple[str, ...]
    required_approvals: tuple[str, ...]
    explanation: str
    evaluated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class ApprovalPolicyEngine:
    """Apply zero-bypass approval policy to sensitive actions."""

    SENSITIVE_ACTIONS = {
        ActionType.SEND_BUYER_QUOTATION,
        ActionType.START_NEGOTIATION,
        ActionType.ISSUE_PURCHASE_ORDER,
        ActionType.RELEASE_PAYMENT,
        ActionType.BOOK_SHIPMENT,
        ActionType.ACTIVATE_CONTRACT,
        ActionType.RESERVE_INVENTORY,
    }

    def evaluate(
        self,
        request: ApprovalRequest,
    ) -> ApprovalResult:
        blockers: list[str] = []
        required_approvals: list[str] = []

        if not request.buyer_verified:
            blockers.append("Buyer verification is incomplete.")

        if not request.supplier_verified:
            blockers.append("Supplier verification is incomplete.")

        if not request.compliance_cleared:
            blockers.append("Compliance clearance is incomplete.")

        if request.risk_score >= 80:
            blockers.append("Risk score is critically high.")

        if request.trust_score < 50:
            blockers.append("Trust score is below minimum.")

        if request.action_type in {
            ActionType.ISSUE_PURCHASE_ORDER,
            ActionType.RELEASE_PAYMENT,
            ActionType.BOOK_SHIPMENT,
            ActionType.ACTIVATE_CONTRACT,
        }:
            if not request.buyer_final_approval:
                blockers.append("Buyer final approval is missing.")

            if not request.funds_cleared:
                blockers.append("Buyer funds are not cleared.")

            if not request.documents_verified:
                blockers.append("Required documents are not verified.")

            if not request.margin_protected:
                blockers.append("Protected margin is not confirmed.")

        if request.action_type == ActionType.ACTIVATE_CONTRACT:
            if not request.contract_ready:
                blockers.append("Contract is not ready for activation.")

        if request.action_type in self.SENSITIVE_ACTIONS:
            required_approvals.append(
                "Authorised human approval"
            )

        if blockers:
            decision = ApprovalDecision.DENY
            allowed = False
        elif required_approvals and not request.authorised_human_approval:
            decision = ApprovalDecision.REQUIRE_APPROVAL
            allowed = False
        elif request.authorised_human_approval:
            decision = ApprovalDecision.ALLOW
            allowed = True
        else:
            decision = ApprovalDecision.HOLD
            allowed = False

        return ApprovalResult(
            request_id=request.request_id,
            decision=decision,
            action_type=request.action_type,
            allowed=allowed,
            blockers=tuple(blockers),
            required_approvals=tuple(required_approvals),
            explanation=(
                f"Action '{request.action_type.value}' is "
                f"{'allowed' if allowed else 'not allowed'}. "
                f"Decision: {decision.value}."
            ),
        )


_engine = ApprovalPolicyEngine()


def get_approval_policy_engine() -> ApprovalPolicyEngine:
    return _engine