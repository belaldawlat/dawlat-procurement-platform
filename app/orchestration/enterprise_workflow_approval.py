"""Governed approvals for enterprise workflow stages and tasks.

Package V - Enterprise Workflow Intelligence.

This module provides immutable approval records, role-aware decision
validation, quorum calculation, duplicate-vote protection, expiry handling,
and deterministic approval outcomes without coupling the workflow layer to a
particular UI, database, or identity provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Iterable, Mapping
from uuid import uuid4

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_models import (
    EnterpriseWorkflow,
    EnterpriseWorkflowApprovalMode,
    EnterpriseWorkflowStage,
    EnterpriseWorkflowStageStatus,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp and normalise it to UTC."""

    cleaned = str(value or "").strip()

    if not cleaned:
        raise ValueError("Approval timestamp is required.")

    parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


class EnterpriseWorkflowApprovalDecision(str, Enum):
    """Supported human or governed approval decisions."""

    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class EnterpriseWorkflowApprovalStatus(str, Enum):
    """Lifecycle state of one approval request."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class EnterpriseWorkflowApprovalSubjectType(str, Enum):
    """Workflow object types that may require approval."""

    WORKFLOW = "workflow"
    STAGE = "stage"
    TASK = "task"


@dataclass(frozen=True)
class EnterpriseWorkflowApprovalVote:
    """One immutable approval vote."""

    approver_id: str
    decision: EnterpriseWorkflowApprovalDecision
    approver_roles: tuple[str, ...] = ()
    comment: str = ""
    decided_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        approver_id = str(self.approver_id or "").strip()

        if not approver_id:
            raise ValueError("Workflow approval approver ID is required.")

        roles = tuple(
            str(role).strip()
            for role in self.approver_roles
            if str(role).strip()
        )

        if len(roles) != len(set(roles)):
            raise ValueError("Workflow approval roles must be unique.")

        _parse_timestamp(self.decided_at)

        object.__setattr__(self, "approver_id", approver_id)
        object.__setattr__(self, "approver_roles", roles)
        object.__setattr__(
            self,
            "comment",
            str(self.comment or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "approver_id": self.approver_id,
            "decision": self.decision.value,
            "approver_roles": list(self.approver_roles),
            "comment": self.comment,
            "decided_at": self.decided_at,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowApprovalRequest:
    """Immutable governed approval request."""

    workflow_id: str
    subject_id: str
    subject_type: EnterpriseWorkflowApprovalSubjectType
    approval_mode: EnterpriseWorkflowApprovalMode
    required_approvals: int
    request_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    approver_roles: tuple[str, ...] = ()
    status: EnterpriseWorkflowApprovalStatus = (
        EnterpriseWorkflowApprovalStatus.PENDING
    )
    requested_by: str = "system"
    requested_at: str = dataclass_field(default_factory=utc_timestamp)
    expires_at: str = ""
    votes: tuple[EnterpriseWorkflowApprovalVote, ...] = ()
    reason: str = ""
    correlation_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        request_id = str(self.request_id or "").strip()
        workflow_id = str(self.workflow_id or "").strip()
        subject_id = str(self.subject_id or "").strip()
        requested_by = str(self.requested_by or "").strip()

        if not request_id:
            raise ValueError("Workflow approval request ID is required.")
        if not workflow_id:
            raise ValueError("Workflow approval workflow ID is required.")
        if not subject_id:
            raise ValueError("Workflow approval subject ID is required.")
        if not requested_by:
            raise ValueError("Workflow approval requester is required.")
        if self.required_approvals < 0:
            raise ValueError("Required workflow approvals cannot be negative.")

        roles = tuple(
            str(role).strip()
            for role in self.approver_roles
            if str(role).strip()
        )

        if len(roles) != len(set(roles)):
            raise ValueError("Workflow approval roles must be unique.")

        votes = tuple(self.votes)
        voter_ids = [vote.approver_id for vote in votes]

        if len(voter_ids) != len(set(voter_ids)):
            raise ValueError(
                "Each approver may vote only once per approval request."
            )

        if self.approval_mode is EnterpriseWorkflowApprovalMode.NONE:
            if self.required_approvals != 0:
                raise ValueError(
                    "Approval count must be zero when mode is none."
                )
            if self.status not in {
                EnterpriseWorkflowApprovalStatus.NOT_REQUIRED,
                EnterpriseWorkflowApprovalStatus.CANCELLED,
            }:
                raise ValueError(
                    "Approval mode none must use not-required status."
                )
        elif self.required_approvals < 1:
            raise ValueError(
                "Governed approval requests require at least one approval."
            )

        _parse_timestamp(self.requested_at)

        if self.expires_at:
            expiry = _parse_timestamp(self.expires_at)
            requested = _parse_timestamp(self.requested_at)

            if expiry <= requested:
                raise ValueError(
                    "Workflow approval expiry must follow request time."
                )

        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "workflow_id", workflow_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "requested_by", requested_by)
        object.__setattr__(self, "approver_roles", roles)
        object.__setattr__(self, "votes", votes)
        object.__setattr__(
            self,
            "reason",
            str(self.reason or "").strip(),
        )
        object.__setattr__(
            self,
            "correlation_id",
            str(self.correlation_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def approval_count(self) -> int:
        """Return the number of affirmative votes."""

        return sum(
            1
            for vote in self.votes
            if vote.decision
            is EnterpriseWorkflowApprovalDecision.APPROVE
        )

    @property
    def rejection_count(self) -> int:
        """Return the number of rejection votes."""

        return sum(
            1
            for vote in self.votes
            if vote.decision
            is EnterpriseWorkflowApprovalDecision.REJECT
        )

    @property
    def is_terminal(self) -> bool:
        """Return whether no further decisions may be accepted."""

        return self.status in {
            EnterpriseWorkflowApprovalStatus.NOT_REQUIRED,
            EnterpriseWorkflowApprovalStatus.APPROVED,
            EnterpriseWorkflowApprovalStatus.REJECTED,
            EnterpriseWorkflowApprovalStatus.EXPIRED,
            EnterpriseWorkflowApprovalStatus.CANCELLED,
        }

    @property
    def is_expired(self) -> bool:
        """Return whether the request has passed its expiry timestamp."""

        if not self.expires_at:
            return False

        return datetime.now(timezone.utc) >= _parse_timestamp(
            self.expires_at
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "subject_id": self.subject_id,
            "subject_type": self.subject_type.value,
            "approval_mode": self.approval_mode.value,
            "required_approvals": self.required_approvals,
            "approver_roles": list(self.approver_roles),
            "status": self.status.value,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at,
            "expires_at": self.expires_at,
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
            "votes": [vote.as_dict() for vote in self.votes],
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowApprovalResult:
    """Result returned after an approval operation."""

    request: EnterpriseWorkflowApprovalRequest
    accepted: bool
    status_changed: bool = False
    message: str = ""
    violations: tuple[str, ...] = ()

    @property
    def approved(self) -> bool:
        """Return whether the request is approved."""

        return (
            self.request.status
            is EnterpriseWorkflowApprovalStatus.APPROVED
        )

    @property
    def rejected(self) -> bool:
        """Return whether the request is rejected."""

        return (
            self.request.status
            is EnterpriseWorkflowApprovalStatus.REJECTED
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "request": self.request.as_dict(),
            "accepted": self.accepted,
            "status_changed": self.status_changed,
            "approved": self.approved,
            "rejected": self.rejected,
            "message": self.message,
            "violations": list(self.violations),
        }


class EnterpriseWorkflowApprovalManager:
    """Thread-safe approval request and decision manager."""

    def __init__(self) -> None:
        self._requests: dict[
            str,
            EnterpriseWorkflowApprovalRequest,
        ] = {}
        self._lock = RLock()

    def create_for_stage(
        self,
        workflow: EnterpriseWorkflow,
        stage_id: str,
        *,
        requested_by: str = "system",
        reason: str = "",
        expires_at: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowApprovalRequest:
        """Create a governed approval request for a workflow stage."""

        stage = self._find_stage(workflow, stage_id)

        if stage.approval_mode is EnterpriseWorkflowApprovalMode.NONE:
            status = EnterpriseWorkflowApprovalStatus.NOT_REQUIRED
        else:
            status = EnterpriseWorkflowApprovalStatus.PENDING

        request = EnterpriseWorkflowApprovalRequest(
            workflow_id=workflow.workflow_id,
            subject_id=stage.stage_id,
            subject_type=EnterpriseWorkflowApprovalSubjectType.STAGE,
            approval_mode=stage.approval_mode,
            required_approvals=stage.required_approvals,
            approver_roles=stage.approver_roles,
            status=status,
            requested_by=requested_by,
            expires_at=expires_at,
            reason=reason,
            correlation_id=workflow.correlation_id,
            metadata=redact_mapping(dict(metadata or {})),
        )

        with self._lock:
            self._requests[request.request_id] = request

        return request

    def create_for_task(
        self,
        workflow: EnterpriseWorkflow,
        stage_id: str,
        task_id: str,
        *,
        requested_by: str = "system",
        required_approvals: int = 1,
        approver_roles: Iterable[str] = (),
        approval_mode: EnterpriseWorkflowApprovalMode = (
            EnterpriseWorkflowApprovalMode.SINGLE
        ),
        reason: str = "",
        expires_at: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowApprovalRequest:
        """Create a governed approval request for one workflow task."""

        stage = self._find_stage(workflow, stage_id)
        task = next(
            (
                item
                for item in stage.tasks
                if item.task_id == str(task_id or "").strip()
            ),
            None,
        )

        if task is None:
            raise KeyError("Workflow task was not found.")
        if not task.requires_approval:
            raise ValueError(
                "Workflow task does not require approval."
            )

        request = EnterpriseWorkflowApprovalRequest(
            workflow_id=workflow.workflow_id,
            subject_id=task.task_id,
            subject_type=EnterpriseWorkflowApprovalSubjectType.TASK,
            approval_mode=approval_mode,
            required_approvals=required_approvals,
            approver_roles=tuple(approver_roles),
            requested_by=requested_by,
            expires_at=expires_at,
            reason=reason,
            correlation_id=workflow.correlation_id,
            metadata={
                "stage_id": stage.stage_id,
                **redact_mapping(dict(metadata or {})),
            },
        )

        with self._lock:
            self._requests[request.request_id] = request

        return request

    def decide(
        self,
        request_id: str,
        *,
        approver_id: str,
        decision: EnterpriseWorkflowApprovalDecision,
        approver_roles: Iterable[str] = (),
        comment: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowApprovalResult:
        """Record one governed decision and calculate the new status."""

        cleaned_request_id = str(request_id or "").strip()

        if not cleaned_request_id:
            raise ValueError("Workflow approval request ID is required.")

        with self._lock:
            current = self._requests.get(cleaned_request_id)

            if current is None:
                raise KeyError("Workflow approval request was not found.")

            if current.is_terminal:
                return EnterpriseWorkflowApprovalResult(
                    request=current,
                    accepted=False,
                    message=(
                        "Workflow approval request is already terminal."
                    ),
                    violations=("approval_request_terminal",),
                )

            if current.is_expired:
                expired = replace(
                    current,
                    status=EnterpriseWorkflowApprovalStatus.EXPIRED,
                )
                self._requests[cleaned_request_id] = expired

                return EnterpriseWorkflowApprovalResult(
                    request=expired,
                    accepted=False,
                    status_changed=True,
                    message="Workflow approval request has expired.",
                    violations=("approval_request_expired",),
                )

            cleaned_approver = str(approver_id or "").strip()

            if not cleaned_approver:
                raise ValueError(
                    "Workflow approval approver ID is required."
                )

            if any(
                vote.approver_id == cleaned_approver
                for vote in current.votes
            ):
                return EnterpriseWorkflowApprovalResult(
                    request=current,
                    accepted=False,
                    message="Approver has already voted.",
                    violations=("duplicate_approval_vote",),
                )

            roles = tuple(
                str(role).strip()
                for role in approver_roles
                if str(role).strip()
            )

            if current.approver_roles and not (
                set(roles) & set(current.approver_roles)
            ):
                return EnterpriseWorkflowApprovalResult(
                    request=current,
                    accepted=False,
                    message="Approver does not hold an authorised role.",
                    violations=("unauthorised_approver_role",),
                )

            vote = EnterpriseWorkflowApprovalVote(
                approver_id=cleaned_approver,
                decision=decision,
                approver_roles=roles,
                comment=comment,
                metadata=redact_mapping(dict(metadata or {})),
            )
            votes = (*current.votes, vote)
            updated = replace(current, votes=votes)
            final_status = self._calculate_status(updated)
            status_changed = final_status is not current.status
            updated = replace(updated, status=final_status)
            self._requests[cleaned_request_id] = updated

            return EnterpriseWorkflowApprovalResult(
                request=updated,
                accepted=True,
                status_changed=status_changed,
                message="Workflow approval decision recorded.",
            )

    def approve(
        self,
        request_id: str,
        *,
        approver_id: str,
        approver_roles: Iterable[str] = (),
        comment: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowApprovalResult:
        """Convenience wrapper for an affirmative decision."""

        return self.decide(
            request_id,
            approver_id=approver_id,
            decision=EnterpriseWorkflowApprovalDecision.APPROVE,
            approver_roles=approver_roles,
            comment=comment,
            metadata=metadata,
        )

    def reject(
        self,
        request_id: str,
        *,
        approver_id: str,
        approver_roles: Iterable[str] = (),
        comment: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowApprovalResult:
        """Convenience wrapper for a rejection decision."""

        return self.decide(
            request_id,
            approver_id=approver_id,
            decision=EnterpriseWorkflowApprovalDecision.REJECT,
            approver_roles=approver_roles,
            comment=comment,
            metadata=metadata,
        )

    def cancel(
        self,
        request_id: str,
        *,
        actor_id: str = "system",
        reason: str = "",
    ) -> EnterpriseWorkflowApprovalRequest:
        """Cancel a non-terminal approval request."""

        cleaned_request_id = str(request_id or "").strip()
        actor = str(actor_id or "").strip()

        if not cleaned_request_id:
            raise ValueError("Workflow approval request ID is required.")
        if not actor:
            raise ValueError("Workflow approval actor ID is required.")

        with self._lock:
            current = self._requests.get(cleaned_request_id)

            if current is None:
                raise KeyError("Workflow approval request was not found.")
            if current.is_terminal:
                return current

            cancelled = replace(
                current,
                status=EnterpriseWorkflowApprovalStatus.CANCELLED,
                metadata={
                    **redact_mapping(current.metadata),
                    "cancelled_by": actor,
                    "cancellation_reason": str(reason or "").strip(),
                    "cancelled_at": utc_timestamp(),
                },
            )
            self._requests[cleaned_request_id] = cancelled

            return cancelled

    def expire_due_requests(
        self,
        *,
        now: str | None = None,
    ) -> tuple[EnterpriseWorkflowApprovalRequest, ...]:
        """Expire all pending requests whose deadline has passed."""

        current_time = (
            _parse_timestamp(now)
            if now
            else datetime.now(timezone.utc)
        )
        expired: list[EnterpriseWorkflowApprovalRequest] = []

        with self._lock:
            for request_id, request in tuple(self._requests.items()):
                if (
                    request.status
                    is EnterpriseWorkflowApprovalStatus.PENDING
                    and request.expires_at
                    and current_time >= _parse_timestamp(
                        request.expires_at
                    )
                ):
                    updated = replace(
                        request,
                        status=EnterpriseWorkflowApprovalStatus.EXPIRED,
                    )
                    self._requests[request_id] = updated
                    expired.append(updated)

        return tuple(expired)

    def get(
        self,
        request_id: str,
    ) -> EnterpriseWorkflowApprovalRequest:
        """Return one approval request."""

        cleaned_request_id = str(request_id or "").strip()

        if not cleaned_request_id:
            raise ValueError("Workflow approval request ID is required.")

        with self._lock:
            request = self._requests.get(cleaned_request_id)

        if request is None:
            raise KeyError("Workflow approval request was not found.")

        return request

    def list_requests(
        self,
        *,
        workflow_id: str | None = None,
        subject_id: str | None = None,
        status: EnterpriseWorkflowApprovalStatus | None = None,
        include_terminal: bool = True,
    ) -> tuple[EnterpriseWorkflowApprovalRequest, ...]:
        """Return approval requests matching optional criteria."""

        cleaned_workflow_id = (
            str(workflow_id).strip()
            if workflow_id is not None
            else None
        )
        cleaned_subject_id = (
            str(subject_id).strip()
            if subject_id is not None
            else None
        )

        with self._lock:
            requests = tuple(self._requests.values())

        filtered = [
            request
            for request in requests
            if (
                cleaned_workflow_id is None
                or request.workflow_id == cleaned_workflow_id
            )
            and (
                cleaned_subject_id is None
                or request.subject_id == cleaned_subject_id
            )
            and (status is None or request.status is status)
            and (include_terminal or not request.is_terminal)
        ]

        filtered.sort(
            key=lambda request: (
                request.requested_at,
                request.request_id,
            )
        )

        return tuple(filtered)

    def apply_stage_status(
        self,
        workflow: EnterpriseWorkflow,
        request_id: str,
    ) -> EnterpriseWorkflow:
        """Apply an approval outcome to its workflow stage immutably."""

        request = self.get(request_id)

        if request.workflow_id != workflow.workflow_id:
            raise ValueError(
                "Approval request does not belong to the workflow."
            )
        if (
            request.subject_type
            is not EnterpriseWorkflowApprovalSubjectType.STAGE
        ):
            raise ValueError(
                "Approval request does not target a workflow stage."
            )

        stages: list[EnterpriseWorkflowStage] = []
        found = False

        for stage in workflow.stages:
            if stage.stage_id != request.subject_id:
                stages.append(stage)
                continue

            found = True
            status = stage.status

            if (
                request.status
                is EnterpriseWorkflowApprovalStatus.APPROVED
            ):
                status = EnterpriseWorkflowStageStatus.APPROVED
            elif (
                request.status
                is EnterpriseWorkflowApprovalStatus.REJECTED
            ):
                status = EnterpriseWorkflowStageStatus.REJECTED
            elif (
                request.status
                is EnterpriseWorkflowApprovalStatus.PENDING
            ):
                status = (
                    EnterpriseWorkflowStageStatus.AWAITING_APPROVAL
                )

            stages.append(replace(stage, status=status))

        if not found:
            raise KeyError("Workflow approval stage was not found.")

        return replace(workflow, stages=tuple(stages))

    def clear(self) -> None:
        """Clear all in-memory approval requests."""

        with self._lock:
            self._requests.clear()

    @staticmethod
    def _find_stage(
        workflow: EnterpriseWorkflow,
        stage_id: str,
    ) -> EnterpriseWorkflowStage:
        if not isinstance(workflow, EnterpriseWorkflow):
            raise TypeError(
                "Workflow approval requires EnterpriseWorkflow."
            )

        cleaned_stage_id = str(stage_id or "").strip()

        if not cleaned_stage_id:
            raise ValueError("Workflow approval stage ID is required.")

        stage = next(
            (
                item
                for item in workflow.stages
                if item.stage_id == cleaned_stage_id
            ),
            None,
        )

        if stage is None:
            raise KeyError("Workflow stage was not found.")

        return stage

    @staticmethod
    def _calculate_status(
        request: EnterpriseWorkflowApprovalRequest,
    ) -> EnterpriseWorkflowApprovalStatus:
        if request.rejection_count:
            return EnterpriseWorkflowApprovalStatus.REJECTED

        if (
            request.approval_mode
            is EnterpriseWorkflowApprovalMode.SINGLE
            and request.approval_count >= 1
        ):
            return EnterpriseWorkflowApprovalStatus.APPROVED

        if (
            request.approval_mode
            in {
                EnterpriseWorkflowApprovalMode.QUORUM,
                EnterpriseWorkflowApprovalMode.UNANIMOUS,
            }
            and request.approval_count >= request.required_approvals
        ):
            return EnterpriseWorkflowApprovalStatus.APPROVED

        return EnterpriseWorkflowApprovalStatus.PENDING


_enterprise_workflow_approval_manager: (
    EnterpriseWorkflowApprovalManager | None
) = None
_enterprise_workflow_approval_lock = RLock()


def get_enterprise_workflow_approval_manager(
) -> EnterpriseWorkflowApprovalManager:
    """Return the process-wide workflow approval manager."""

    global _enterprise_workflow_approval_manager

    with _enterprise_workflow_approval_lock:
        if _enterprise_workflow_approval_manager is None:
            _enterprise_workflow_approval_manager = (
                EnterpriseWorkflowApprovalManager()
            )

        return _enterprise_workflow_approval_manager


# Backward-compatible aliases for earlier Package V integrations.
WorkflowApprovalDecision = EnterpriseWorkflowApprovalDecision
WorkflowApprovalStatus = EnterpriseWorkflowApprovalStatus
WorkflowApprovalSubjectType = EnterpriseWorkflowApprovalSubjectType
WorkflowApprovalVote = EnterpriseWorkflowApprovalVote
WorkflowApprovalRequest = EnterpriseWorkflowApprovalRequest
WorkflowApprovalResult = EnterpriseWorkflowApprovalResult
WorkflowApprovalManager = EnterpriseWorkflowApprovalManager
get_workflow_approval_manager = (
    get_enterprise_workflow_approval_manager
)