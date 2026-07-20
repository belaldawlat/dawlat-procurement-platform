"""Enterprise workflow orchestration coordinator.

Package V - Enterprise Workflow Intelligence.

This module provides the primary application-facing orchestration boundary for
enterprise workflows. It coordinates workflow persistence, governed approvals,
state transitions, readiness refresh, analytics, idempotency, audit context,
and failure-safe execution without coupling callers to the underlying service
implementations.

The coordinator deliberately keeps domain models immutable. Every successful
operation returns a new workflow representation and, when requested, persists
it through the enterprise workflow store using optimistic concurrency.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Callable, Iterable, Mapping, TypeVar
from uuid import uuid4

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_analytics import (
    EnterpriseWorkflowAnalytics,
    EnterpriseWorkflowHealthReport,
    EnterpriseWorkflowPortfolioReport,
    get_enterprise_workflow_analytics,
)
from app.orchestration.enterprise_workflow_approval import (
    EnterpriseWorkflowApprovalDecision,
    EnterpriseWorkflowApprovalManager,
    EnterpriseWorkflowApprovalRequest,
    EnterpriseWorkflowApprovalResult,
    EnterpriseWorkflowApprovalStatus,
    get_enterprise_workflow_approval_manager,
)
from app.orchestration.enterprise_workflow_models import (
    EnterpriseWorkflow,
    EnterpriseWorkflowStageStatus,
    EnterpriseWorkflowStatus,
    EnterpriseWorkflowTaskStatus,
)
from app.orchestration.enterprise_workflow_store import (
    EnterpriseWorkflowStore,
    EnterpriseWorkflowStoreQuery,
    EnterpriseWorkflowStoreRecord,
    get_enterprise_workflow_store,
)
from app.orchestration.enterprise_workflow_transition import (
    EnterpriseWorkflowTransitionEngine,
    EnterpriseWorkflowTransitionEvent,
    EnterpriseWorkflowTransitionResult,
    get_enterprise_workflow_transition_engine,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


T = TypeVar("T")


class EnterpriseWorkflowCoordinatorOperation(str, Enum):
    """Coordinator operations exposed through the orchestration boundary."""

    CREATE = "create"
    SAVE = "save"
    LOAD = "load"
    REFRESH = "refresh"
    TRANSITION_WORKFLOW = "transition_workflow"
    TRANSITION_STAGE = "transition_stage"
    TRANSITION_TASK = "transition_task"
    REQUEST_STAGE_APPROVAL = "request_stage_approval"
    REQUEST_TASK_APPROVAL = "request_task_approval"
    DECIDE_APPROVAL = "decide_approval"
    APPLY_APPROVAL = "apply_approval"
    ANALYSE = "analyse"
    ARCHIVE = "archive"
    RESTORE = "restore"
    DELETE = "delete"


class EnterpriseWorkflowCoordinatorOutcome(str, Enum):
    """Outcome of a coordinator command."""

    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"
    IDEMPOTENT_REPLAY = "idempotent_replay"


@dataclass(frozen=True)
class EnterpriseWorkflowCommandContext:
    """Execution context propagated through coordinated operations."""

    actor_id: str = "system"
    correlation_id: str = ""
    causation_id: str = ""
    idempotency_key: str = ""
    expected_revision: int | None = None
    persist: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    requested_at: str = dataclass_field(default_factory=utc_timestamp)

    def __post_init__(self) -> None:
        actor_id = str(self.actor_id or "").strip()

        if not actor_id:
            raise ValueError("Workflow coordinator actor ID is required.")
        if self.expected_revision is not None and self.expected_revision < 1:
            raise ValueError(
                "Expected workflow revision must be at least 1."
            )

        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(
            self,
            "correlation_id",
            str(self.correlation_id or "").strip(),
        )
        object.__setattr__(
            self,
            "causation_id",
            str(self.causation_id or "").strip(),
        )
        object.__setattr__(
            self,
            "idempotency_key",
            str(self.idempotency_key or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def with_defaults(
        self,
        *,
        correlation_id: str = "",
        causation_id: str = "",
    ) -> "EnterpriseWorkflowCommandContext":
        """Return a context with generated tracing identifiers."""

        return EnterpriseWorkflowCommandContext(
            actor_id=self.actor_id,
            correlation_id=(
                self.correlation_id
                or str(correlation_id or "").strip()
                or uuid4().hex
            ),
            causation_id=(
                self.causation_id
                or str(causation_id or "").strip()
            ),
            idempotency_key=self.idempotency_key,
            expected_revision=self.expected_revision,
            persist=self.persist,
            metadata=self.metadata,
            requested_at=self.requested_at,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "idempotency_key": self.idempotency_key,
            "expected_revision": self.expected_revision,
            "persist": self.persist,
            "metadata": redact_mapping(self.metadata),
            "requested_at": self.requested_at,
        }


@dataclass(frozen=True)
class EnterpriseWorkflowCoordinatorEvent:
    """Append-only coordinator audit event."""

    operation: EnterpriseWorkflowCoordinatorOperation
    outcome: EnterpriseWorkflowCoordinatorOutcome
    actor_id: str
    event_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    workflow_id: str = ""
    subject_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    idempotency_key: str = ""
    message: str = ""
    violations: tuple[str, ...] = ()
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    occurred_at: str = dataclass_field(default_factory=utc_timestamp)

    def __post_init__(self) -> None:
        if not str(self.event_id or "").strip():
            raise ValueError("Coordinator event ID is required.")
        if not str(self.actor_id or "").strip():
            raise ValueError("Coordinator event actor ID is required.")

        object.__setattr__(
            self,
            "violations",
            tuple(
                str(item).strip()
                for item in self.violations
                if str(item).strip()
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "event_id": self.event_id,
            "operation": self.operation.value,
            "outcome": self.outcome.value,
            "actor_id": self.actor_id,
            "workflow_id": self.workflow_id,
            "subject_id": self.subject_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "idempotency_key": self.idempotency_key,
            "message": self.message,
            "violations": list(self.violations),
            "metadata": redact_mapping(self.metadata),
            "occurred_at": self.occurred_at,
        }


@dataclass(frozen=True)
class EnterpriseWorkflowCoordinatorResult:
    """Unified result returned by coordinator commands."""

    operation: EnterpriseWorkflowCoordinatorOperation
    outcome: EnterpriseWorkflowCoordinatorOutcome
    event: EnterpriseWorkflowCoordinatorEvent
    workflow: EnterpriseWorkflow | None = None
    store_record: EnterpriseWorkflowStoreRecord | None = None
    approval_request: EnterpriseWorkflowApprovalRequest | None = None
    approval_result: EnterpriseWorkflowApprovalResult | None = None
    transition_result: EnterpriseWorkflowTransitionResult | None = None
    health_report: EnterpriseWorkflowHealthReport | None = None
    payload: dict[str, Any] = dataclass_field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        """Return whether the command succeeded or replayed safely."""

        return self.outcome in {
            EnterpriseWorkflowCoordinatorOutcome.SUCCEEDED,
            EnterpriseWorkflowCoordinatorOutcome.IDEMPOTENT_REPLAY,
        }

    @property
    def rejected(self) -> bool:
        """Return whether the command was rejected by policy."""

        return (
            self.outcome
            is EnterpriseWorkflowCoordinatorOutcome.REJECTED
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "operation": self.operation.value,
            "outcome": self.outcome.value,
            "succeeded": self.succeeded,
            "rejected": self.rejected,
            "event": self.event.as_dict(),
            "workflow": (
                self.workflow.as_dict()
                if self.workflow is not None
                else None
            ),
            "store_record": (
                self.store_record.as_dict()
                if self.store_record is not None
                else None
            ),
            "approval_request": (
                self.approval_request.as_dict()
                if self.approval_request is not None
                else None
            ),
            "approval_result": (
                self.approval_result.as_dict()
                if self.approval_result is not None
                else None
            ),
            "transition_result": (
                self.transition_result.as_dict()
                if self.transition_result is not None
                else None
            ),
            "health_report": (
                self.health_report.as_dict()
                if self.health_report is not None
                else None
            ),
            "payload": redact_mapping(self.payload),
        }


class EnterpriseWorkflowCoordinator:
    """Enterprise orchestration boundary for workflow operations."""

    def __init__(
        self,
        *,
        store: EnterpriseWorkflowStore | None = None,
        approval_manager: EnterpriseWorkflowApprovalManager | None = None,
        transition_engine: EnterpriseWorkflowTransitionEngine | None = None,
        analytics: EnterpriseWorkflowAnalytics | None = None,
    ) -> None:
        self._store = store or get_enterprise_workflow_store()
        self._approval_manager = (
            approval_manager
            or get_enterprise_workflow_approval_manager()
        )
        self._transition_engine = (
            transition_engine
            or get_enterprise_workflow_transition_engine(
                store=self._store
            )
        )
        self._analytics = (
            analytics or get_enterprise_workflow_analytics()
        )
        self._events: list[EnterpriseWorkflowCoordinatorEvent] = []
        self._idempotency_results: dict[
            str,
            EnterpriseWorkflowCoordinatorResult,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        workflow: EnterpriseWorkflow,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Create and optionally persist a workflow."""

        ctx = self._context(context, workflow.correlation_id)

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            record = None

            if ctx.persist:
                record = self._store.create(
                    workflow,
                    actor_id=ctx.actor_id,
                    metadata=self._operation_metadata(ctx),
                )

            return self._success(
                EnterpriseWorkflowCoordinatorOperation.CREATE,
                ctx,
                workflow=workflow,
                store_record=record,
                message="Enterprise workflow created.",
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.CREATE,
            ctx,
            execute,
            workflow_id=workflow.workflow_id,
        )

    def save(
        self,
        workflow: EnterpriseWorkflow,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Persist a workflow using optimistic concurrency."""

        ctx = self._context(context, workflow.correlation_id)

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            record = self._store.save(
                workflow,
                expected_revision=ctx.expected_revision,
                actor_id=ctx.actor_id,
                metadata=self._operation_metadata(ctx),
            )

            return self._success(
                EnterpriseWorkflowCoordinatorOperation.SAVE,
                ctx,
                workflow=workflow,
                store_record=record,
                message="Enterprise workflow saved.",
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.SAVE,
            ctx,
            execute,
            workflow_id=workflow.workflow_id,
        )

    def load(
        self,
        workflow_id: str,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
        include_archived: bool = False,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Load one workflow and its current store record."""

        ctx = self._context(context)
        cleaned_id = str(workflow_id or "").strip()

        if not cleaned_id:
            raise ValueError("Workflow ID is required.")

        record = self._store.get_record(
            cleaned_id,
            include_archived=include_archived,
        )

        return self._success(
            EnterpriseWorkflowCoordinatorOperation.LOAD,
            ctx,
            workflow=record.workflow,
            store_record=record,
            message="Enterprise workflow loaded.",
        )

    def refresh(
        self,
        workflow: EnterpriseWorkflow,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Refresh stage and task readiness and optionally persist."""

        ctx = self._context(context, workflow.correlation_id)

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            refreshed = self._transition_engine.refresh_readiness(
                workflow
            )
            record = None

            if ctx.persist and refreshed != workflow:
                record = self._store.save(
                    refreshed,
                    expected_revision=ctx.expected_revision,
                    actor_id=ctx.actor_id,
                    metadata={
                        **self._operation_metadata(ctx),
                        "operation": "refresh_readiness",
                    },
                )

            return self._success(
                EnterpriseWorkflowCoordinatorOperation.REFRESH,
                ctx,
                workflow=refreshed,
                store_record=record,
                message="Workflow readiness refreshed.",
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.REFRESH,
            ctx,
            execute,
            workflow_id=workflow.workflow_id,
        )

    def transition_workflow(
        self,
        workflow: EnterpriseWorkflow,
        target_status: EnterpriseWorkflowStatus,
        *,
        reason: str = "",
        force: bool = False,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Coordinate a workflow-level state transition."""

        ctx = self._context(context, workflow.correlation_id)

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            result = self._transition_engine.transition_workflow(
                workflow,
                target_status,
                actor_id=ctx.actor_id,
                reason=reason,
                expected_revision=ctx.expected_revision,
                force=force,
                persist=ctx.persist,
                metadata=self._operation_metadata(ctx),
            )

            return self._from_transition(
                EnterpriseWorkflowCoordinatorOperation.TRANSITION_WORKFLOW,
                ctx,
                result,
                subject_id=workflow.workflow_id,
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.TRANSITION_WORKFLOW,
            ctx,
            execute,
            workflow_id=workflow.workflow_id,
        )

    def transition_stage(
        self,
        workflow: EnterpriseWorkflow,
        stage_id: str,
        target_status: EnterpriseWorkflowStageStatus,
        *,
        approval_request: EnterpriseWorkflowApprovalRequest | None = None,
        reason: str = "",
        force: bool = False,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Coordinate a stage-level state transition."""

        ctx = self._context(context, workflow.correlation_id)
        cleaned_stage_id = str(stage_id or "").strip()

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            result = self._transition_engine.transition_stage(
                workflow,
                cleaned_stage_id,
                target_status,
                actor_id=ctx.actor_id,
                reason=reason,
                expected_revision=ctx.expected_revision,
                approval_request=approval_request,
                force=force,
                persist=ctx.persist,
                metadata=self._operation_metadata(ctx),
            )

            return self._from_transition(
                EnterpriseWorkflowCoordinatorOperation.TRANSITION_STAGE,
                ctx,
                result,
                subject_id=cleaned_stage_id,
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.TRANSITION_STAGE,
            ctx,
            execute,
            workflow_id=workflow.workflow_id,
            subject_id=cleaned_stage_id,
        )

    def transition_task(
        self,
        workflow: EnterpriseWorkflow,
        stage_id: str,
        task_id: str,
        target_status: EnterpriseWorkflowTaskStatus,
        *,
        approval_request: EnterpriseWorkflowApprovalRequest | None = None,
        reason: str = "",
        force: bool = False,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Coordinate a task-level state transition."""

        ctx = self._context(context, workflow.correlation_id)
        cleaned_task_id = str(task_id or "").strip()

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            result = self._transition_engine.transition_task(
                workflow,
                stage_id,
                cleaned_task_id,
                target_status,
                actor_id=ctx.actor_id,
                reason=reason,
                expected_revision=ctx.expected_revision,
                approval_request=approval_request,
                force=force,
                persist=ctx.persist,
                metadata=self._operation_metadata(ctx),
            )

            return self._from_transition(
                EnterpriseWorkflowCoordinatorOperation.TRANSITION_TASK,
                ctx,
                result,
                subject_id=cleaned_task_id,
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.TRANSITION_TASK,
            ctx,
            execute,
            workflow_id=workflow.workflow_id,
            subject_id=cleaned_task_id,
        )

    def request_stage_approval(
        self,
        workflow: EnterpriseWorkflow,
        stage_id: str,
        *,
        reason: str = "",
        expires_at: str = "",
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Create a governed approval request for a workflow stage."""

        ctx = self._context(context, workflow.correlation_id)
        cleaned_stage_id = str(stage_id or "").strip()

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            request = self._approval_manager.create_for_stage(
                workflow,
                cleaned_stage_id,
                requested_by=ctx.actor_id,
                reason=reason,
                expires_at=expires_at,
                metadata=self._operation_metadata(ctx),
            )

            return self._success(
                EnterpriseWorkflowCoordinatorOperation.REQUEST_STAGE_APPROVAL,
                ctx,
                workflow=workflow,
                approval_request=request,
                subject_id=cleaned_stage_id,
                message="Stage approval requested.",
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.REQUEST_STAGE_APPROVAL,
            ctx,
            execute,
            workflow_id=workflow.workflow_id,
            subject_id=cleaned_stage_id,
        )

    def request_task_approval(
        self,
        workflow: EnterpriseWorkflow,
        stage_id: str,
        task_id: str,
        *,
        required_approvals: int = 1,
        approver_roles: Iterable[str] = (),
        reason: str = "",
        expires_at: str = "",
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Create a governed approval request for a workflow task."""

        ctx = self._context(context, workflow.correlation_id)
        cleaned_task_id = str(task_id or "").strip()

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            request = self._approval_manager.create_for_task(
                workflow,
                stage_id,
                cleaned_task_id,
                requested_by=ctx.actor_id,
                required_approvals=required_approvals,
                approver_roles=tuple(approver_roles),
                reason=reason,
                expires_at=expires_at,
                metadata=self._operation_metadata(ctx),
            )

            return self._success(
                EnterpriseWorkflowCoordinatorOperation.REQUEST_TASK_APPROVAL,
                ctx,
                workflow=workflow,
                approval_request=request,
                subject_id=cleaned_task_id,
                message="Task approval requested.",
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.REQUEST_TASK_APPROVAL,
            ctx,
            execute,
            workflow_id=workflow.workflow_id,
            subject_id=cleaned_task_id,
        )

    def decide_approval(
        self,
        request_id: str,
        decision: EnterpriseWorkflowApprovalDecision,
        *,
        approver_roles: Iterable[str] = (),
        comment: str = "",
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Record a governed approval decision."""

        ctx = self._context(context)
        cleaned_request_id = str(request_id or "").strip()

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            decision_result = self._approval_manager.decide(
                cleaned_request_id,
                approver_id=ctx.actor_id,
                decision=decision,
                approver_roles=tuple(approver_roles),
                comment=comment,
                metadata=self._operation_metadata(ctx),
            )
            outcome = (
                EnterpriseWorkflowCoordinatorOutcome.SUCCEEDED
                if decision_result.accepted
                else EnterpriseWorkflowCoordinatorOutcome.REJECTED
            )
            event = self._event(
                EnterpriseWorkflowCoordinatorOperation.DECIDE_APPROVAL,
                outcome,
                ctx,
                workflow_id=decision_result.request.workflow_id,
                subject_id=decision_result.request.subject_id,
                message=decision_result.message,
                violations=decision_result.violations,
            )

            return EnterpriseWorkflowCoordinatorResult(
                operation=(
                    EnterpriseWorkflowCoordinatorOperation.DECIDE_APPROVAL
                ),
                outcome=outcome,
                event=event,
                approval_request=decision_result.request,
                approval_result=decision_result,
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.DECIDE_APPROVAL,
            ctx,
            execute,
            subject_id=cleaned_request_id,
        )

    def apply_stage_approval(
        self,
        workflow: EnterpriseWorkflow,
        request_id: str,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Apply an approval decision to a workflow stage and persist it."""

        ctx = self._context(context, workflow.correlation_id)

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            request = self._approval_manager.get(request_id)

            if request.status not in {
                EnterpriseWorkflowApprovalStatus.APPROVED,
                EnterpriseWorkflowApprovalStatus.REJECTED,
            }:
                return self._rejected(
                    EnterpriseWorkflowCoordinatorOperation.APPLY_APPROVAL,
                    ctx,
                    workflow=workflow,
                    subject_id=request.subject_id,
                    message="Approval request is not terminally decided.",
                    violations=("approval_not_decided",),
                )

            updated = self._approval_manager.apply_stage_status(
                workflow,
                request_id,
            )
            record = None

            if ctx.persist:
                record = self._store.save(
                    updated,
                    expected_revision=ctx.expected_revision,
                    actor_id=ctx.actor_id,
                    metadata={
                        **self._operation_metadata(ctx),
                        "approval_request_id": request_id,
                    },
                )

            return self._success(
                EnterpriseWorkflowCoordinatorOperation.APPLY_APPROVAL,
                ctx,
                workflow=updated,
                store_record=record,
                approval_request=request,
                subject_id=request.subject_id,
                message="Approval decision applied to workflow stage.",
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.APPLY_APPROVAL,
            ctx,
            execute,
            workflow_id=workflow.workflow_id,
            subject_id=request_id,
        )

    def analyse(
        self,
        workflow: EnterpriseWorkflow,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Generate a complete workflow health report."""

        ctx = self._context(context, workflow.correlation_id)
        approvals = self._approval_manager.list_requests(
            workflow_id=workflow.workflow_id
        )
        transitions = self._transition_engine.history(
            workflow_id=workflow.workflow_id
        )

        try:
            record = self._store.get_record(
                workflow.workflow_id,
                include_archived=True,
            )
        except (KeyError, ValueError):
            record = None

        report = self._analytics.analyse(
            workflow,
            approvals=approvals,
            transitions=transitions,
            store_record=record,
            metadata=self._operation_metadata(ctx),
        )

        return self._success(
            EnterpriseWorkflowCoordinatorOperation.ANALYSE,
            ctx,
            workflow=workflow,
            store_record=record,
            health_report=report,
            message="Workflow health analysis completed.",
        )

    def analyse_portfolio(
        self,
        *,
        query: EnterpriseWorkflowStoreQuery | None = None,
        include_archived: bool = False,
        top_bottleneck_limit: int = 10,
    ) -> EnterpriseWorkflowPortfolioReport:
        """Generate portfolio analytics from stored workflows."""

        records = self._store.list_records(
            query=query,
            include_archived=include_archived,
        )
        workflows = tuple(record.workflow for record in records)
        approvals = tuple(
            request
            for workflow in workflows
            for request in self._approval_manager.list_requests(
                workflow_id=workflow.workflow_id
            )
        )
        transitions = tuple(
            event
            for workflow in workflows
            for event in self._transition_engine.history(
                workflow_id=workflow.workflow_id
            )
        )

        return self._analytics.analyse_portfolio(
            workflows,
            approvals=approvals,
            transitions=transitions,
            store_records=records,
            top_bottleneck_limit=top_bottleneck_limit,
        )

    def archive(
        self,
        workflow_id: str,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Archive a stored workflow."""

        ctx = self._context(context)
        cleaned_id = str(workflow_id or "").strip()

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            record = self._store.archive(
                cleaned_id,
                expected_revision=ctx.expected_revision,
                actor_id=ctx.actor_id,
                metadata=self._operation_metadata(ctx),
            )

            return self._success(
                EnterpriseWorkflowCoordinatorOperation.ARCHIVE,
                ctx,
                workflow=record.workflow,
                store_record=record,
                message="Enterprise workflow archived.",
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.ARCHIVE,
            ctx,
            execute,
            workflow_id=cleaned_id,
        )

    def restore(
        self,
        workflow_id: str,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Restore an archived workflow."""

        ctx = self._context(context)
        cleaned_id = str(workflow_id or "").strip()

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            record = self._store.restore(
                cleaned_id,
                expected_revision=ctx.expected_revision,
                actor_id=ctx.actor_id,
                metadata=self._operation_metadata(ctx),
            )

            return self._success(
                EnterpriseWorkflowCoordinatorOperation.RESTORE,
                ctx,
                workflow=record.workflow,
                store_record=record,
                message="Enterprise workflow restored.",
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.RESTORE,
            ctx,
            execute,
            workflow_id=cleaned_id,
        )

    def delete(
        self,
        workflow_id: str,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Delete a stored workflow through the configured store."""

        ctx = self._context(context)
        cleaned_id = str(workflow_id or "").strip()

        def execute() -> EnterpriseWorkflowCoordinatorResult:
            deleted = self._store.delete(
                cleaned_id,
                expected_revision=ctx.expected_revision,
                actor_id=ctx.actor_id,
                metadata=self._operation_metadata(ctx),
            )

            if isinstance(deleted, EnterpriseWorkflowStoreRecord):
                workflow = deleted.workflow
                record = deleted
            else:
                workflow = None
                record = None

            return self._success(
                EnterpriseWorkflowCoordinatorOperation.DELETE,
                ctx,
                workflow=workflow,
                store_record=record,
                message="Enterprise workflow deleted.",
                payload={"deleted": bool(deleted)},
            )

        return self._execute_idempotent(
            EnterpriseWorkflowCoordinatorOperation.DELETE,
            ctx,
            execute,
            workflow_id=cleaned_id,
        )

    def events(
        self,
        *,
        workflow_id: str | None = None,
        operation: EnterpriseWorkflowCoordinatorOperation | None = None,
        outcome: EnterpriseWorkflowCoordinatorOutcome | None = None,
    ) -> tuple[EnterpriseWorkflowCoordinatorEvent, ...]:
        """Return coordinator audit events matching optional filters."""

        cleaned_workflow_id = (
            str(workflow_id).strip()
            if workflow_id is not None
            else None
        )

        with self._lock:
            events = tuple(self._events)

        return tuple(
            event
            for event in events
            if (
                cleaned_workflow_id is None
                or event.workflow_id == cleaned_workflow_id
            )
            and (
                operation is None
                or event.operation is operation
            )
            and (
                outcome is None
                or event.outcome is outcome
            )
        )

    def clear_runtime_state(self) -> None:
        """Clear coordinator events and idempotency cache."""

        with self._lock:
            self._events.clear()
            self._idempotency_results.clear()

    def _execute_idempotent(
        self,
        operation: EnterpriseWorkflowCoordinatorOperation,
        context: EnterpriseWorkflowCommandContext,
        execute: Callable[[], EnterpriseWorkflowCoordinatorResult],
        *,
        workflow_id: str = "",
        subject_id: str = "",
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Execute once for an idempotency key and replay safely."""

        key = context.idempotency_key

        with self._lock:
            if key and key in self._idempotency_results:
                previous = self._idempotency_results[key]
                replay_event = self._event(
                    operation,
                    EnterpriseWorkflowCoordinatorOutcome.IDEMPOTENT_REPLAY,
                    context,
                    workflow_id=(
                        workflow_id
                        or previous.event.workflow_id
                    ),
                    subject_id=(
                        subject_id
                        or previous.event.subject_id
                    ),
                    message="Idempotent coordinator result replayed.",
                    metadata={
                        "original_event_id": previous.event.event_id,
                    },
                )

                return EnterpriseWorkflowCoordinatorResult(
                    operation=operation,
                    outcome=(
                        EnterpriseWorkflowCoordinatorOutcome.IDEMPOTENT_REPLAY
                    ),
                    event=replay_event,
                    workflow=previous.workflow,
                    store_record=previous.store_record,
                    approval_request=previous.approval_request,
                    approval_result=previous.approval_result,
                    transition_result=previous.transition_result,
                    health_report=previous.health_report,
                    payload=previous.payload,
                )

        try:
            result = execute()
        except Exception as exc:
            failed = self._failed(
                operation,
                context,
                workflow_id=workflow_id,
                subject_id=subject_id,
                message=str(exc) or exc.__class__.__name__,
                metadata={
                    "exception_type": exc.__class__.__name__,
                },
            )

            with self._lock:
                if key:
                    self._idempotency_results[key] = failed

            raise

        with self._lock:
            if key:
                self._idempotency_results[key] = result

        return result

    def _from_transition(
        self,
        operation: EnterpriseWorkflowCoordinatorOperation,
        context: EnterpriseWorkflowCommandContext,
        result: EnterpriseWorkflowTransitionResult,
        *,
        subject_id: str,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Convert a transition result into the coordinator contract."""

        if result.rejected:
            return self._rejected(
                operation,
                context,
                workflow=result.workflow,
                transition_result=result,
                subject_id=subject_id,
                message="Workflow transition rejected.",
                violations=result.event.violations,
            )

        return self._success(
            operation,
            context,
            workflow=result.workflow,
            store_record=result.persisted_record,
            transition_result=result,
            subject_id=subject_id,
            message="Workflow transition applied.",
        )

    def _success(
        self,
        operation: EnterpriseWorkflowCoordinatorOperation,
        context: EnterpriseWorkflowCommandContext,
        *,
        workflow: EnterpriseWorkflow | None = None,
        store_record: EnterpriseWorkflowStoreRecord | None = None,
        approval_request: EnterpriseWorkflowApprovalRequest | None = None,
        transition_result: EnterpriseWorkflowTransitionResult | None = None,
        health_report: EnterpriseWorkflowHealthReport | None = None,
        subject_id: str = "",
        message: str = "",
        payload: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        event = self._event(
            operation,
            EnterpriseWorkflowCoordinatorOutcome.SUCCEEDED,
            context,
            workflow_id=(
                workflow.workflow_id
                if workflow is not None
                else ""
            ),
            subject_id=subject_id,
            message=message,
        )

        return EnterpriseWorkflowCoordinatorResult(
            operation=operation,
            outcome=EnterpriseWorkflowCoordinatorOutcome.SUCCEEDED,
            event=event,
            workflow=workflow,
            store_record=store_record,
            approval_request=approval_request,
            transition_result=transition_result,
            health_report=health_report,
            payload=redact_mapping(dict(payload or {})),
        )

    def _rejected(
        self,
        operation: EnterpriseWorkflowCoordinatorOperation,
        context: EnterpriseWorkflowCommandContext,
        *,
        workflow: EnterpriseWorkflow | None = None,
        transition_result: EnterpriseWorkflowTransitionResult | None = None,
        subject_id: str = "",
        message: str = "",
        violations: Iterable[str] = (),
    ) -> EnterpriseWorkflowCoordinatorResult:
        event = self._event(
            operation,
            EnterpriseWorkflowCoordinatorOutcome.REJECTED,
            context,
            workflow_id=(
                workflow.workflow_id
                if workflow is not None
                else ""
            ),
            subject_id=subject_id,
            message=message,
            violations=tuple(violations),
        )

        return EnterpriseWorkflowCoordinatorResult(
            operation=operation,
            outcome=EnterpriseWorkflowCoordinatorOutcome.REJECTED,
            event=event,
            workflow=workflow,
            transition_result=transition_result,
        )

    def _failed(
        self,
        operation: EnterpriseWorkflowCoordinatorOperation,
        context: EnterpriseWorkflowCommandContext,
        *,
        workflow_id: str = "",
        subject_id: str = "",
        message: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        event = self._event(
            operation,
            EnterpriseWorkflowCoordinatorOutcome.FAILED,
            context,
            workflow_id=workflow_id,
            subject_id=subject_id,
            message=message,
            metadata=metadata,
        )

        return EnterpriseWorkflowCoordinatorResult(
            operation=operation,
            outcome=EnterpriseWorkflowCoordinatorOutcome.FAILED,
            event=event,
        )

    def _event(
        self,
        operation: EnterpriseWorkflowCoordinatorOperation,
        outcome: EnterpriseWorkflowCoordinatorOutcome,
        context: EnterpriseWorkflowCommandContext,
        *,
        workflow_id: str = "",
        subject_id: str = "",
        message: str = "",
        violations: Iterable[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowCoordinatorEvent:
        event = EnterpriseWorkflowCoordinatorEvent(
            operation=operation,
            outcome=outcome,
            actor_id=context.actor_id,
            workflow_id=str(workflow_id or "").strip(),
            subject_id=str(subject_id or "").strip(),
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            idempotency_key=context.idempotency_key,
            message=str(message or "").strip(),
            violations=tuple(violations),
            metadata={
                **redact_mapping(context.metadata),
                **redact_mapping(dict(metadata or {})),
            },
        )

        with self._lock:
            self._events.append(event)

        return event

    @staticmethod
    def _context(
        context: EnterpriseWorkflowCommandContext | None,
        correlation_id: str = "",
    ) -> EnterpriseWorkflowCommandContext:
        base = context or EnterpriseWorkflowCommandContext()
        return base.with_defaults(correlation_id=correlation_id)

    @staticmethod
    def _operation_metadata(
        context: EnterpriseWorkflowCommandContext,
    ) -> dict[str, Any]:
        return {
            **redact_mapping(context.metadata),
            "correlation_id": context.correlation_id,
            "causation_id": context.causation_id,
            "idempotency_key": context.idempotency_key,
            "requested_at": context.requested_at,
        }


_enterprise_workflow_coordinator: EnterpriseWorkflowCoordinator | None = None
_enterprise_workflow_coordinator_lock = RLock()


def get_enterprise_workflow_coordinator(
    *,
    store: EnterpriseWorkflowStore | None = None,
    approval_manager: EnterpriseWorkflowApprovalManager | None = None,
    transition_engine: EnterpriseWorkflowTransitionEngine | None = None,
    analytics: EnterpriseWorkflowAnalytics | None = None,
) -> EnterpriseWorkflowCoordinator:
    """Return the process-wide enterprise workflow coordinator."""

    global _enterprise_workflow_coordinator

    with _enterprise_workflow_coordinator_lock:
        if _enterprise_workflow_coordinator is None:
            _enterprise_workflow_coordinator = (
                EnterpriseWorkflowCoordinator(
                    store=store,
                    approval_manager=approval_manager,
                    transition_engine=transition_engine,
                    analytics=analytics,
                )
            )

        return _enterprise_workflow_coordinator


# Backward-compatible aliases for earlier Package V integrations.
WorkflowCoordinatorOperation = EnterpriseWorkflowCoordinatorOperation
WorkflowCoordinatorOutcome = EnterpriseWorkflowCoordinatorOutcome
WorkflowCommandContext = EnterpriseWorkflowCommandContext
WorkflowCoordinatorEvent = EnterpriseWorkflowCoordinatorEvent
WorkflowCoordinatorResult = EnterpriseWorkflowCoordinatorResult
WorkflowCoordinator = EnterpriseWorkflowCoordinator
get_workflow_coordinator = get_enterprise_workflow_coordinator