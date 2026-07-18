"""Enterprise approval and policy gate execution engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.observability.logging_config import get_logger
from app.orchestration.approval_models import (
    ApprovalDecision,
    ApprovalDecisionType,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalSubjectType,
)
from app.orchestration.approval_policy import (
    ApprovalPolicy,
    ApprovalPolicyViolation,
)
from app.orchestration.approval_store import (
    InMemoryApprovalStore,
)
from app.orchestration.exceptions import (
    WorkflowStateError,
    WorkflowValidationError,
)


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp safely."""

    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ApprovalDecisionResult:
    """Result of submitting an approval decision."""

    accepted: bool
    request: ApprovalRequest
    decision: ApprovalDecision | None
    violations: tuple[ApprovalPolicyViolation, ...] = ()

    @property
    def approved(self) -> bool:
        """Return whether the request became approved."""

        return (
            self.accepted
            and self.request.status
            is ApprovalStatus.APPROVED
        )

    @property
    def rejected(self) -> bool:
        """Return whether the request became rejected."""

        return (
            self.accepted
            and self.request.status
            is ApprovalStatus.REJECTED
        )


class ApprovalEngine:
    """Create requests and enforce approval policy gates."""

    def __init__(
        self,
        *,
        store: InMemoryApprovalStore | None = None,
        raise_on_rejection: bool = True,
    ) -> None:
        self._store = store or InMemoryApprovalStore()
        self._raise_on_rejection = raise_on_rejection
        self._logger = get_logger(
            "orchestration.approval_engine"
        )

    @property
    def store(self) -> InMemoryApprovalStore:
        """Return the active approval store."""

        return self._store

    def register_policy(
        self,
        policy: ApprovalPolicy,
        *,
        replace_existing: bool = False,
    ) -> ApprovalPolicy:
        """Register an approval policy."""

        return self._store.register_policy(
            policy,
            replace_existing=replace_existing,
        )

    def create_request(
        self,
        *,
        policy_id: str,
        subject_type: ApprovalSubjectType,
        subject_id: str,
        requested_by: str,
        workflow_instance_id: str = "",
        workflow_step_id: str = "",
        title: str = "",
        description: str = "",
        amount: float | None = None,
        currency: str = "",
        expires_at: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Create and validate an approval request."""

        policy = self._store.get_policy(policy_id)

        request = ApprovalRequest(
            policy_id=policy_id,
            subject_type=subject_type,
            subject_id=subject_id,
            requested_by=requested_by,
            workflow_instance_id=workflow_instance_id,
            workflow_step_id=workflow_step_id,
            title=title,
            description=description,
            amount=amount,
            currency=currency,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        violations = policy.validate_request(request)

        if violations:
            raise WorkflowValidationError(
                technical_message=(
                    "Approval request failed policy validation."
                ),
                metadata={
                    "policy_id": policy_id,
                    "subject_id": subject_id,
                    "violations": [
                        {
                            "code": violation.code,
                            "message": violation.message,
                            "field_name": (
                                violation.field_name
                            ),
                        }
                        for violation in violations
                    ],
                },
            )

        if request.expires_at:
            self._validate_expiry_timestamp(
                request.expires_at
            )

        self._store.create_request(request)

        self._logger.info(
            "Approval request created.",
            extra={
                "request_id": request.request_id,
                "policy_id": request.policy_id,
                "subject_type": request.subject_type.value,
                "subject_id": request.subject_id,
                "amount": request.amount,
                "currency": request.currency,
            },
        )

        return request

    def submit_decision(
        self,
        request_id: str,
        *,
        decision: ApprovalDecisionType,
        approver_id: str,
        approver_role: str,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalDecisionResult:
        """Submit and enforce an approval decision."""

        request = self._store.get_request(request_id)
        request = self._expire_if_required(request)

        policy = self._store.get_policy(
            request.policy_id
        )

        proposed = ApprovalDecision(
            decision_id=uuid4().hex,
            request_id=request.request_id,
            decision=decision,
            approver_id=approver_id,
            approver_role=approver_role,
            reason=reason,
            metadata=metadata or {},
        )

        violations = policy.validate_decision(
            request,
            proposed,
        )

        if violations:
            result = ApprovalDecisionResult(
                accepted=False,
                request=request,
                decision=None,
                violations=violations,
            )

            self._logger.warning(
                "Approval decision rejected.",
                extra={
                    "request_id": request.request_id,
                    "policy_id": request.policy_id,
                    "approver_id": approver_id,
                    "approver_role": approver_role,
                    "violations": [
                        {
                            "code": violation.code,
                            "message": violation.message,
                        }
                        for violation in violations
                    ],
                },
            )

            if self._raise_on_rejection:
                raise WorkflowStateError(
                    technical_message=(
                        "Approval decision was rejected "
                        "by policy controls."
                    ),
                    metadata={
                        "request_id": request.request_id,
                        "policy_id": request.policy_id,
                        "violations": [
                            {
                                "code": violation.code,
                                "message": violation.message,
                                "field_name": (
                                    violation.field_name
                                ),
                            }
                            for violation in violations
                        ],
                    },
                )

            return result

        new_status = policy.resolve_status(
            request,
            proposed,
        )

        updated = request.add_decision(
            proposed,
            status=new_status,
        )
        self._store.save_request(updated)

        self._logger.info(
            "Approval decision accepted.",
            extra={
                "request_id": updated.request_id,
                "decision_id": proposed.decision_id,
                "decision": proposed.decision.value,
                "approver_id": proposed.approver_id,
                "approver_role": proposed.approver_role,
                "new_status": updated.status.value,
                "approval_count": updated.approval_count,
                "rejection_count": updated.rejection_count,
            },
        )

        return ApprovalDecisionResult(
            accepted=True,
            request=updated,
            decision=proposed,
        )

    def approve(
        self,
        request_id: str,
        *,
        approver_id: str,
        approver_role: str,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalDecisionResult:
        """Approve an approval request."""

        return self.submit_decision(
            request_id,
            decision=ApprovalDecisionType.APPROVE,
            approver_id=approver_id,
            approver_role=approver_role,
            reason=reason,
            metadata=metadata,
        )

    def reject(
        self,
        request_id: str,
        *,
        approver_id: str,
        approver_role: str,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalDecisionResult:
        """Reject an approval request."""

        return self.submit_decision(
            request_id,
            decision=ApprovalDecisionType.REJECT,
            approver_id=approver_id,
            approver_role=approver_role,
            reason=reason,
            metadata=metadata,
        )

    def abstain(
        self,
        request_id: str,
        *,
        approver_id: str,
        approver_role: str,
        reason: str = "",
    ) -> ApprovalDecisionResult:
        """Record an abstention decision."""

        return self.submit_decision(
            request_id,
            decision=ApprovalDecisionType.ABSTAIN,
            approver_id=approver_id,
            approver_role=approver_role,
            reason=reason,
        )

    def cancel(
        self,
        request_id: str,
        *,
        actor_id: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Cancel a non-terminal approval request."""

        request = self._store.get_request(request_id)

        if request.is_terminal:
            raise WorkflowStateError(
                technical_message=(
                    "A terminal approval request cannot "
                    "be cancelled."
                ),
                metadata={
                    "request_id": request.request_id,
                    "status": request.status.value,
                },
            )

        updated = request.with_status(
            ApprovalStatus.CANCELLED
        )
        self._store.save_request(updated)

        self._logger.warning(
            "Approval request cancelled.",
            extra={
                "request_id": updated.request_id,
                "actor_id": str(actor_id or "").strip(),
                "reason": str(reason or "").strip(),
            },
        )

        return updated

    def refresh_status(
        self,
        request_id: str,
    ) -> ApprovalRequest:
        """Refresh expiry and return the latest request."""

        request = self._store.get_request(request_id)
        return self._expire_if_required(request)

    def is_gate_satisfied(
        self,
        request_id: str,
    ) -> bool:
        """Return whether an approval gate is satisfied."""

        request = self.refresh_status(request_id)

        return request.status is ApprovalStatus.APPROVED

    def require_approved(
        self,
        request_id: str,
    ) -> ApprovalRequest:
        """Return the request or fail closed if unapproved."""

        request = self.refresh_status(request_id)

        if request.status is not ApprovalStatus.APPROVED:
            raise WorkflowStateError(
                technical_message=(
                    "Approval gate is not satisfied."
                ),
                metadata={
                    "request_id": request.request_id,
                    "status": request.status.value,
                },
            )

        return request

    def _expire_if_required(
        self,
        request: ApprovalRequest,
    ) -> ApprovalRequest:
        """Expire a request when its deadline has passed."""

        if request.is_terminal or not request.expires_at:
            return request

        expires_at = _parse_timestamp(
            request.expires_at
        )

        if datetime.now(timezone.utc) < expires_at:
            return request

        expired = request.with_status(
            ApprovalStatus.EXPIRED
        )
        self._store.save_request(expired)

        self._logger.warning(
            "Approval request expired.",
            extra={
                "request_id": expired.request_id,
                "expires_at": expired.expires_at,
            },
        )

        return expired

    @staticmethod
    def _validate_expiry_timestamp(
        expires_at: str,
    ) -> None:
        """Validate approval expiry timestamp format."""

        try:
            _parse_timestamp(expires_at)
        except (TypeError, ValueError) as error:
            raise WorkflowValidationError(
                technical_message=(
                    "Approval expiry timestamp is invalid."
                ),
                metadata={
                    "expires_at": expires_at,
                },
            ) from error


_default_approval_engine = ApprovalEngine()


def get_approval_engine() -> ApprovalEngine:
    """Return the shared approval engine."""

    return _default_approval_engine