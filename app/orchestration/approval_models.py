"""Immutable models for enterprise workflow approvals."""

from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field as dataclass_field,
    replace,
)
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class ApprovalStatus(str, Enum):
    """Lifecycle states for an approval request."""

    PENDING = "pending"
    PARTIALLY_APPROVED = "partially_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalDecisionType(str, Enum):
    """Supported approval decisions."""

    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class ApprovalSubjectType(str, Enum):
    """Supported approval subject classifications."""

    WORKFLOW = "workflow"
    WORKFLOW_STEP = "workflow_step"
    SUPPLIER = "supplier"
    QUOTATION = "quotation"
    PURCHASE_ORDER = "purchase_order"
    PAYMENT = "payment"
    SHIPMENT = "shipment"
    DOCUMENT = "document"
    COMPLIANCE = "compliance"
    OTHER = "other"


@dataclass(frozen=True)
class ApprovalDecision:
    """Immutable decision made against an approval request."""

    decision_id: str
    request_id: str
    decision: ApprovalDecisionType
    approver_id: str
    approver_role: str
    reason: str = ""
    decided_at: str = dataclass_field(
        default_factory=utc_timestamp
    )
    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Validate and normalise approval decision values."""

        decision_id = str(self.decision_id or "").strip()
        request_id = str(self.request_id or "").strip()
        approver_id = str(self.approver_id or "").strip()
        approver_role = str(self.approver_role or "").strip()

        if not decision_id:
            raise ValueError("Approval decision ID is required.")

        if not request_id:
            raise ValueError("Approval request ID is required.")

        if not approver_id:
            raise ValueError("Approver ID is required.")

        if not approver_role:
            raise ValueError("Approver role is required.")

        object.__setattr__(self, "decision_id", decision_id)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "approver_id", approver_id)
        object.__setattr__(
            self,
            "approver_role",
            approver_role,
        )
        object.__setattr__(
            self,
            "reason",
            str(self.reason or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        payload = asdict(self)
        payload["decision"] = self.decision.value
        payload["metadata"] = redact_mapping(self.metadata)
        return payload


@dataclass(frozen=True)
class ApprovalRequest:
    """Immutable approval request and its decision history."""

    policy_id: str
    subject_type: ApprovalSubjectType
    subject_id: str
    requested_by: str
    request_id: str = dataclass_field(
        default_factory=lambda: uuid4().hex
    )
    workflow_instance_id: str = ""
    workflow_step_id: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    title: str = ""
    description: str = ""
    amount: float | None = None
    currency: str = ""
    created_at: str = dataclass_field(
        default_factory=utc_timestamp
    )
    expires_at: str = ""
    decisions: tuple[ApprovalDecision, ...] = ()
    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Validate and normalise approval request data."""

        policy_id = str(self.policy_id or "").strip()
        subject_id = str(self.subject_id or "").strip()
        requested_by = str(self.requested_by or "").strip()
        request_id = str(
            self.request_id or uuid4().hex
        ).strip()

        if not policy_id:
            raise ValueError("Approval policy ID is required.")

        if not subject_id:
            raise ValueError("Approval subject ID is required.")

        if not requested_by:
            raise ValueError(
                "Approval requester ID is required."
            )

        if self.amount is not None and self.amount < 0:
            raise ValueError(
                "Approval amount cannot be negative."
            )

        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(
            self,
            "requested_by",
            requested_by,
        )
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(
            self,
            "workflow_instance_id",
            str(self.workflow_instance_id or "").strip(),
        )
        object.__setattr__(
            self,
            "workflow_step_id",
            str(self.workflow_step_id or "").strip(),
        )
        object.__setattr__(
            self,
            "title",
            str(self.title or "").strip(),
        )
        object.__setattr__(
            self,
            "description",
            str(self.description or "").strip(),
        )
        object.__setattr__(
            self,
            "currency",
            str(self.currency or "").strip().upper(),
        )
        object.__setattr__(
            self,
            "expires_at",
            str(self.expires_at or "").strip(),
        )
        object.__setattr__(
            self,
            "decisions",
            tuple(self.decisions),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def is_terminal(self) -> bool:
        """Return whether the request is terminal."""

        return self.status in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.CANCELLED,
        }

    @property
    def approval_count(self) -> int:
        """Return the number of approval decisions."""

        return sum(
            decision.decision
            is ApprovalDecisionType.APPROVE
            for decision in self.decisions
        )

    @property
    def rejection_count(self) -> int:
        """Return the number of rejection decisions."""

        return sum(
            decision.decision
            is ApprovalDecisionType.REJECT
            for decision in self.decisions
        )

    @property
    def decided_approver_ids(self) -> frozenset[str]:
        """Return approvers who already submitted a decision."""

        return frozenset(
            decision.approver_id
            for decision in self.decisions
        )

    def add_decision(
        self,
        decision: ApprovalDecision,
        *,
        status: ApprovalStatus,
    ) -> "ApprovalRequest":
        """Return a copy containing an additional decision."""

        return replace(
            self,
            status=status,
            decisions=(
                *self.decisions,
                decision,
            ),
        )

    def with_status(
        self,
        status: ApprovalStatus,
    ) -> "ApprovalRequest":
        """Return a copy with a new status."""

        return replace(self, status=status)

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "request_id": self.request_id,
            "policy_id": self.policy_id,
            "subject_type": self.subject_type.value,
            "subject_id": self.subject_id,
            "requested_by": self.requested_by,
            "workflow_instance_id": (
                self.workflow_instance_id
            ),
            "workflow_step_id": self.workflow_step_id,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "amount": self.amount,
            "currency": self.currency,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
            "metadata": redact_mapping(self.metadata),
            "decisions": [
                decision.as_dict()
                for decision in self.decisions
            ],
        }