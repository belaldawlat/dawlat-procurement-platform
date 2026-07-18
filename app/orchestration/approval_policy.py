"""Approval policy definitions and deterministic evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.approval_models import (
    ApprovalDecision,
    ApprovalDecisionType,
    ApprovalRequest,
    ApprovalStatus,
)


@dataclass(frozen=True)
class ApprovalPolicyViolation:
    """Deterministic reason an approval action was rejected."""

    code: str
    message: str
    field_name: str = ""
    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Normalise and redact violation values."""

        object.__setattr__(
            self,
            "code",
            str(self.code or "").strip(),
        )
        object.__setattr__(
            self,
            "message",
            str(self.message or "").strip(),
        )
        object.__setattr__(
            self,
            "field_name",
            str(self.field_name or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )


@dataclass(frozen=True)
class ApprovalPolicy:
    """Immutable role, quorum and threshold approval policy."""

    policy_id: str
    name: str
    required_approvals: int = 1
    allowed_roles: frozenset[str] = frozenset()
    minimum_amount: float | None = None
    maximum_amount: float | None = None
    allow_requester_approval: bool = False
    reject_on_first_rejection: bool = True
    require_distinct_approvers: bool = True
    enabled: bool = True
    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Validate immutable policy configuration."""

        policy_id = str(self.policy_id or "").strip()
        name = str(self.name or "").strip()

        if not policy_id:
            raise ValueError("Approval policy ID is required.")

        if not name:
            raise ValueError("Approval policy name is required.")

        if self.required_approvals < 1:
            raise ValueError(
                "Required approvals must be at least 1."
            )

        if (
            self.minimum_amount is not None
            and self.minimum_amount < 0
        ):
            raise ValueError(
                "Minimum approval amount cannot be negative."
            )

        if (
            self.maximum_amount is not None
            and self.maximum_amount < 0
        ):
            raise ValueError(
                "Maximum approval amount cannot be negative."
            )

        if (
            self.minimum_amount is not None
            and self.maximum_amount is not None
            and self.minimum_amount > self.maximum_amount
        ):
            raise ValueError(
                "Minimum amount cannot exceed maximum amount."
            )

        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "allowed_roles",
            frozenset(
                str(role).strip()
                for role in self.allowed_roles
                if str(role).strip()
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def applies_to_amount(
        self,
        amount: float | None,
    ) -> bool:
        """Return whether the policy covers the supplied amount."""

        if amount is None:
            return (
                self.minimum_amount is None
                and self.maximum_amount is None
            )

        if (
            self.minimum_amount is not None
            and amount < self.minimum_amount
        ):
            return False

        if (
            self.maximum_amount is not None
            and amount > self.maximum_amount
        ):
            return False

        return True

    def validate_request(
        self,
        request: ApprovalRequest,
    ) -> tuple[ApprovalPolicyViolation, ...]:
        """Validate a request against this policy."""

        violations: list[ApprovalPolicyViolation] = []

        if not self.enabled:
            violations.append(
                ApprovalPolicyViolation(
                    code="APPROVAL_POLICY_DISABLED",
                    message="The approval policy is disabled.",
                )
            )

        if request.policy_id != self.policy_id:
            violations.append(
                ApprovalPolicyViolation(
                    code="APPROVAL_POLICY_MISMATCH",
                    message=(
                        "The approval request references a "
                        "different policy."
                    ),
                    field_name="policy_id",
                )
            )

        if not self.applies_to_amount(request.amount):
            violations.append(
                ApprovalPolicyViolation(
                    code="APPROVAL_AMOUNT_OUTSIDE_POLICY",
                    message=(
                        "The approval amount is outside the "
                        "policy threshold."
                    ),
                    field_name="amount",
                    metadata={
                        "amount": request.amount,
                        "minimum_amount": self.minimum_amount,
                        "maximum_amount": self.maximum_amount,
                    },
                )
            )

        return tuple(violations)

    def validate_decision(
        self,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> tuple[ApprovalPolicyViolation, ...]:
        """Validate a proposed approval decision."""

        violations: list[ApprovalPolicyViolation] = []

        if request.is_terminal:
            violations.append(
                ApprovalPolicyViolation(
                    code="APPROVAL_REQUEST_TERMINAL",
                    message=(
                        "A terminal approval request cannot "
                        "receive further decisions."
                    ),
                )
            )

        if decision.request_id != request.request_id:
            violations.append(
                ApprovalPolicyViolation(
                    code="APPROVAL_REQUEST_ID_MISMATCH",
                    message=(
                        "The decision does not belong to the "
                        "approval request."
                    ),
                    field_name="request_id",
                )
            )

        if (
            self.allowed_roles
            and decision.approver_role
            not in self.allowed_roles
        ):
            violations.append(
                ApprovalPolicyViolation(
                    code="APPROVER_ROLE_NOT_ALLOWED",
                    message=(
                        "The approver role is not permitted "
                        "by this policy."
                    ),
                    field_name="approver_role",
                    metadata={
                        "approver_role": (
                            decision.approver_role
                        ),
                        "allowed_roles": sorted(
                            self.allowed_roles
                        ),
                    },
                )
            )

        if (
            not self.allow_requester_approval
            and decision.approver_id
            == request.requested_by
        ):
            violations.append(
                ApprovalPolicyViolation(
                    code="SEPARATION_OF_DUTIES_VIOLATION",
                    message=(
                        "The requester cannot approve their "
                        "own request."
                    ),
                    field_name="approver_id",
                )
            )

        if (
            self.require_distinct_approvers
            and decision.approver_id
            in request.decided_approver_ids
        ):
            violations.append(
                ApprovalPolicyViolation(
                    code="DUPLICATE_APPROVER_DECISION",
                    message=(
                        "This approver has already submitted "
                        "a decision."
                    ),
                    field_name="approver_id",
                )
            )

        return tuple(
            sorted(
                violations,
                key=lambda violation: (
                    violation.code,
                    violation.field_name,
                ),
            )
        )

    def resolve_status(
        self,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> ApprovalStatus:
        """Resolve the request status after an accepted decision."""

        if (
            decision.decision
            is ApprovalDecisionType.REJECT
            and self.reject_on_first_rejection
        ):
            return ApprovalStatus.REJECTED

        approvals = request.approval_count

        if decision.decision is ApprovalDecisionType.APPROVE:
            approvals += 1

        rejections = request.rejection_count

        if decision.decision is ApprovalDecisionType.REJECT:
            rejections += 1

        if approvals >= self.required_approvals:
            return ApprovalStatus.APPROVED

        if rejections > 0:
            return ApprovalStatus.PARTIALLY_APPROVED

        if approvals > 0:
            return ApprovalStatus.PARTIALLY_APPROVED

        return ApprovalStatus.PENDING