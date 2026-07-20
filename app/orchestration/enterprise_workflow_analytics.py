"""Enterprise workflow analytics and operational health intelligence.

Package V - Enterprise Workflow Intelligence.

This module calculates deterministic workflow, stage, task, approval, and
transition metrics without requiring a specific database or presentation
layer. It is designed for command centers, audit reports, orchestration
services, and the Package V intelligence coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_approval import (
    EnterpriseWorkflowApprovalRequest,
    EnterpriseWorkflowApprovalStatus,
)
from app.orchestration.enterprise_workflow_models import (
    EnterpriseWorkflow,
    EnterpriseWorkflowPriority,
    EnterpriseWorkflowStage,
    EnterpriseWorkflowStageStatus,
    EnterpriseWorkflowStatus,
    EnterpriseWorkflowTask,
    EnterpriseWorkflowTaskStatus,
)
from app.orchestration.enterprise_workflow_store import (
    EnterpriseWorkflowStoreRecord,
)
from app.orchestration.enterprise_workflow_transition import (
    EnterpriseWorkflowTransitionEvent,
    EnterpriseWorkflowTransitionOutcome,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO timestamp and normalise it to UTC."""

    cleaned = str(value or "").strip()

    if not cleaned:
        return None

    parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _duration_seconds(
    started_at: str | None,
    completed_at: str | None,
    *,
    now: datetime | None = None,
) -> float | None:
    """Return elapsed seconds between two timestamps."""

    start = _parse_timestamp(started_at)

    if start is None:
        return None

    end = _parse_timestamp(completed_at) or now or datetime.now(
        timezone.utc
    )

    return max(0.0, (end - start).total_seconds())


def _percentage(numerator: int | float, denominator: int | float) -> float:
    """Return a stable percentage value."""

    if denominator <= 0:
        return 0.0

    return round((float(numerator) / float(denominator)) * 100.0, 2)


@dataclass(frozen=True)
class EnterpriseWorkflowTaskMetrics:
    """Calculated task-level workflow metrics."""

    total: int = 0
    pending: int = 0
    ready: int = 0
    running: int = 0
    succeeded: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    cancelled: int = 0
    requires_approval: int = 0
    success_rate: float = 0.0
    completion_rate: float = 0.0
    failure_rate: float = 0.0
    blocked_rate: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "total": self.total,
            "pending": self.pending,
            "ready": self.ready,
            "running": self.running,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "cancelled": self.cancelled,
            "requires_approval": self.requires_approval,
            "success_rate": self.success_rate,
            "completion_rate": self.completion_rate,
            "failure_rate": self.failure_rate,
            "blocked_rate": self.blocked_rate,
        }


@dataclass(frozen=True)
class EnterpriseWorkflowStageMetrics:
    """Calculated stage-level workflow metrics."""

    total: int = 0
    pending: int = 0
    ready: int = 0
    in_progress: int = 0
    awaiting_approval: int = 0
    approved: int = 0
    rejected: int = 0
    completed: int = 0
    blocked: int = 0
    skipped: int = 0
    cancelled: int = 0
    completion_rate: float = 0.0
    blocked_rate: float = 0.0
    approval_wait_rate: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "total": self.total,
            "pending": self.pending,
            "ready": self.ready,
            "in_progress": self.in_progress,
            "awaiting_approval": self.awaiting_approval,
            "approved": self.approved,
            "rejected": self.rejected,
            "completed": self.completed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "cancelled": self.cancelled,
            "completion_rate": self.completion_rate,
            "blocked_rate": self.blocked_rate,
            "approval_wait_rate": self.approval_wait_rate,
        }


@dataclass(frozen=True)
class EnterpriseWorkflowApprovalMetrics:
    """Calculated workflow approval metrics."""

    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    expired: int = 0
    cancelled: int = 0
    not_required: int = 0
    approval_rate: float = 0.0
    rejection_rate: float = 0.0
    expiry_rate: float = 0.0
    average_decision_seconds: float = 0.0
    maximum_decision_seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "total": self.total,
            "pending": self.pending,
            "approved": self.approved,
            "rejected": self.rejected,
            "expired": self.expired,
            "cancelled": self.cancelled,
            "not_required": self.not_required,
            "approval_rate": self.approval_rate,
            "rejection_rate": self.rejection_rate,
            "expiry_rate": self.expiry_rate,
            "average_decision_seconds": self.average_decision_seconds,
            "maximum_decision_seconds": self.maximum_decision_seconds,
        }


@dataclass(frozen=True)
class EnterpriseWorkflowTransitionMetrics:
    """Calculated workflow transition metrics."""

    total: int = 0
    applied: int = 0
    rejected: int = 0
    no_change: int = 0
    application_rate: float = 0.0
    rejection_rate: float = 0.0
    violation_counts: dict[str, int] = dataclass_field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "violation_counts",
            dict(sorted(self.violation_counts.items())),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "total": self.total,
            "applied": self.applied,
            "rejected": self.rejected,
            "no_change": self.no_change,
            "application_rate": self.application_rate,
            "rejection_rate": self.rejection_rate,
            "violation_counts": dict(self.violation_counts),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowBottleneck:
    """One detected operational bottleneck."""

    workflow_id: str
    subject_type: str
    subject_id: str
    severity: str
    reason: str
    age_seconds: float = 0.0
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.workflow_id or "").strip():
            raise ValueError("Workflow bottleneck workflow ID is required.")
        if not str(self.subject_type or "").strip():
            raise ValueError("Workflow bottleneck subject type is required.")
        if not str(self.subject_id or "").strip():
            raise ValueError("Workflow bottleneck subject ID is required.")
        if self.severity not in {"low", "medium", "high", "critical"}:
            raise ValueError("Workflow bottleneck severity is invalid.")

        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "workflow_id": self.workflow_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "severity": self.severity,
            "reason": self.reason,
            "age_seconds": round(self.age_seconds, 2),
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowHealthReport:
    """Complete analytics report for one workflow."""

    workflow_id: str
    case_id: str
    template_id: str
    workflow_status: EnterpriseWorkflowStatus
    priority: EnterpriseWorkflowPriority
    health_score: float
    health_label: str
    stage_metrics: EnterpriseWorkflowStageMetrics
    task_metrics: EnterpriseWorkflowTaskMetrics
    approval_metrics: EnterpriseWorkflowApprovalMetrics
    transition_metrics: EnterpriseWorkflowTransitionMetrics
    bottlenecks: tuple[EnterpriseWorkflowBottleneck, ...] = ()
    recommendations: tuple[str, ...] = ()
    calculated_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.health_score <= 100.0:
            raise ValueError(
                "Workflow health score must be between 0 and 100."
            )
        if self.health_label not in {
            "healthy",
            "watch",
            "at_risk",
            "critical",
        }:
            raise ValueError("Workflow health label is invalid.")

        object.__setattr__(
            self,
            "bottlenecks",
            tuple(self.bottlenecks),
        )
        object.__setattr__(
            self,
            "recommendations",
            tuple(
                str(item).strip()
                for item in self.recommendations
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
            "workflow_id": self.workflow_id,
            "case_id": self.case_id,
            "template_id": self.template_id,
            "workflow_status": self.workflow_status.value,
            "priority": self.priority.value,
            "health_score": self.health_score,
            "health_label": self.health_label,
            "stage_metrics": self.stage_metrics.as_dict(),
            "task_metrics": self.task_metrics.as_dict(),
            "approval_metrics": self.approval_metrics.as_dict(),
            "transition_metrics": self.transition_metrics.as_dict(),
            "bottlenecks": [
                bottleneck.as_dict()
                for bottleneck in self.bottlenecks
            ],
            "recommendations": list(self.recommendations),
            "calculated_at": self.calculated_at,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowPortfolioReport:
    """Aggregated analytics across multiple workflows."""

    total_workflows: int
    status_counts: dict[str, int]
    priority_counts: dict[str, int]
    average_health_score: float
    healthy: int
    watch: int
    at_risk: int
    critical: int
    active_workflows: int
    completed_workflows: int
    failed_workflows: int
    blocked_stages: int
    failed_tasks: int
    pending_approvals: int
    top_bottlenecks: tuple[EnterpriseWorkflowBottleneck, ...] = ()
    calculated_at: str = dataclass_field(default_factory=utc_timestamp)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "status_counts",
            dict(sorted(self.status_counts.items())),
        )
        object.__setattr__(
            self,
            "priority_counts",
            dict(sorted(self.priority_counts.items())),
        )
        object.__setattr__(
            self,
            "top_bottlenecks",
            tuple(self.top_bottlenecks),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "total_workflows": self.total_workflows,
            "status_counts": dict(self.status_counts),
            "priority_counts": dict(self.priority_counts),
            "average_health_score": self.average_health_score,
            "healthy": self.healthy,
            "watch": self.watch,
            "at_risk": self.at_risk,
            "critical": self.critical,
            "active_workflows": self.active_workflows,
            "completed_workflows": self.completed_workflows,
            "failed_workflows": self.failed_workflows,
            "blocked_stages": self.blocked_stages,
            "failed_tasks": self.failed_tasks,
            "pending_approvals": self.pending_approvals,
            "top_bottlenecks": [
                bottleneck.as_dict()
                for bottleneck in self.top_bottlenecks
            ],
            "calculated_at": self.calculated_at,
        }


class EnterpriseWorkflowAnalytics:
    """Deterministic analytics service for workflow intelligence."""

    def analyse(
        self,
        workflow: EnterpriseWorkflow,
        *,
        approvals: Iterable[
            EnterpriseWorkflowApprovalRequest
        ] = (),
        transitions: Iterable[
            EnterpriseWorkflowTransitionEvent
        ] = (),
        store_record: EnterpriseWorkflowStoreRecord | None = None,
        now: str | None = None,
        blocked_threshold_seconds: float = 3600.0,
        approval_threshold_seconds: float = 86400.0,
        running_threshold_seconds: float = 86400.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowHealthReport:
        """Calculate a complete health report for one workflow."""

        if not isinstance(workflow, EnterpriseWorkflow):
            raise TypeError(
                "Workflow analytics requires EnterpriseWorkflow."
            )

        current_time = (
            _parse_timestamp(now)
            if now
            else datetime.now(timezone.utc)
        )
        assert current_time is not None

        workflow_approvals = tuple(
            approval
            for approval in approvals
            if approval.workflow_id == workflow.workflow_id
        )
        workflow_transitions = tuple(
            transition
            for transition in transitions
            if transition.workflow_id == workflow.workflow_id
        )

        stage_metrics = self.stage_metrics(workflow.stages)
        tasks = tuple(
            task
            for stage in workflow.stages
            for task in stage.tasks
        )
        task_metrics = self.task_metrics(tasks)
        approval_metrics = self.approval_metrics(
            workflow_approvals,
            now=current_time,
        )
        transition_metrics = self.transition_metrics(
            workflow_transitions
        )
        bottlenecks = self.detect_bottlenecks(
            workflow,
            approvals=workflow_approvals,
            transitions=workflow_transitions,
            now=current_time,
            blocked_threshold_seconds=blocked_threshold_seconds,
            approval_threshold_seconds=approval_threshold_seconds,
            running_threshold_seconds=running_threshold_seconds,
        )

        score = self._health_score(
            workflow,
            stage_metrics=stage_metrics,
            task_metrics=task_metrics,
            approval_metrics=approval_metrics,
            transition_metrics=transition_metrics,
            bottlenecks=bottlenecks,
        )
        label = self._health_label(score)
        recommendations = self._recommendations(
            workflow,
            stage_metrics=stage_metrics,
            task_metrics=task_metrics,
            approval_metrics=approval_metrics,
            transition_metrics=transition_metrics,
            bottlenecks=bottlenecks,
        )

        report_metadata = {
            "revision": (
                store_record.revision
                if store_record is not None
                else None
            ),
            "archived": (
                store_record.archived
                if store_record is not None
                else workflow.status
                is EnterpriseWorkflowStatus.ARCHIVED
            ),
            **redact_mapping(dict(metadata or {})),
        }

        return EnterpriseWorkflowHealthReport(
            workflow_id=workflow.workflow_id,
            case_id=workflow.case_id,
            template_id=workflow.template_id,
            workflow_status=workflow.status,
            priority=workflow.priority,
            health_score=score,
            health_label=label,
            stage_metrics=stage_metrics,
            task_metrics=task_metrics,
            approval_metrics=approval_metrics,
            transition_metrics=transition_metrics,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
            metadata=report_metadata,
        )

    def analyse_portfolio(
        self,
        workflows: Iterable[EnterpriseWorkflow],
        *,
        approvals: Iterable[
            EnterpriseWorkflowApprovalRequest
        ] = (),
        transitions: Iterable[
            EnterpriseWorkflowTransitionEvent
        ] = (),
        store_records: Iterable[
            EnterpriseWorkflowStoreRecord
        ] = (),
        now: str | None = None,
        top_bottleneck_limit: int = 10,
    ) -> EnterpriseWorkflowPortfolioReport:
        """Calculate aggregated health metrics across workflows."""

        if top_bottleneck_limit < 1:
            raise ValueError(
                "Top bottleneck limit must be at least 1."
            )

        workflow_items = tuple(workflows)
        approval_items = tuple(approvals)
        transition_items = tuple(transitions)
        records_by_id = {
            record.workflow_id: record
            for record in store_records
        }

        reports = tuple(
            self.analyse(
                workflow,
                approvals=approval_items,
                transitions=transition_items,
                store_record=records_by_id.get(
                    workflow.workflow_id
                ),
                now=now,
            )
            for workflow in workflow_items
        )

        status_counts = {
            status.value: sum(
                1
                for workflow in workflow_items
                if workflow.status is status
            )
            for status in EnterpriseWorkflowStatus
        }
        priority_counts = {
            priority.value: sum(
                1
                for workflow in workflow_items
                if workflow.priority is priority
            )
            for priority in EnterpriseWorkflowPriority
        }

        bottlenecks = sorted(
            (
                bottleneck
                for report in reports
                for bottleneck in report.bottlenecks
            ),
            key=lambda item: (
                self._severity_rank(item.severity),
                item.age_seconds,
                item.workflow_id,
                item.subject_id,
            ),
            reverse=True,
        )

        return EnterpriseWorkflowPortfolioReport(
            total_workflows=len(workflow_items),
            status_counts=status_counts,
            priority_counts=priority_counts,
            average_health_score=round(
                mean(
                    report.health_score
                    for report in reports
                ),
                2,
            )
            if reports
            else 0.0,
            healthy=sum(
                1
                for report in reports
                if report.health_label == "healthy"
            ),
            watch=sum(
                1
                for report in reports
                if report.health_label == "watch"
            ),
            at_risk=sum(
                1
                for report in reports
                if report.health_label == "at_risk"
            ),
            critical=sum(
                1
                for report in reports
                if report.health_label == "critical"
            ),
            active_workflows=status_counts.get(
                EnterpriseWorkflowStatus.ACTIVE.value,
                0,
            ),
            completed_workflows=status_counts.get(
                EnterpriseWorkflowStatus.COMPLETED.value,
                0,
            ),
            failed_workflows=status_counts.get(
                EnterpriseWorkflowStatus.FAILED.value,
                0,
            ),
            blocked_stages=sum(
                report.stage_metrics.blocked
                for report in reports
            ),
            failed_tasks=sum(
                report.task_metrics.failed
                for report in reports
            ),
            pending_approvals=sum(
                report.approval_metrics.pending
                for report in reports
            ),
            top_bottlenecks=tuple(
                bottlenecks[:top_bottleneck_limit]
            ),
        )

    @staticmethod
    def stage_metrics(
        stages: Iterable[EnterpriseWorkflowStage],
    ) -> EnterpriseWorkflowStageMetrics:
        """Calculate stage distribution and completion metrics."""

        items = tuple(stages)
        counts = {
            status: sum(
                1
                for stage in items
                if stage.status is status
            )
            for status in EnterpriseWorkflowStageStatus
        }
        completed = (
            counts[EnterpriseWorkflowStageStatus.COMPLETED]
            + counts[EnterpriseWorkflowStageStatus.SKIPPED]
        )

        return EnterpriseWorkflowStageMetrics(
            total=len(items),
            pending=counts[
                EnterpriseWorkflowStageStatus.PENDING
            ],
            ready=counts[EnterpriseWorkflowStageStatus.READY],
            in_progress=counts[
                EnterpriseWorkflowStageStatus.IN_PROGRESS
            ],
            awaiting_approval=counts[
                EnterpriseWorkflowStageStatus.AWAITING_APPROVAL
            ],
            approved=counts[
                EnterpriseWorkflowStageStatus.APPROVED
            ],
            rejected=counts[
                EnterpriseWorkflowStageStatus.REJECTED
            ],
            completed=counts[
                EnterpriseWorkflowStageStatus.COMPLETED
            ],
            blocked=counts[
                EnterpriseWorkflowStageStatus.BLOCKED
            ],
            skipped=counts[
                EnterpriseWorkflowStageStatus.SKIPPED
            ],
            cancelled=counts[
                EnterpriseWorkflowStageStatus.CANCELLED
            ],
            completion_rate=_percentage(completed, len(items)),
            blocked_rate=_percentage(
                counts[EnterpriseWorkflowStageStatus.BLOCKED],
                len(items),
            ),
            approval_wait_rate=_percentage(
                counts[
                    EnterpriseWorkflowStageStatus.AWAITING_APPROVAL
                ],
                len(items),
            ),
        )

    @staticmethod
    def task_metrics(
        tasks: Iterable[EnterpriseWorkflowTask],
    ) -> EnterpriseWorkflowTaskMetrics:
        """Calculate task distribution and delivery metrics."""

        items = tuple(tasks)
        counts = {
            status: sum(
                1
                for task in items
                if task.status is status
            )
            for status in EnterpriseWorkflowTaskStatus
        }
        finished = (
            counts[EnterpriseWorkflowTaskStatus.SUCCEEDED]
            + counts[EnterpriseWorkflowTaskStatus.SKIPPED]
        )
        terminal_executions = (
            counts[EnterpriseWorkflowTaskStatus.SUCCEEDED]
            + counts[EnterpriseWorkflowTaskStatus.FAILED]
        )

        return EnterpriseWorkflowTaskMetrics(
            total=len(items),
            pending=counts[
                EnterpriseWorkflowTaskStatus.PENDING
            ],
            ready=counts[EnterpriseWorkflowTaskStatus.READY],
            running=counts[
                EnterpriseWorkflowTaskStatus.RUNNING
            ],
            succeeded=counts[
                EnterpriseWorkflowTaskStatus.SUCCEEDED
            ],
            failed=counts[
                EnterpriseWorkflowTaskStatus.FAILED
            ],
            blocked=counts[
                EnterpriseWorkflowTaskStatus.BLOCKED
            ],
            skipped=counts[
                EnterpriseWorkflowTaskStatus.SKIPPED
            ],
            cancelled=counts[
                EnterpriseWorkflowTaskStatus.CANCELLED
            ],
            requires_approval=sum(
                1
                for task in items
                if task.requires_approval
            ),
            success_rate=_percentage(
                counts[
                    EnterpriseWorkflowTaskStatus.SUCCEEDED
                ],
                terminal_executions,
            ),
            completion_rate=_percentage(finished, len(items)),
            failure_rate=_percentage(
                counts[EnterpriseWorkflowTaskStatus.FAILED],
                len(items),
            ),
            blocked_rate=_percentage(
                counts[EnterpriseWorkflowTaskStatus.BLOCKED],
                len(items),
            ),
        )

    @staticmethod
    def approval_metrics(
        approvals: Iterable[
            EnterpriseWorkflowApprovalRequest
        ],
        *,
        now: datetime | None = None,
    ) -> EnterpriseWorkflowApprovalMetrics:
        """Calculate approval distribution and decision latency."""

        items = tuple(approvals)
        counts = {
            status: sum(
                1
                for approval in items
                if approval.status is status
            )
            for status in EnterpriseWorkflowApprovalStatus
        }
        decided = (
            counts[EnterpriseWorkflowApprovalStatus.APPROVED]
            + counts[EnterpriseWorkflowApprovalStatus.REJECTED]
        )

        durations: list[float] = []

        for approval in items:
            if not approval.votes:
                continue

            last_vote = max(
                approval.votes,
                key=lambda vote: vote.decided_at,
            )
            duration = _duration_seconds(
                approval.requested_at,
                last_vote.decided_at,
                now=now,
            )

            if duration is not None:
                durations.append(duration)

        return EnterpriseWorkflowApprovalMetrics(
            total=len(items),
            pending=counts[
                EnterpriseWorkflowApprovalStatus.PENDING
            ],
            approved=counts[
                EnterpriseWorkflowApprovalStatus.APPROVED
            ],
            rejected=counts[
                EnterpriseWorkflowApprovalStatus.REJECTED
            ],
            expired=counts[
                EnterpriseWorkflowApprovalStatus.EXPIRED
            ],
            cancelled=counts[
                EnterpriseWorkflowApprovalStatus.CANCELLED
            ],
            not_required=counts[
                EnterpriseWorkflowApprovalStatus.NOT_REQUIRED
            ],
            approval_rate=_percentage(
                counts[EnterpriseWorkflowApprovalStatus.APPROVED],
                decided,
            ),
            rejection_rate=_percentage(
                counts[EnterpriseWorkflowApprovalStatus.REJECTED],
                decided,
            ),
            expiry_rate=_percentage(
                counts[EnterpriseWorkflowApprovalStatus.EXPIRED],
                len(items),
            ),
            average_decision_seconds=round(
                mean(durations),
                2,
            )
            if durations
            else 0.0,
            maximum_decision_seconds=round(
                max(durations),
                2,
            )
            if durations
            else 0.0,
        )

    @staticmethod
    def transition_metrics(
        transitions: Iterable[
            EnterpriseWorkflowTransitionEvent
        ],
    ) -> EnterpriseWorkflowTransitionMetrics:
        """Calculate transition outcomes and policy violations."""

        items = tuple(transitions)
        applied = sum(
            1
            for event in items
            if event.outcome
            is EnterpriseWorkflowTransitionOutcome.APPLIED
        )
        rejected = sum(
            1
            for event in items
            if event.outcome
            is EnterpriseWorkflowTransitionOutcome.REJECTED
        )
        no_change = sum(
            1
            for event in items
            if event.outcome
            is EnterpriseWorkflowTransitionOutcome.NO_CHANGE
        )
        violation_counts: dict[str, int] = {}

        for event in items:
            for violation in event.violations:
                violation_counts[violation] = (
                    violation_counts.get(violation, 0) + 1
                )

        return EnterpriseWorkflowTransitionMetrics(
            total=len(items),
            applied=applied,
            rejected=rejected,
            no_change=no_change,
            application_rate=_percentage(applied, len(items)),
            rejection_rate=_percentage(rejected, len(items)),
            violation_counts=violation_counts,
        )

    def detect_bottlenecks(
        self,
        workflow: EnterpriseWorkflow,
        *,
        approvals: Sequence[
            EnterpriseWorkflowApprovalRequest
        ] = (),
        transitions: Sequence[
            EnterpriseWorkflowTransitionEvent
        ] = (),
        now: datetime | None = None,
        blocked_threshold_seconds: float = 3600.0,
        approval_threshold_seconds: float = 86400.0,
        running_threshold_seconds: float = 86400.0,
    ) -> tuple[EnterpriseWorkflowBottleneck, ...]:
        """Detect blocked, delayed, failed, and approval bottlenecks."""

        current_time = now or datetime.now(timezone.utc)
        bottlenecks: list[EnterpriseWorkflowBottleneck] = []

        for stage in workflow.stages:
            if stage.status is EnterpriseWorkflowStageStatus.BLOCKED:
                age = self._subject_age_from_transitions(
                    transitions,
                    stage.stage_id,
                    current_time,
                )
                severity = (
                    "critical"
                    if age >= blocked_threshold_seconds * 4
                    else "high"
                    if age >= blocked_threshold_seconds
                    else "medium"
                )
                bottlenecks.append(
                    EnterpriseWorkflowBottleneck(
                        workflow_id=workflow.workflow_id,
                        subject_type="stage",
                        subject_id=stage.stage_id,
                        severity=severity,
                        reason="stage_blocked",
                        age_seconds=age,
                        metadata={"stage_name": stage.name},
                    )
                )

            if (
                stage.status
                is EnterpriseWorkflowStageStatus.AWAITING_APPROVAL
            ):
                age = self._subject_age_from_transitions(
                    transitions,
                    stage.stage_id,
                    current_time,
                )
                severity = (
                    "high"
                    if age >= approval_threshold_seconds
                    else "medium"
                )
                bottlenecks.append(
                    EnterpriseWorkflowBottleneck(
                        workflow_id=workflow.workflow_id,
                        subject_type="stage",
                        subject_id=stage.stage_id,
                        severity=severity,
                        reason="stage_awaiting_approval",
                        age_seconds=age,
                        metadata={"stage_name": stage.name},
                    )
                )

            for task in stage.tasks:
                bottleneck = self._task_bottleneck(
                    workflow,
                    stage,
                    task,
                    transitions=transitions,
                    now=current_time,
                    blocked_threshold_seconds=(
                        blocked_threshold_seconds
                    ),
                    running_threshold_seconds=(
                        running_threshold_seconds
                    ),
                )

                if bottleneck is not None:
                    bottlenecks.append(bottleneck)

        for approval in approvals:
            if (
                approval.status
                is EnterpriseWorkflowApprovalStatus.PENDING
            ):
                age = _duration_seconds(
                    approval.requested_at,
                    None,
                    now=current_time,
                ) or 0.0

                if age >= approval_threshold_seconds:
                    bottlenecks.append(
                        EnterpriseWorkflowBottleneck(
                            workflow_id=workflow.workflow_id,
                            subject_type="approval",
                            subject_id=approval.request_id,
                            severity=(
                                "critical"
                                if approval.is_expired
                                else "high"
                            ),
                            reason="approval_decision_delayed",
                            age_seconds=age,
                            metadata={
                                "approval_subject_id": (
                                    approval.subject_id
                                ),
                                "required_approvals": (
                                    approval.required_approvals
                                ),
                                "received_approvals": (
                                    approval.approval_count
                                ),
                            },
                        )
                    )

        bottlenecks.sort(
            key=lambda item: (
                self._severity_rank(item.severity),
                item.age_seconds,
                item.subject_id,
            ),
            reverse=True,
        )

        return tuple(bottlenecks)

    def _task_bottleneck(
        self,
        workflow: EnterpriseWorkflow,
        stage: EnterpriseWorkflowStage,
        task: EnterpriseWorkflowTask,
        *,
        transitions: Sequence[
            EnterpriseWorkflowTransitionEvent
        ],
        now: datetime,
        blocked_threshold_seconds: float,
        running_threshold_seconds: float,
    ) -> EnterpriseWorkflowBottleneck | None:
        age = self._subject_age_from_transitions(
            transitions,
            task.task_id,
            now,
        )

        if task.status is EnterpriseWorkflowTaskStatus.FAILED:
            return EnterpriseWorkflowBottleneck(
                workflow_id=workflow.workflow_id,
                subject_type="task",
                subject_id=task.task_id,
                severity="high",
                reason="task_failed",
                age_seconds=age,
                metadata={
                    "task_name": task.name,
                    "stage_id": stage.stage_id,
                },
            )

        if task.status is EnterpriseWorkflowTaskStatus.BLOCKED:
            return EnterpriseWorkflowBottleneck(
                workflow_id=workflow.workflow_id,
                subject_type="task",
                subject_id=task.task_id,
                severity=(
                    "critical"
                    if age >= blocked_threshold_seconds * 4
                    else "high"
                    if age >= blocked_threshold_seconds
                    else "medium"
                ),
                reason="task_blocked",
                age_seconds=age,
                metadata={
                    "task_name": task.name,
                    "stage_id": stage.stage_id,
                },
            )

        if (
            task.status is EnterpriseWorkflowTaskStatus.RUNNING
            and age >= running_threshold_seconds
        ):
            return EnterpriseWorkflowBottleneck(
                workflow_id=workflow.workflow_id,
                subject_type="task",
                subject_id=task.task_id,
                severity="high",
                reason="task_running_long",
                age_seconds=age,
                metadata={
                    "task_name": task.name,
                    "stage_id": stage.stage_id,
                },
            )

        return None

    @staticmethod
    def _subject_age_from_transitions(
        transitions: Sequence[
            EnterpriseWorkflowTransitionEvent
        ],
        subject_id: str,
        now: datetime,
    ) -> float:
        matching = [
            event
            for event in transitions
            if event.subject_id == subject_id
        ]

        if not matching:
            return 0.0

        latest = max(
            matching,
            key=lambda event: event.occurred_at,
        )
        return _duration_seconds(
            latest.occurred_at,
            None,
            now=now,
        ) or 0.0

    @staticmethod
    def _health_score(
        workflow: EnterpriseWorkflow,
        *,
        stage_metrics: EnterpriseWorkflowStageMetrics,
        task_metrics: EnterpriseWorkflowTaskMetrics,
        approval_metrics: EnterpriseWorkflowApprovalMetrics,
        transition_metrics: EnterpriseWorkflowTransitionMetrics,
        bottlenecks: Sequence[EnterpriseWorkflowBottleneck],
    ) -> float:
        score = 100.0

        score -= task_metrics.failure_rate * 0.45
        score -= task_metrics.blocked_rate * 0.35
        score -= stage_metrics.blocked_rate * 0.40
        score -= stage_metrics.approval_wait_rate * 0.15
        score -= approval_metrics.expiry_rate * 0.20
        score -= transition_metrics.rejection_rate * 0.10

        severity_penalties = {
            "low": 1.0,
            "medium": 4.0,
            "high": 9.0,
            "critical": 18.0,
        }
        score -= sum(
            severity_penalties[bottleneck.severity]
            for bottleneck in bottlenecks
        )

        if workflow.status is EnterpriseWorkflowStatus.COMPLETED:
            score = max(score, 95.0)
        elif workflow.status is EnterpriseWorkflowStatus.FAILED:
            score = min(score, 25.0)
        elif workflow.status is EnterpriseWorkflowStatus.CANCELLED:
            score = min(score, 40.0)
        elif workflow.status is EnterpriseWorkflowStatus.ARCHIVED:
            score = max(score, 80.0)

        return round(min(100.0, max(0.0, score)), 2)

    @staticmethod
    def _health_label(score: float) -> str:
        if score >= 85.0:
            return "healthy"
        if score >= 65.0:
            return "watch"
        if score >= 40.0:
            return "at_risk"
        return "critical"

    @staticmethod
    def _recommendations(
        workflow: EnterpriseWorkflow,
        *,
        stage_metrics: EnterpriseWorkflowStageMetrics,
        task_metrics: EnterpriseWorkflowTaskMetrics,
        approval_metrics: EnterpriseWorkflowApprovalMetrics,
        transition_metrics: EnterpriseWorkflowTransitionMetrics,
        bottlenecks: Sequence[EnterpriseWorkflowBottleneck],
    ) -> tuple[str, ...]:
        recommendations: list[str] = []

        if stage_metrics.blocked:
            recommendations.append(
                "Resolve blocked workflow stages and verify their "
                "dependency inputs."
            )
        if task_metrics.failed:
            recommendations.append(
                "Review failed tasks, root causes, retry eligibility, "
                "and compensating controls."
            )
        if approval_metrics.pending:
            recommendations.append(
                "Escalate pending approvals to authorised approvers "
                "before operational deadlines."
            )
        if approval_metrics.expired:
            recommendations.append(
                "Reissue expired approvals with validated approver roles "
                "and updated expiry windows."
            )
        if transition_metrics.rejected:
            recommendations.append(
                "Review rejected transition attempts for policy, "
                "dependency, or approval violations."
            )
        if any(
            bottleneck.severity == "critical"
            for bottleneck in bottlenecks
        ):
            recommendations.append(
                "Escalate critical workflow bottlenecks to the command "
                "center and accountable owner."
            )
        if (
            workflow.status is EnterpriseWorkflowStatus.ACTIVE
            and not bottlenecks
            and task_metrics.running == 0
            and task_metrics.ready == 0
            and stage_metrics.ready == 0
        ):
            recommendations.append(
                "Refresh workflow readiness and validate unresolved "
                "dependencies."
            )
        if not recommendations:
            recommendations.append(
                "Continue execution and monitor workflow health, "
                "approvals, and SLA exposure."
            )

        return tuple(recommendations)

    @staticmethod
    def _severity_rank(severity: str) -> int:
        return {
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4,
        }.get(severity, 0)


_enterprise_workflow_analytics: EnterpriseWorkflowAnalytics | None = None


def get_enterprise_workflow_analytics() -> EnterpriseWorkflowAnalytics:
    """Return the process-wide enterprise workflow analytics service."""

    global _enterprise_workflow_analytics

    if _enterprise_workflow_analytics is None:
        _enterprise_workflow_analytics = EnterpriseWorkflowAnalytics()

    return _enterprise_workflow_analytics


# Backward-compatible aliases retained for earlier Package V integrations.
WorkflowTaskMetrics = EnterpriseWorkflowTaskMetrics
WorkflowStageMetrics = EnterpriseWorkflowStageMetrics
WorkflowApprovalMetrics = EnterpriseWorkflowApprovalMetrics
WorkflowTransitionMetrics = EnterpriseWorkflowTransitionMetrics
WorkflowBottleneck = EnterpriseWorkflowBottleneck
WorkflowHealthReport = EnterpriseWorkflowHealthReport
WorkflowPortfolioReport = EnterpriseWorkflowPortfolioReport
WorkflowAnalytics = EnterpriseWorkflowAnalytics
get_workflow_analytics = get_enterprise_workflow_analytics