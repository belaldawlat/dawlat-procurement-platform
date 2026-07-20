"""Governed state transitions for enterprise workflows.

Package V - Enterprise Workflow Intelligence.

The transition engine applies immutable workflow, stage, and task changes;
validates dependency gates; enforces approval requirements; records transition
history; and optionally persists successful changes through the enterprise
workflow store using optimistic concurrency.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Iterable, Mapping
from uuid import uuid4

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_approval import (
    EnterpriseWorkflowApprovalRequest,
    EnterpriseWorkflowApprovalStatus,
)
from app.orchestration.enterprise_workflow_models import (
    EnterpriseWorkflow,
    EnterpriseWorkflowApprovalMode,
    EnterpriseWorkflowStage,
    EnterpriseWorkflowStageStatus,
    EnterpriseWorkflowStatus,
    EnterpriseWorkflowTask,
    EnterpriseWorkflowTaskStatus,
)
from app.orchestration.enterprise_workflow_store import (
    EnterpriseWorkflowStore,
    EnterpriseWorkflowStoreRecord,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class EnterpriseWorkflowTransitionSubjectType(str, Enum):
    """Workflow object types supported by the transition engine."""

    WORKFLOW = "workflow"
    STAGE = "stage"
    TASK = "task"


class EnterpriseWorkflowTransitionOutcome(str, Enum):
    """Possible transition execution outcomes."""

    APPLIED = "applied"
    REJECTED = "rejected"
    NO_CHANGE = "no_change"


@dataclass(frozen=True)
class EnterpriseWorkflowTransitionRequest:
    """Immutable request to change one workflow object state."""

    workflow_id: str
    subject_type: EnterpriseWorkflowTransitionSubjectType
    target_status: str
    subject_id: str = ""
    stage_id: str = ""
    request_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    actor_id: str = "system"
    reason: str = ""
    expected_revision: int | None = None
    approval_request: EnterpriseWorkflowApprovalRequest | None = None
    force: bool = False
    correlation_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    requested_at: str = dataclass_field(default_factory=utc_timestamp)

    def __post_init__(self) -> None:
        request_id = str(self.request_id or "").strip()
        workflow_id = str(self.workflow_id or "").strip()
        subject_id = str(self.subject_id or "").strip()
        stage_id = str(self.stage_id or "").strip()
        actor_id = str(self.actor_id or "").strip()
        target_status = str(self.target_status or "").strip()

        if not request_id:
            raise ValueError("Workflow transition request ID is required.")
        if not workflow_id:
            raise ValueError("Workflow transition workflow ID is required.")
        if not actor_id:
            raise ValueError("Workflow transition actor ID is required.")
        if not target_status:
            raise ValueError("Workflow transition target status is required.")
        if self.expected_revision is not None and self.expected_revision < 1:
            raise ValueError(
                "Expected workflow revision must be at least 1."
            )
        if (
            self.subject_type
            in {
                EnterpriseWorkflowTransitionSubjectType.STAGE,
                EnterpriseWorkflowTransitionSubjectType.TASK,
            }
            and not subject_id
        ):
            raise ValueError(
                "Stage and task transitions require a subject ID."
            )
        if (
            self.subject_type
            is EnterpriseWorkflowTransitionSubjectType.TASK
            and not stage_id
        ):
            raise ValueError(
                "Task transitions require the containing stage ID."
            )

        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "workflow_id", workflow_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "stage_id", stage_id)
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "target_status", target_status)
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

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "subject_type": self.subject_type.value,
            "subject_id": self.subject_id,
            "stage_id": self.stage_id,
            "target_status": self.target_status,
            "actor_id": self.actor_id,
            "reason": self.reason,
            "expected_revision": self.expected_revision,
            "approval_request_id": (
                self.approval_request.request_id
                if self.approval_request is not None
                else ""
            ),
            "force": self.force,
            "correlation_id": self.correlation_id,
            "metadata": redact_mapping(self.metadata),
            "requested_at": self.requested_at,
        }


@dataclass(frozen=True)
class EnterpriseWorkflowTransitionEvent:
    """Append-only audit event for one transition attempt."""

    request_id: str
    workflow_id: str
    subject_type: EnterpriseWorkflowTransitionSubjectType
    subject_id: str
    previous_status: str
    target_status: str
    outcome: EnterpriseWorkflowTransitionOutcome
    actor_id: str
    event_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    reason: str = ""
    violations: tuple[str, ...] = ()
    correlation_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    occurred_at: str = dataclass_field(default_factory=utc_timestamp)

    def __post_init__(self) -> None:
        required = {
            "event_id": self.event_id,
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "actor_id": self.actor_id,
            "previous_status": self.previous_status,
            "target_status": self.target_status,
        }

        for name, value in required.items():
            if not str(value or "").strip():
                raise ValueError(
                    f"Workflow transition {name.replace('_', ' ')} "
                    "is required."
                )

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
            "request_id": self.request_id,
            "workflow_id": self.workflow_id,
            "subject_type": self.subject_type.value,
            "subject_id": self.subject_id,
            "previous_status": self.previous_status,
            "target_status": self.target_status,
            "outcome": self.outcome.value,
            "actor_id": self.actor_id,
            "reason": self.reason,
            "violations": list(self.violations),
            "correlation_id": self.correlation_id,
            "metadata": redact_mapping(self.metadata),
            "occurred_at": self.occurred_at,
        }


@dataclass(frozen=True)
class EnterpriseWorkflowTransitionResult:
    """Result of a governed transition request."""

    workflow: EnterpriseWorkflow
    event: EnterpriseWorkflowTransitionEvent
    persisted_record: EnterpriseWorkflowStoreRecord | None = None

    @property
    def applied(self) -> bool:
        """Return whether the requested transition was applied."""

        return self.event.outcome is EnterpriseWorkflowTransitionOutcome.APPLIED

    @property
    def rejected(self) -> bool:
        """Return whether the requested transition was rejected."""

        return (
            self.event.outcome
            is EnterpriseWorkflowTransitionOutcome.REJECTED
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "workflow": self.workflow.as_dict(),
            "event": self.event.as_dict(),
            "persisted_record": (
                self.persisted_record.as_dict()
                if self.persisted_record is not None
                else None
            ),
            "applied": self.applied,
            "rejected": self.rejected,
        }


class EnterpriseWorkflowTransitionEngine:
    """Thread-safe governed transition engine."""

    _WORKFLOW_TRANSITIONS: dict[
        EnterpriseWorkflowStatus,
        frozenset[EnterpriseWorkflowStatus],
    ] = {
        EnterpriseWorkflowStatus.DRAFT: frozenset(
            {
                EnterpriseWorkflowStatus.VALIDATED,
                EnterpriseWorkflowStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStatus.VALIDATED: frozenset(
            {
                EnterpriseWorkflowStatus.ACTIVE,
                EnterpriseWorkflowStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStatus.ACTIVE: frozenset(
            {
                EnterpriseWorkflowStatus.PAUSED,
                EnterpriseWorkflowStatus.COMPLETED,
                EnterpriseWorkflowStatus.FAILED,
                EnterpriseWorkflowStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStatus.PAUSED: frozenset(
            {
                EnterpriseWorkflowStatus.ACTIVE,
                EnterpriseWorkflowStatus.FAILED,
                EnterpriseWorkflowStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStatus.COMPLETED: frozenset(
            {EnterpriseWorkflowStatus.ARCHIVED}
        ),
        EnterpriseWorkflowStatus.FAILED: frozenset(
            {
                EnterpriseWorkflowStatus.PAUSED,
                EnterpriseWorkflowStatus.CANCELLED,
                EnterpriseWorkflowStatus.ARCHIVED,
            }
        ),
        EnterpriseWorkflowStatus.CANCELLED: frozenset(
            {EnterpriseWorkflowStatus.ARCHIVED}
        ),
        EnterpriseWorkflowStatus.ARCHIVED: frozenset(),
    }

    _STAGE_TRANSITIONS: dict[
        EnterpriseWorkflowStageStatus,
        frozenset[EnterpriseWorkflowStageStatus],
    ] = {
        EnterpriseWorkflowStageStatus.PENDING: frozenset(
            {
                EnterpriseWorkflowStageStatus.READY,
                EnterpriseWorkflowStageStatus.BLOCKED,
                EnterpriseWorkflowStageStatus.SKIPPED,
                EnterpriseWorkflowStageStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStageStatus.READY: frozenset(
            {
                EnterpriseWorkflowStageStatus.IN_PROGRESS,
                EnterpriseWorkflowStageStatus.BLOCKED,
                EnterpriseWorkflowStageStatus.SKIPPED,
                EnterpriseWorkflowStageStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStageStatus.IN_PROGRESS: frozenset(
            {
                EnterpriseWorkflowStageStatus.AWAITING_APPROVAL,
                EnterpriseWorkflowStageStatus.COMPLETED,
                EnterpriseWorkflowStageStatus.BLOCKED,
                EnterpriseWorkflowStageStatus.REJECTED,
                EnterpriseWorkflowStageStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStageStatus.AWAITING_APPROVAL: frozenset(
            {
                EnterpriseWorkflowStageStatus.APPROVED,
                EnterpriseWorkflowStageStatus.REJECTED,
                EnterpriseWorkflowStageStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStageStatus.APPROVED: frozenset(
            {
                EnterpriseWorkflowStageStatus.COMPLETED,
                EnterpriseWorkflowStageStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStageStatus.REJECTED: frozenset(
            {
                EnterpriseWorkflowStageStatus.IN_PROGRESS,
                EnterpriseWorkflowStageStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStageStatus.BLOCKED: frozenset(
            {
                EnterpriseWorkflowStageStatus.READY,
                EnterpriseWorkflowStageStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowStageStatus.COMPLETED: frozenset(),
        EnterpriseWorkflowStageStatus.SKIPPED: frozenset(),
        EnterpriseWorkflowStageStatus.CANCELLED: frozenset(),
    }

    _TASK_TRANSITIONS: dict[
        EnterpriseWorkflowTaskStatus,
        frozenset[EnterpriseWorkflowTaskStatus],
    ] = {
        EnterpriseWorkflowTaskStatus.PENDING: frozenset(
            {
                EnterpriseWorkflowTaskStatus.READY,
                EnterpriseWorkflowTaskStatus.BLOCKED,
                EnterpriseWorkflowTaskStatus.SKIPPED,
                EnterpriseWorkflowTaskStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowTaskStatus.READY: frozenset(
            {
                EnterpriseWorkflowTaskStatus.RUNNING,
                EnterpriseWorkflowTaskStatus.BLOCKED,
                EnterpriseWorkflowTaskStatus.SKIPPED,
                EnterpriseWorkflowTaskStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowTaskStatus.RUNNING: frozenset(
            {
                EnterpriseWorkflowTaskStatus.SUCCEEDED,
                EnterpriseWorkflowTaskStatus.FAILED,
                EnterpriseWorkflowTaskStatus.BLOCKED,
                EnterpriseWorkflowTaskStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowTaskStatus.FAILED: frozenset(
            {
                EnterpriseWorkflowTaskStatus.READY,
                EnterpriseWorkflowTaskStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowTaskStatus.BLOCKED: frozenset(
            {
                EnterpriseWorkflowTaskStatus.READY,
                EnterpriseWorkflowTaskStatus.CANCELLED,
            }
        ),
        EnterpriseWorkflowTaskStatus.SUCCEEDED: frozenset(),
        EnterpriseWorkflowTaskStatus.SKIPPED: frozenset(),
        EnterpriseWorkflowTaskStatus.CANCELLED: frozenset(),
    }

    def __init__(
        self,
        *,
        store: EnterpriseWorkflowStore | None = None,
    ) -> None:
        self._store = store
        self._events: list[EnterpriseWorkflowTransitionEvent] = []
        self._lock = RLock()

    def transition(
        self,
        workflow: EnterpriseWorkflow,
        request: EnterpriseWorkflowTransitionRequest,
        *,
        persist: bool = False,
    ) -> EnterpriseWorkflowTransitionResult:
        """Validate and apply one workflow, stage, or task transition."""

        if not isinstance(workflow, EnterpriseWorkflow):
            raise TypeError(
                "Workflow transition requires EnterpriseWorkflow."
            )
        if not isinstance(request, EnterpriseWorkflowTransitionRequest):
            raise TypeError(
                "Workflow transition requires a transition request."
            )
        if request.workflow_id != workflow.workflow_id:
            raise ValueError(
                "Transition request does not belong to the workflow."
            )

        with self._lock:
            if (
                request.subject_type
                is EnterpriseWorkflowTransitionSubjectType.WORKFLOW
            ):
                updated, previous, violations = (
                    self._transition_workflow(workflow, request)
                )
                subject_id = workflow.workflow_id
            elif (
                request.subject_type
                is EnterpriseWorkflowTransitionSubjectType.STAGE
            ):
                updated, previous, violations = self._transition_stage(
                    workflow,
                    request,
                )
                subject_id = request.subject_id
            else:
                updated, previous, violations = self._transition_task(
                    workflow,
                    request,
                )
                subject_id = request.subject_id

            target = request.target_status
            outcome = (
                EnterpriseWorkflowTransitionOutcome.REJECTED
                if violations
                else (
                    EnterpriseWorkflowTransitionOutcome.NO_CHANGE
                    if updated == workflow
                    else EnterpriseWorkflowTransitionOutcome.APPLIED
                )
            )

            event = EnterpriseWorkflowTransitionEvent(
                request_id=request.request_id,
                workflow_id=workflow.workflow_id,
                subject_type=request.subject_type,
                subject_id=subject_id,
                previous_status=previous,
                target_status=target,
                outcome=outcome,
                actor_id=request.actor_id,
                reason=request.reason,
                violations=tuple(violations),
                correlation_id=(
                    request.correlation_id or workflow.correlation_id
                ),
                metadata=request.metadata,
            )
            self._events.append(event)

            persisted_record = None

            if persist and outcome is EnterpriseWorkflowTransitionOutcome.APPLIED:
                if self._store is None:
                    raise RuntimeError(
                        "Workflow transition persistence requires a store."
                    )

                persisted_record = self._store.save(
                    updated,
                    expected_revision=request.expected_revision,
                    actor_id=request.actor_id,
                    metadata={
                        "transition_event_id": event.event_id,
                        "transition_request_id": request.request_id,
                    },
                )

            return EnterpriseWorkflowTransitionResult(
                workflow=updated,
                event=event,
                persisted_record=persisted_record,
            )

    def transition_workflow(
        self,
        workflow: EnterpriseWorkflow,
        target_status: EnterpriseWorkflowStatus,
        *,
        actor_id: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
        force: bool = False,
        persist: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowTransitionResult:
        """Convenience wrapper for workflow-level transitions."""

        return self.transition(
            workflow,
            EnterpriseWorkflowTransitionRequest(
                workflow_id=workflow.workflow_id,
                subject_type=(
                    EnterpriseWorkflowTransitionSubjectType.WORKFLOW
                ),
                target_status=target_status.value,
                actor_id=actor_id,
                reason=reason,
                expected_revision=expected_revision,
                force=force,
                correlation_id=workflow.correlation_id,
                metadata=redact_mapping(dict(metadata or {})),
            ),
            persist=persist,
        )

    def transition_stage(
        self,
        workflow: EnterpriseWorkflow,
        stage_id: str,
        target_status: EnterpriseWorkflowStageStatus,
        *,
        actor_id: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
        approval_request: EnterpriseWorkflowApprovalRequest | None = None,
        force: bool = False,
        persist: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowTransitionResult:
        """Convenience wrapper for stage-level transitions."""

        return self.transition(
            workflow,
            EnterpriseWorkflowTransitionRequest(
                workflow_id=workflow.workflow_id,
                subject_type=(
                    EnterpriseWorkflowTransitionSubjectType.STAGE
                ),
                subject_id=stage_id,
                target_status=target_status.value,
                actor_id=actor_id,
                reason=reason,
                expected_revision=expected_revision,
                approval_request=approval_request,
                force=force,
                correlation_id=workflow.correlation_id,
                metadata=redact_mapping(dict(metadata or {})),
            ),
            persist=persist,
        )

    def transition_task(
        self,
        workflow: EnterpriseWorkflow,
        stage_id: str,
        task_id: str,
        target_status: EnterpriseWorkflowTaskStatus,
        *,
        actor_id: str = "system",
        reason: str = "",
        expected_revision: int | None = None,
        approval_request: EnterpriseWorkflowApprovalRequest | None = None,
        force: bool = False,
        persist: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowTransitionResult:
        """Convenience wrapper for task-level transitions."""

        return self.transition(
            workflow,
            EnterpriseWorkflowTransitionRequest(
                workflow_id=workflow.workflow_id,
                subject_type=(
                    EnterpriseWorkflowTransitionSubjectType.TASK
                ),
                subject_id=task_id,
                stage_id=stage_id,
                target_status=target_status.value,
                actor_id=actor_id,
                reason=reason,
                expected_revision=expected_revision,
                approval_request=approval_request,
                force=force,
                correlation_id=workflow.correlation_id,
                metadata=redact_mapping(dict(metadata or {})),
            ),
            persist=persist,
        )

    def refresh_readiness(
        self,
        workflow: EnterpriseWorkflow,
    ) -> EnterpriseWorkflow:
        """Promote dependency-satisfied pending stages and tasks to ready."""

        completed_stages = {
            stage.stage_id
            for stage in workflow.stages
            if stage.status
            in {
                EnterpriseWorkflowStageStatus.COMPLETED,
                EnterpriseWorkflowStageStatus.SKIPPED,
            }
        }

        refreshed_stages: list[EnterpriseWorkflowStage] = []

        for stage in workflow.stages:
            stage_status = stage.status

            if (
                stage_status is EnterpriseWorkflowStageStatus.PENDING
                and set(stage.depends_on).issubset(completed_stages)
            ):
                stage_status = EnterpriseWorkflowStageStatus.READY

            completed_tasks = {
                task.task_id
                for task in stage.tasks
                if task.status
                in {
                    EnterpriseWorkflowTaskStatus.SUCCEEDED,
                    EnterpriseWorkflowTaskStatus.SKIPPED,
                }
            }
            refreshed_tasks: list[EnterpriseWorkflowTask] = []

            for task in stage.tasks:
                task_status = task.status

                if (
                    stage_status
                    in {
                        EnterpriseWorkflowStageStatus.READY,
                        EnterpriseWorkflowStageStatus.IN_PROGRESS,
                        EnterpriseWorkflowStageStatus.APPROVED,
                    }
                    and task_status
                    is EnterpriseWorkflowTaskStatus.PENDING
                    and set(task.depends_on).issubset(completed_tasks)
                ):
                    task_status = EnterpriseWorkflowTaskStatus.READY

                refreshed_tasks.append(
                    replace(task, status=task_status)
                )

            refreshed_stages.append(
                replace(
                    stage,
                    status=stage_status,
                    tasks=tuple(refreshed_tasks),
                )
            )

        return replace(workflow, stages=tuple(refreshed_stages))

    def history(
        self,
        *,
        workflow_id: str | None = None,
        subject_id: str | None = None,
        outcome: EnterpriseWorkflowTransitionOutcome | None = None,
    ) -> tuple[EnterpriseWorkflowTransitionEvent, ...]:
        """Return transition events matching optional criteria."""

        with self._lock:
            events = tuple(self._events)

        return tuple(
            event
            for event in events
            if (
                workflow_id is None
                or event.workflow_id == str(workflow_id).strip()
            )
            and (
                subject_id is None
                or event.subject_id == str(subject_id).strip()
            )
            and (outcome is None or event.outcome is outcome)
        )

    def clear_history(self) -> None:
        """Clear in-memory transition audit events."""

        with self._lock:
            self._events.clear()

    def _transition_workflow(
        self,
        workflow: EnterpriseWorkflow,
        request: EnterpriseWorkflowTransitionRequest,
    ) -> tuple[EnterpriseWorkflow, str, tuple[str, ...]]:
        try:
            target = EnterpriseWorkflowStatus(request.target_status)
        except ValueError:
            return (
                workflow,
                workflow.status.value,
                ("invalid_workflow_target_status",),
            )

        if target is workflow.status:
            return workflow, workflow.status.value, ()

        violations: list[str] = []

        if (
            not request.force
            and target not in self._WORKFLOW_TRANSITIONS[workflow.status]
        ):
            violations.append("workflow_transition_not_allowed")

        if target is EnterpriseWorkflowStatus.COMPLETED:
            incomplete = [
                stage.stage_id
                for stage in workflow.stages
                if stage.status
                not in {
                    EnterpriseWorkflowStageStatus.COMPLETED,
                    EnterpriseWorkflowStageStatus.SKIPPED,
                }
            ]
            if incomplete and not request.force:
                violations.append("workflow_has_incomplete_stages")

        if target is EnterpriseWorkflowStatus.ACTIVE:
            if not any(
                stage.status
                in {
                    EnterpriseWorkflowStageStatus.READY,
                    EnterpriseWorkflowStageStatus.IN_PROGRESS,
                    EnterpriseWorkflowStageStatus.APPROVED,
                }
                for stage in self.refresh_readiness(workflow).stages
            ):
                violations.append("workflow_has_no_ready_stage")

        if violations:
            return workflow, workflow.status.value, tuple(violations)

        updated = replace(workflow, status=target)

        if target is EnterpriseWorkflowStatus.ACTIVE:
            updated = self.refresh_readiness(updated)

        return updated, workflow.status.value, ()

    def _transition_stage(
        self,
        workflow: EnterpriseWorkflow,
        request: EnterpriseWorkflowTransitionRequest,
    ) -> tuple[EnterpriseWorkflow, str, tuple[str, ...]]:
        stage = self._find_stage(workflow, request.subject_id)

        try:
            target = EnterpriseWorkflowStageStatus(
                request.target_status
            )
        except ValueError:
            return (
                workflow,
                stage.status.value,
                ("invalid_stage_target_status",),
            )

        if target is stage.status:
            return workflow, stage.status.value, ()

        violations: list[str] = []

        if (
            not request.force
            and target not in self._STAGE_TRANSITIONS[stage.status]
        ):
            violations.append("stage_transition_not_allowed")

        if (
            target
            in {
                EnterpriseWorkflowStageStatus.READY,
                EnterpriseWorkflowStageStatus.IN_PROGRESS,
            }
            and not self._stage_dependencies_satisfied(
                workflow,
                stage,
            )
            and not request.force
        ):
            violations.append("stage_dependencies_not_satisfied")

        if (
            target is EnterpriseWorkflowStageStatus.COMPLETED
            and not self._stage_tasks_complete(stage)
            and not request.force
        ):
            violations.append("stage_has_incomplete_tasks")

        if (
            target is EnterpriseWorkflowStageStatus.COMPLETED
            and stage.approval_mode
            is not EnterpriseWorkflowApprovalMode.NONE
            and stage.status
            is not EnterpriseWorkflowStageStatus.APPROVED
            and not request.force
        ):
            violations.append("stage_approval_required")

        if (
            target
            in {
                EnterpriseWorkflowStageStatus.APPROVED,
                EnterpriseWorkflowStageStatus.REJECTED,
            }
            and not self._approval_matches(
                workflow,
                request,
                stage.stage_id,
                target,
            )
            and not request.force
        ):
            violations.append("valid_stage_approval_required")

        if violations:
            return workflow, stage.status.value, tuple(violations)

        stages = tuple(
            replace(item, status=target)
            if item.stage_id == stage.stage_id
            else item
            for item in workflow.stages
        )
        updated = replace(workflow, stages=stages)
        updated = self.refresh_readiness(updated)

        return updated, stage.status.value, ()

    def _transition_task(
        self,
        workflow: EnterpriseWorkflow,
        request: EnterpriseWorkflowTransitionRequest,
    ) -> tuple[EnterpriseWorkflow, str, tuple[str, ...]]:
        stage = self._find_stage(workflow, request.stage_id)
        task = self._find_task(stage, request.subject_id)

        try:
            target = EnterpriseWorkflowTaskStatus(
                request.target_status
            )
        except ValueError:
            return (
                workflow,
                task.status.value,
                ("invalid_task_target_status",),
            )

        if target is task.status:
            return workflow, task.status.value, ()

        violations: list[str] = []

        if (
            not request.force
            and target not in self._TASK_TRANSITIONS[task.status]
        ):
            violations.append("task_transition_not_allowed")

        if (
            target
            in {
                EnterpriseWorkflowTaskStatus.READY,
                EnterpriseWorkflowTaskStatus.RUNNING,
            }
            and not self._task_dependencies_satisfied(stage, task)
            and not request.force
        ):
            violations.append("task_dependencies_not_satisfied")

        if (
            target is EnterpriseWorkflowTaskStatus.RUNNING
            and stage.status
            not in {
                EnterpriseWorkflowStageStatus.READY,
                EnterpriseWorkflowStageStatus.IN_PROGRESS,
                EnterpriseWorkflowStageStatus.APPROVED,
            }
            and not request.force
        ):
            violations.append("containing_stage_not_executable")

        if (
            target is EnterpriseWorkflowTaskStatus.SUCCEEDED
            and task.requires_approval
            and not self._task_approval_matches(
                workflow,
                request,
                task.task_id,
            )
            and not request.force
        ):
            violations.append("valid_task_approval_required")

        if violations:
            return workflow, task.status.value, tuple(violations)

        updated_tasks = tuple(
            replace(item, status=target)
            if item.task_id == task.task_id
            else item
            for item in stage.tasks
        )

        updated_stage_status = stage.status

        if (
            target is EnterpriseWorkflowTaskStatus.RUNNING
            and stage.status is EnterpriseWorkflowStageStatus.READY
        ):
            updated_stage_status = (
                EnterpriseWorkflowStageStatus.IN_PROGRESS
            )

        updated_stage = replace(
            stage,
            tasks=updated_tasks,
            status=updated_stage_status,
        )

        if self._stage_tasks_complete(updated_stage):
            updated_stage = replace(
                updated_stage,
                status=(
                    EnterpriseWorkflowStageStatus.AWAITING_APPROVAL
                    if updated_stage.approval_mode
                    is not EnterpriseWorkflowApprovalMode.NONE
                    else EnterpriseWorkflowStageStatus.COMPLETED
                ),
            )

        stages = tuple(
            updated_stage
            if item.stage_id == stage.stage_id
            else item
            for item in workflow.stages
        )
        updated = self.refresh_readiness(
            replace(workflow, stages=stages)
        )

        return updated, task.status.value, ()

    @staticmethod
    def _find_stage(
        workflow: EnterpriseWorkflow,
        stage_id: str,
    ) -> EnterpriseWorkflowStage:
        cleaned_id = str(stage_id or "").strip()

        stage = next(
            (
                item
                for item in workflow.stages
                if item.stage_id == cleaned_id
            ),
            None,
        )

        if stage is None:
            raise KeyError("Workflow stage was not found.")

        return stage

    @staticmethod
    def _find_task(
        stage: EnterpriseWorkflowStage,
        task_id: str,
    ) -> EnterpriseWorkflowTask:
        cleaned_id = str(task_id or "").strip()

        task = next(
            (
                item
                for item in stage.tasks
                if item.task_id == cleaned_id
            ),
            None,
        )

        if task is None:
            raise KeyError("Workflow task was not found.")

        return task

    @staticmethod
    def _stage_dependencies_satisfied(
        workflow: EnterpriseWorkflow,
        stage: EnterpriseWorkflowStage,
    ) -> bool:
        completed = {
            item.stage_id
            for item in workflow.stages
            if item.status
            in {
                EnterpriseWorkflowStageStatus.COMPLETED,
                EnterpriseWorkflowStageStatus.SKIPPED,
            }
        }
        return set(stage.depends_on).issubset(completed)

    @staticmethod
    def _task_dependencies_satisfied(
        stage: EnterpriseWorkflowStage,
        task: EnterpriseWorkflowTask,
    ) -> bool:
        complete = {
            item.task_id
            for item in stage.tasks
            if item.status
            in {
                EnterpriseWorkflowTaskStatus.SUCCEEDED,
                EnterpriseWorkflowTaskStatus.SKIPPED,
            }
        }
        return set(task.depends_on).issubset(complete)

    @staticmethod
    def _stage_tasks_complete(stage: EnterpriseWorkflowStage) -> bool:
        return all(
            task.status
            in {
                EnterpriseWorkflowTaskStatus.SUCCEEDED,
                EnterpriseWorkflowTaskStatus.SKIPPED,
            }
            for task in stage.tasks
        )

    @staticmethod
    def _approval_matches(
        workflow: EnterpriseWorkflow,
        request: EnterpriseWorkflowTransitionRequest,
        subject_id: str,
        target: EnterpriseWorkflowStageStatus,
    ) -> bool:
        approval = request.approval_request

        if approval is None:
            return False
        if approval.workflow_id != workflow.workflow_id:
            return False
        if approval.subject_id != subject_id:
            return False

        expected = (
            EnterpriseWorkflowApprovalStatus.APPROVED
            if target is EnterpriseWorkflowStageStatus.APPROVED
            else EnterpriseWorkflowApprovalStatus.REJECTED
        )
        return approval.status is expected

    @staticmethod
    def _task_approval_matches(
        workflow: EnterpriseWorkflow,
        request: EnterpriseWorkflowTransitionRequest,
        subject_id: str,
    ) -> bool:
        approval = request.approval_request

        return bool(
            approval is not None
            and approval.workflow_id == workflow.workflow_id
            and approval.subject_id == subject_id
            and approval.status
            is EnterpriseWorkflowApprovalStatus.APPROVED
        )


_enterprise_workflow_transition_engine: (
    EnterpriseWorkflowTransitionEngine | None
) = None
_enterprise_workflow_transition_lock = RLock()


def get_enterprise_workflow_transition_engine(
    *,
    store: EnterpriseWorkflowStore | None = None,
) -> EnterpriseWorkflowTransitionEngine:
    """Return the process-wide workflow transition engine."""

    global _enterprise_workflow_transition_engine

    with _enterprise_workflow_transition_lock:
        if _enterprise_workflow_transition_engine is None:
            _enterprise_workflow_transition_engine = (
                EnterpriseWorkflowTransitionEngine(store=store)
            )
        elif store is not None:
            _enterprise_workflow_transition_engine._store = store

        return _enterprise_workflow_transition_engine


# Backward-compatible aliases for earlier Package V callers.
WorkflowTransitionSubjectType = EnterpriseWorkflowTransitionSubjectType
WorkflowTransitionOutcome = EnterpriseWorkflowTransitionOutcome
WorkflowTransitionRequest = EnterpriseWorkflowTransitionRequest
WorkflowTransitionEvent = EnterpriseWorkflowTransitionEvent
WorkflowTransitionResult = EnterpriseWorkflowTransitionResult
WorkflowTransitionEngine = EnterpriseWorkflowTransitionEngine
get_workflow_transition_engine = (
    get_enterprise_workflow_transition_engine
)