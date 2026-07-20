"""Enterprise workflow intelligence and explainable recommendations.

Package V - Enterprise Workflow Intelligence.

This module converts deterministic workflow analytics into explainable,
prioritised operational intelligence. It does not mutate workflows directly.
Instead, it produces immutable findings and recommended actions that can be
reviewed, approved, and executed through the enterprise workflow coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_workflow_analytics import (
    EnterpriseWorkflowBottleneck,
    EnterpriseWorkflowHealthReport,
    EnterpriseWorkflowPortfolioReport,
)
from app.orchestration.enterprise_workflow_approval import (
    EnterpriseWorkflowApprovalStatus,
)
from app.orchestration.enterprise_workflow_coordinator import (
    EnterpriseWorkflowCommandContext,
    EnterpriseWorkflowCoordinator,
    EnterpriseWorkflowCoordinatorResult,
    get_enterprise_workflow_coordinator,
)
from app.orchestration.enterprise_workflow_models import (
    EnterpriseWorkflow,
    EnterpriseWorkflowPriority,
    EnterpriseWorkflowStageStatus,
    EnterpriseWorkflowStatus,
    EnterpriseWorkflowTaskStatus,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class EnterpriseWorkflowIntelligenceSeverity(str, Enum):
    """Severity assigned to workflow intelligence findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EnterpriseWorkflowIntelligenceCategory(str, Enum):
    """Supported categories of workflow intelligence."""

    EXECUTION = "execution"
    DEPENDENCY = "dependency"
    APPROVAL = "approval"
    RISK = "risk"
    PERFORMANCE = "performance"
    GOVERNANCE = "governance"
    DATA_QUALITY = "data_quality"
    PORTFOLIO = "portfolio"


class EnterpriseWorkflowRecommendedActionType(str, Enum):
    """Types of actions recommended by the intelligence service."""

    REFRESH_READINESS = "refresh_readiness"
    RESOLVE_BLOCKER = "resolve_blocker"
    RETRY_TASK = "retry_task"
    ESCALATE_APPROVAL = "escalate_approval"
    REISSUE_APPROVAL = "reissue_approval"
    REVIEW_POLICY_VIOLATION = "review_policy_violation"
    PAUSE_WORKFLOW = "pause_workflow"
    RESUME_WORKFLOW = "resume_workflow"
    COMPLETE_WORKFLOW = "complete_workflow"
    ARCHIVE_WORKFLOW = "archive_workflow"
    INVESTIGATE_FAILURE = "investigate_failure"
    MONITOR = "monitor"


@dataclass(frozen=True)
class EnterpriseWorkflowIntelligenceFinding:
    """One explainable workflow intelligence finding."""

    workflow_id: str
    category: EnterpriseWorkflowIntelligenceCategory
    severity: EnterpriseWorkflowIntelligenceSeverity
    title: str
    rationale: str
    subject_id: str = ""
    finding_id: str = dataclass_field(
        default_factory=lambda: uuid4().hex
    )
    confidence: float = 1.0
    evidence: tuple[str, ...] = ()
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    detected_at: str = dataclass_field(default_factory=utc_timestamp)

    def __post_init__(self) -> None:
        if not str(self.finding_id or "").strip():
            raise ValueError("Workflow intelligence finding ID is required.")
        if not str(self.workflow_id or "").strip():
            raise ValueError(
                "Workflow intelligence workflow ID is required."
            )
        if not str(self.title or "").strip():
            raise ValueError("Workflow intelligence title is required.")
        if not str(self.rationale or "").strip():
            raise ValueError("Workflow intelligence rationale is required.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "Workflow intelligence confidence must be between 0 and 1."
            )

        object.__setattr__(
            self,
            "subject_id",
            str(self.subject_id or "").strip(),
        )
        object.__setattr__(
            self,
            "evidence",
            tuple(
                str(item).strip()
                for item in self.evidence
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
            "finding_id": self.finding_id,
            "workflow_id": self.workflow_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "rationale": self.rationale,
            "subject_id": self.subject_id,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "metadata": redact_mapping(self.metadata),
            "detected_at": self.detected_at,
        }


@dataclass(frozen=True)
class EnterpriseWorkflowRecommendedAction:
    """One explainable action recommended for human or automated review."""

    workflow_id: str
    action_type: EnterpriseWorkflowRecommendedActionType
    title: str
    rationale: str
    priority: int
    action_id: str = dataclass_field(
        default_factory=lambda: uuid4().hex
    )
    subject_id: str = ""
    requires_approval: bool = True
    confidence: float = 1.0
    finding_ids: tuple[str, ...] = ()
    parameters: dict[str, Any] = dataclass_field(default_factory=dict)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    recommended_at: str = dataclass_field(default_factory=utc_timestamp)

    def __post_init__(self) -> None:
        if not str(self.action_id or "").strip():
            raise ValueError(
                "Workflow intelligence action ID is required."
            )
        if not str(self.workflow_id or "").strip():
            raise ValueError(
                "Workflow intelligence action workflow ID is required."
            )
        if not str(self.title or "").strip():
            raise ValueError(
                "Workflow intelligence action title is required."
            )
        if not str(self.rationale or "").strip():
            raise ValueError(
                "Workflow intelligence action rationale is required."
            )
        if self.priority < 1 or self.priority > 100:
            raise ValueError(
                "Workflow intelligence action priority must be 1-100."
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "Workflow intelligence action confidence must be "
                "between 0 and 1."
            )

        object.__setattr__(
            self,
            "subject_id",
            str(self.subject_id or "").strip(),
        )
        object.__setattr__(
            self,
            "finding_ids",
            tuple(
                str(item).strip()
                for item in self.finding_ids
                if str(item).strip()
            ),
        )
        object.__setattr__(
            self,
            "parameters",
            redact_mapping(self.parameters),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "action_id": self.action_id,
            "workflow_id": self.workflow_id,
            "action_type": self.action_type.value,
            "title": self.title,
            "rationale": self.rationale,
            "priority": self.priority,
            "subject_id": self.subject_id,
            "requires_approval": self.requires_approval,
            "confidence": self.confidence,
            "finding_ids": list(self.finding_ids),
            "parameters": redact_mapping(self.parameters),
            "metadata": redact_mapping(self.metadata),
            "recommended_at": self.recommended_at,
        }


@dataclass(frozen=True)
class EnterpriseWorkflowIntelligenceReport:
    """Complete intelligence report for one workflow."""

    workflow_id: str
    health_report: EnterpriseWorkflowHealthReport
    overall_severity: EnterpriseWorkflowIntelligenceSeverity
    confidence: float
    findings: tuple[EnterpriseWorkflowIntelligenceFinding, ...] = ()
    recommended_actions: tuple[
        EnterpriseWorkflowRecommendedAction,
        ...
    ] = ()
    summary: str = ""
    report_id: str = dataclass_field(
        default_factory=lambda: uuid4().hex
    )
    generated_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.report_id or "").strip():
            raise ValueError(
                "Workflow intelligence report ID is required."
            )
        if not str(self.workflow_id or "").strip():
            raise ValueError(
                "Workflow intelligence report workflow ID is required."
            )
        if self.health_report.workflow_id != self.workflow_id:
            raise ValueError(
                "Workflow intelligence health report ID mismatch."
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "Workflow intelligence report confidence must be "
                "between 0 and 1."
            )

        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(
            self,
            "recommended_actions",
            tuple(self.recommended_actions),
        )
        object.__setattr__(
            self,
            "summary",
            str(self.summary or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "report_id": self.report_id,
            "workflow_id": self.workflow_id,
            "overall_severity": self.overall_severity.value,
            "confidence": self.confidence,
            "summary": self.summary,
            "health_report": self.health_report.as_dict(),
            "findings": [
                finding.as_dict() for finding in self.findings
            ],
            "recommended_actions": [
                action.as_dict()
                for action in self.recommended_actions
            ],
            "generated_at": self.generated_at,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseWorkflowPortfolioIntelligenceReport:
    """Portfolio-wide workflow intelligence report."""

    portfolio_report: EnterpriseWorkflowPortfolioReport
    overall_severity: EnterpriseWorkflowIntelligenceSeverity
    findings: tuple[EnterpriseWorkflowIntelligenceFinding, ...] = ()
    recommended_actions: tuple[
        EnterpriseWorkflowRecommendedAction,
        ...
    ] = ()
    summary: str = ""
    report_id: str = dataclass_field(
        default_factory=lambda: uuid4().hex
    )
    generated_at: str = dataclass_field(default_factory=utc_timestamp)

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "report_id": self.report_id,
            "overall_severity": self.overall_severity.value,
            "summary": self.summary,
            "portfolio_report": self.portfolio_report.as_dict(),
            "findings": [
                finding.as_dict() for finding in self.findings
            ],
            "recommended_actions": [
                action.as_dict()
                for action in self.recommended_actions
            ],
            "generated_at": self.generated_at,
        }


class EnterpriseWorkflowIntelligence:
    """Explainable workflow intelligence and recommendation service."""

    def __init__(
        self,
        *,
        coordinator: EnterpriseWorkflowCoordinator | None = None,
    ) -> None:
        self._coordinator = (
            coordinator or get_enterprise_workflow_coordinator()
        )
        self._reports: list[EnterpriseWorkflowIntelligenceReport] = []
        self._lock = RLock()

    def analyse(
        self,
        workflow: EnterpriseWorkflow,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> EnterpriseWorkflowIntelligenceReport:
        """Generate explainable intelligence for one workflow."""

        coordinator_result = self._coordinator.analyse(
            workflow,
            context=context,
        )

        if coordinator_result.health_report is None:
            raise RuntimeError(
                "Workflow coordinator did not return a health report."
            )

        health = coordinator_result.health_report
        findings = self._findings(workflow, health)
        actions = self._actions(workflow, health, findings)
        severity = self._overall_severity(findings, health)
        confidence = self._confidence(workflow, health, findings)
        summary = self._summary(
            workflow,
            health,
            severity,
            findings,
            actions,
        )

        report = EnterpriseWorkflowIntelligenceReport(
            workflow_id=workflow.workflow_id,
            health_report=health,
            overall_severity=severity,
            confidence=confidence,
            findings=findings,
            recommended_actions=actions,
            summary=summary,
            metadata={
                "coordinator_event_id": (
                    coordinator_result.event.event_id
                ),
                **redact_mapping(dict(metadata or {})),
            },
        )

        with self._lock:
            self._reports.append(report)

        return report

    def analyse_portfolio(
        self,
        *,
        include_archived: bool = False,
        top_bottleneck_limit: int = 10,
    ) -> EnterpriseWorkflowPortfolioIntelligenceReport:
        """Generate portfolio-wide workflow intelligence."""

        portfolio = self._coordinator.analyse_portfolio(
            include_archived=include_archived,
            top_bottleneck_limit=top_bottleneck_limit,
        )
        findings: list[EnterpriseWorkflowIntelligenceFinding] = []
        actions: list[EnterpriseWorkflowRecommendedAction] = []

        if portfolio.critical:
            findings.append(
                EnterpriseWorkflowIntelligenceFinding(
                    workflow_id="portfolio",
                    category=(
                        EnterpriseWorkflowIntelligenceCategory.PORTFOLIO
                    ),
                    severity=(
                        EnterpriseWorkflowIntelligenceSeverity.CRITICAL
                    ),
                    title="Critical workflows require intervention",
                    rationale=(
                        f"{portfolio.critical} workflow(s) are in a "
                        "critical health state."
                    ),
                    confidence=1.0,
                    evidence=(
                        f"critical_workflows={portfolio.critical}",
                    ),
                )
            )
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id="portfolio",
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .INVESTIGATE_FAILURE
                    ),
                    title="Open command-center intervention",
                    rationale=(
                        "Critical workflow health requires accountable "
                        "owners, recovery plans, and escalation."
                    ),
                    priority=100,
                    requires_approval=False,
                    confidence=1.0,
                    finding_ids=(findings[-1].finding_id,),
                )
            )

        if portfolio.pending_approvals:
            findings.append(
                EnterpriseWorkflowIntelligenceFinding(
                    workflow_id="portfolio",
                    category=(
                        EnterpriseWorkflowIntelligenceCategory.APPROVAL
                    ),
                    severity=(
                        EnterpriseWorkflowIntelligenceSeverity.HIGH
                        if portfolio.pending_approvals >= 5
                        else EnterpriseWorkflowIntelligenceSeverity.MEDIUM
                    ),
                    title="Portfolio approvals are accumulating",
                    rationale=(
                        f"{portfolio.pending_approvals} approval(s) are "
                        "currently pending."
                    ),
                    confidence=0.98,
                    evidence=(
                        f"pending_approvals={portfolio.pending_approvals}",
                    ),
                )
            )
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id="portfolio",
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .ESCALATE_APPROVAL
                    ),
                    title="Escalate overdue portfolio approvals",
                    rationale=(
                        "Pending approvals can delay procurement, "
                        "shipment, payment, and compliance milestones."
                    ),
                    priority=min(
                        95,
                        60 + portfolio.pending_approvals * 3,
                    ),
                    requires_approval=False,
                    confidence=0.98,
                    finding_ids=(findings[-1].finding_id,),
                )
            )

        if portfolio.failed_tasks:
            findings.append(
                EnterpriseWorkflowIntelligenceFinding(
                    workflow_id="portfolio",
                    category=(
                        EnterpriseWorkflowIntelligenceCategory.EXECUTION
                    ),
                    severity=(
                        EnterpriseWorkflowIntelligenceSeverity.HIGH
                    ),
                    title="Failed tasks detected across portfolio",
                    rationale=(
                        f"{portfolio.failed_tasks} task failure(s) need "
                        "root-cause review."
                    ),
                    confidence=1.0,
                    evidence=(
                        f"failed_tasks={portfolio.failed_tasks}",
                    ),
                )
            )

        severity = self._severity_from_values(
            finding.severity for finding in findings
        )
        summary = (
            f"Portfolio health score averages "
            f"{portfolio.average_health_score:.2f}/100 across "
            f"{portfolio.total_workflows} workflow(s). "
            f"{portfolio.critical} critical and "
            f"{portfolio.at_risk} at-risk workflow(s) require review."
        )

        return EnterpriseWorkflowPortfolioIntelligenceReport(
            portfolio_report=portfolio,
            overall_severity=severity,
            findings=tuple(findings),
            recommended_actions=tuple(
                sorted(
                    actions,
                    key=lambda item: (
                        item.priority,
                        item.action_id,
                    ),
                    reverse=True,
                )
            ),
            summary=summary,
        )

    def execute_recommended_action(
        self,
        workflow: EnterpriseWorkflow,
        action: EnterpriseWorkflowRecommendedAction,
        *,
        context: EnterpriseWorkflowCommandContext | None = None,
    ) -> EnterpriseWorkflowCoordinatorResult:
        """Execute safe coordinator-supported actions.

        Actions that require operational investigation, external escalation,
        task retries, or policy review remain advisory and are intentionally
        not executed automatically.
        """

        if action.workflow_id != workflow.workflow_id:
            raise ValueError(
                "Recommended action does not belong to the workflow."
            )
        if action.requires_approval:
            raise PermissionError(
                "Recommended action requires approval before execution."
            )

        if (
            action.action_type
            is EnterpriseWorkflowRecommendedActionType.REFRESH_READINESS
        ):
            return self._coordinator.refresh(
                workflow,
                context=context,
            )

        if (
            action.action_type
            is EnterpriseWorkflowRecommendedActionType.PAUSE_WORKFLOW
        ):
            return self._coordinator.transition_workflow(
                workflow,
                EnterpriseWorkflowStatus.PAUSED,
                reason=action.rationale,
                context=context,
            )

        if (
            action.action_type
            is EnterpriseWorkflowRecommendedActionType.RESUME_WORKFLOW
        ):
            return self._coordinator.transition_workflow(
                workflow,
                EnterpriseWorkflowStatus.ACTIVE,
                reason=action.rationale,
                context=context,
            )

        if (
            action.action_type
            is EnterpriseWorkflowRecommendedActionType.COMPLETE_WORKFLOW
        ):
            return self._coordinator.transition_workflow(
                workflow,
                EnterpriseWorkflowStatus.COMPLETED,
                reason=action.rationale,
                context=context,
            )

        if (
            action.action_type
            is EnterpriseWorkflowRecommendedActionType.ARCHIVE_WORKFLOW
        ):
            return self._coordinator.archive(
                workflow.workflow_id,
                context=context,
            )

        raise NotImplementedError(
            "Recommended action is advisory and must be handled by an "
            "authorised operational workflow."
        )

    def history(
        self,
        *,
        workflow_id: str | None = None,
    ) -> tuple[EnterpriseWorkflowIntelligenceReport, ...]:
        """Return generated intelligence reports."""

        with self._lock:
            reports = tuple(self._reports)

        if workflow_id is None:
            return reports

        cleaned_id = str(workflow_id).strip()
        return tuple(
            report
            for report in reports
            if report.workflow_id == cleaned_id
        )

    def clear_history(self) -> None:
        """Clear in-memory intelligence report history."""

        with self._lock:
            self._reports.clear()

    def _findings(
        self,
        workflow: EnterpriseWorkflow,
        health: EnterpriseWorkflowHealthReport,
    ) -> tuple[EnterpriseWorkflowIntelligenceFinding, ...]:
        findings: list[EnterpriseWorkflowIntelligenceFinding] = []

        for bottleneck in health.bottlenecks:
            findings.append(
                self._finding_from_bottleneck(
                    workflow,
                    bottleneck,
                )
            )

        if health.task_metrics.failed:
            findings.append(
                EnterpriseWorkflowIntelligenceFinding(
                    workflow_id=workflow.workflow_id,
                    category=(
                        EnterpriseWorkflowIntelligenceCategory.EXECUTION
                    ),
                    severity=(
                        EnterpriseWorkflowIntelligenceSeverity.HIGH
                    ),
                    title="Workflow task failures require review",
                    rationale=(
                        f"{health.task_metrics.failed} workflow task(s) "
                        "are in failed state."
                    ),
                    confidence=1.0,
                    evidence=(
                        f"failed_tasks={health.task_metrics.failed}",
                        f"failure_rate={health.task_metrics.failure_rate}",
                    ),
                )
            )

        if health.approval_metrics.expired:
            findings.append(
                EnterpriseWorkflowIntelligenceFinding(
                    workflow_id=workflow.workflow_id,
                    category=(
                        EnterpriseWorkflowIntelligenceCategory.APPROVAL
                    ),
                    severity=(
                        EnterpriseWorkflowIntelligenceSeverity.HIGH
                    ),
                    title="Expired workflow approvals detected",
                    rationale=(
                        f"{health.approval_metrics.expired} approval "
                        "request(s) expired before completion."
                    ),
                    confidence=1.0,
                    evidence=(
                        f"expired_approvals="
                        f"{health.approval_metrics.expired}",
                    ),
                )
            )

        if health.transition_metrics.rejected:
            findings.append(
                EnterpriseWorkflowIntelligenceFinding(
                    workflow_id=workflow.workflow_id,
                    category=(
                        EnterpriseWorkflowIntelligenceCategory.GOVERNANCE
                    ),
                    severity=(
                        EnterpriseWorkflowIntelligenceSeverity.MEDIUM
                    ),
                    title="Governed workflow transitions were rejected",
                    rationale=(
                        f"{health.transition_metrics.rejected} "
                        "transition attempt(s) violated workflow rules."
                    ),
                    confidence=1.0,
                    evidence=tuple(
                        f"{name}={count}"
                        for name, count in (
                            health.transition_metrics
                            .violation_counts.items()
                        )
                    ),
                )
            )

        if (
            workflow.status is EnterpriseWorkflowStatus.ACTIVE
            and health.task_metrics.running == 0
            and health.task_metrics.ready == 0
            and health.stage_metrics.ready == 0
            and not health.bottlenecks
        ):
            findings.append(
                EnterpriseWorkflowIntelligenceFinding(
                    workflow_id=workflow.workflow_id,
                    category=(
                        EnterpriseWorkflowIntelligenceCategory.DEPENDENCY
                    ),
                    severity=(
                        EnterpriseWorkflowIntelligenceSeverity.MEDIUM
                    ),
                    title="Active workflow has no executable work",
                    rationale=(
                        "The workflow is active, but no stage or task is "
                        "currently ready or running."
                    ),
                    confidence=0.95,
                    evidence=(
                        "running_tasks=0",
                        "ready_tasks=0",
                        "ready_stages=0",
                    ),
                )
            )

        if (
            workflow.priority
            is EnterpriseWorkflowPriority.CRITICAL
            and health.health_score < 85.0
        ):
            findings.append(
                EnterpriseWorkflowIntelligenceFinding(
                    workflow_id=workflow.workflow_id,
                    category=(
                        EnterpriseWorkflowIntelligenceCategory.RISK
                    ),
                    severity=(
                        EnterpriseWorkflowIntelligenceSeverity.CRITICAL
                        if health.health_score < 40.0
                        else EnterpriseWorkflowIntelligenceSeverity.HIGH
                    ),
                    title="Critical-priority workflow health degraded",
                    rationale=(
                        "A critical-priority workflow is below the "
                        "healthy threshold and needs senior oversight."
                    ),
                    confidence=1.0,
                    evidence=(
                        f"health_score={health.health_score}",
                        "priority=critical",
                    ),
                )
            )

        if not findings:
            findings.append(
                EnterpriseWorkflowIntelligenceFinding(
                    workflow_id=workflow.workflow_id,
                    category=(
                        EnterpriseWorkflowIntelligenceCategory.PERFORMANCE
                    ),
                    severity=(
                        EnterpriseWorkflowIntelligenceSeverity.INFO
                    ),
                    title="Workflow is operating within expected controls",
                    rationale=(
                        "No material bottlenecks, failures, expired "
                        "approvals, or policy violations were detected."
                    ),
                    confidence=0.99,
                    evidence=(
                        f"health_score={health.health_score}",
                        f"health_label={health.health_label}",
                    ),
                )
            )

        findings.sort(
            key=lambda item: (
                self._severity_rank(item.severity),
                item.confidence,
                item.finding_id,
            ),
            reverse=True,
        )
        return tuple(findings)

    def _actions(
        self,
        workflow: EnterpriseWorkflow,
        health: EnterpriseWorkflowHealthReport,
        findings: Sequence[
            EnterpriseWorkflowIntelligenceFinding
        ],
    ) -> tuple[EnterpriseWorkflowRecommendedAction, ...]:
        actions: list[EnterpriseWorkflowRecommendedAction] = []

        findings_by_title = {
            finding.title: finding
            for finding in findings
        }

        if any(
            finding.title == "Active workflow has no executable work"
            for finding in findings
        ):
            finding = findings_by_title[
                "Active workflow has no executable work"
            ]
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .REFRESH_READINESS
                    ),
                    title="Refresh workflow readiness",
                    rationale=(
                        "Re-evaluate stage and task dependencies and "
                        "promote eligible work to ready state."
                    ),
                    priority=70,
                    requires_approval=False,
                    confidence=0.95,
                    finding_ids=(finding.finding_id,),
                )
            )

        if health.task_metrics.failed:
            matching = tuple(
                finding.finding_id
                for finding in findings
                if finding.category
                is EnterpriseWorkflowIntelligenceCategory.EXECUTION
            )
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .INVESTIGATE_FAILURE
                    ),
                    title="Investigate failed workflow tasks",
                    rationale=(
                        "Failed tasks require root-cause analysis, "
                        "controlled retry decisions, and compensating "
                        "actions where necessary."
                    ),
                    priority=90,
                    requires_approval=True,
                    confidence=1.0,
                    finding_ids=matching,
                    parameters={
                        "failed_task_count": (
                            health.task_metrics.failed
                        ),
                    },
                )
            )

        if health.approval_metrics.pending:
            matching = tuple(
                finding.finding_id
                for finding in findings
                if finding.category
                is EnterpriseWorkflowIntelligenceCategory.APPROVAL
            )
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .ESCALATE_APPROVAL
                    ),
                    title="Escalate pending workflow approvals",
                    rationale=(
                        "Pending approvals can delay dependent execution "
                        "and increase SLA exposure."
                    ),
                    priority=min(
                        95,
                        65 + health.approval_metrics.pending * 5,
                    ),
                    requires_approval=False,
                    confidence=0.98,
                    finding_ids=matching,
                    parameters={
                        "pending_approval_count": (
                            health.approval_metrics.pending
                        ),
                    },
                )
            )

        if health.approval_metrics.expired:
            matching = tuple(
                finding.finding_id
                for finding in findings
                if "Expired workflow approvals" in finding.title
            )
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .REISSUE_APPROVAL
                    ),
                    title="Reissue expired approvals",
                    rationale=(
                        "Expired approvals must be recreated with valid "
                        "roles, current evidence, and controlled expiry."
                    ),
                    priority=92,
                    requires_approval=True,
                    confidence=1.0,
                    finding_ids=matching,
                )
            )

        if health.transition_metrics.rejected:
            matching = tuple(
                finding.finding_id
                for finding in findings
                if finding.category
                is EnterpriseWorkflowIntelligenceCategory.GOVERNANCE
            )
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .REVIEW_POLICY_VIOLATION
                    ),
                    title="Review rejected workflow transitions",
                    rationale=(
                        "Repeated rejected transitions may indicate "
                        "invalid operator actions, stale state, or policy "
                        "misalignment."
                    ),
                    priority=75,
                    requires_approval=True,
                    confidence=1.0,
                    finding_ids=matching,
                    parameters={
                        "violation_counts": (
                            health.transition_metrics.violation_counts
                        ),
                    },
                )
            )

        if any(
            bottleneck.severity in {"high", "critical"}
            for bottleneck in health.bottlenecks
        ):
            matching = tuple(
                finding.finding_id
                for finding in findings
                if finding.subject_id
            )
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .RESOLVE_BLOCKER
                    ),
                    title="Resolve high-severity workflow blockers",
                    rationale=(
                        "High-severity blockers threaten operational "
                        "deadlines and downstream commercial commitments."
                    ),
                    priority=98,
                    requires_approval=True,
                    confidence=0.99,
                    finding_ids=matching,
                )
            )

        if (
            workflow.status is EnterpriseWorkflowStatus.ACTIVE
            and health.health_label == "critical"
        ):
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .PAUSE_WORKFLOW
                    ),
                    title="Consider pausing critical workflow",
                    rationale=(
                        "Pausing may prevent uncontrolled downstream "
                        "actions while critical failures are investigated."
                    ),
                    priority=96,
                    requires_approval=True,
                    confidence=0.9,
                )
            )

        if (
            workflow.status is EnterpriseWorkflowStatus.PAUSED
            and health.health_label in {"healthy", "watch"}
            and not health.bottlenecks
        ):
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .RESUME_WORKFLOW
                    ),
                    title="Consider resuming workflow",
                    rationale=(
                        "No material bottlenecks remain and workflow "
                        "health is within an acceptable range."
                    ),
                    priority=55,
                    requires_approval=True,
                    confidence=0.85,
                )
            )

        if (
            workflow.status is EnterpriseWorkflowStatus.ACTIVE
            and health.stage_metrics.total > 0
            and health.stage_metrics.completion_rate == 100.0
        ):
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .COMPLETE_WORKFLOW
                    ),
                    title="Complete finished workflow",
                    rationale=(
                        "All workflow stages are completed or skipped."
                    ),
                    priority=80,
                    requires_approval=False,
                    confidence=1.0,
                )
            )

        if (
            workflow.status is EnterpriseWorkflowStatus.COMPLETED
            and health.health_label == "healthy"
        ):
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType
                        .ARCHIVE_WORKFLOW
                    ),
                    title="Archive completed workflow",
                    rationale=(
                        "The workflow is completed and healthy, making "
                        "it eligible for controlled archival."
                    ),
                    priority=40,
                    requires_approval=True,
                    confidence=0.95,
                )
            )

        if not actions:
            actions.append(
                EnterpriseWorkflowRecommendedAction(
                    workflow_id=workflow.workflow_id,
                    action_type=(
                        EnterpriseWorkflowRecommendedActionType.MONITOR
                    ),
                    title="Continue workflow monitoring",
                    rationale=(
                        "No immediate intervention is required. Continue "
                        "tracking health, approvals, and execution."
                    ),
                    priority=20,
                    requires_approval=False,
                    confidence=0.99,
                    finding_ids=tuple(
                        finding.finding_id
                        for finding in findings
                    ),
                )
            )

        actions.sort(
            key=lambda item: (
                item.priority,
                item.confidence,
                item.action_id,
            ),
            reverse=True,
        )
        return tuple(actions)

    @staticmethod
    def _finding_from_bottleneck(
        workflow: EnterpriseWorkflow,
        bottleneck: EnterpriseWorkflowBottleneck,
    ) -> EnterpriseWorkflowIntelligenceFinding:
        severity = {
            "low": EnterpriseWorkflowIntelligenceSeverity.LOW,
            "medium": EnterpriseWorkflowIntelligenceSeverity.MEDIUM,
            "high": EnterpriseWorkflowIntelligenceSeverity.HIGH,
            "critical": (
                EnterpriseWorkflowIntelligenceSeverity.CRITICAL
            ),
        }[bottleneck.severity]

        category = (
            EnterpriseWorkflowIntelligenceCategory.APPROVAL
            if "approval" in bottleneck.reason
            else EnterpriseWorkflowIntelligenceCategory.EXECUTION
        )

        title = bottleneck.reason.replace("_", " ").title()
        rationale = (
            f"{bottleneck.subject_type.title()} "
            f"{bottleneck.subject_id} is affected by "
            f"{bottleneck.reason.replace('_', ' ')}."
        )

        return EnterpriseWorkflowIntelligenceFinding(
            workflow_id=workflow.workflow_id,
            category=category,
            severity=severity,
            title=title,
            rationale=rationale,
            subject_id=bottleneck.subject_id,
            confidence=0.99,
            evidence=(
                f"age_seconds={round(bottleneck.age_seconds, 2)}",
                f"severity={bottleneck.severity}",
                f"reason={bottleneck.reason}",
            ),
            metadata=bottleneck.metadata,
        )

    @staticmethod
    def _overall_severity(
        findings: Sequence[
            EnterpriseWorkflowIntelligenceFinding
        ],
        health: EnterpriseWorkflowHealthReport,
    ) -> EnterpriseWorkflowIntelligenceSeverity:
        severity = EnterpriseWorkflowIntelligence._severity_from_values(
            finding.severity for finding in findings
        )

        if health.health_label == "critical":
            return max(
                severity,
                EnterpriseWorkflowIntelligenceSeverity.CRITICAL,
                key=EnterpriseWorkflowIntelligence._severity_rank,
            )
        if health.health_label == "at_risk":
            return max(
                severity,
                EnterpriseWorkflowIntelligenceSeverity.HIGH,
                key=EnterpriseWorkflowIntelligence._severity_rank,
            )
        if health.health_label == "watch":
            return max(
                severity,
                EnterpriseWorkflowIntelligenceSeverity.MEDIUM,
                key=EnterpriseWorkflowIntelligence._severity_rank,
            )

        return severity

    @staticmethod
    def _confidence(
        workflow: EnterpriseWorkflow,
        health: EnterpriseWorkflowHealthReport,
        findings: Sequence[
            EnterpriseWorkflowIntelligenceFinding
        ],
    ) -> float:
        confidence = 0.98

        if not workflow.stages:
            confidence -= 0.15
        if health.transition_metrics.total == 0:
            confidence -= 0.05
        if (
            health.approval_metrics.total == 0
            and any(
                stage.approval_mode.value != "none"
                for stage in workflow.stages
            )
        ):
            confidence -= 0.08
        if not findings:
            confidence -= 0.05

        return round(max(0.5, min(1.0, confidence)), 2)

    @staticmethod
    def _summary(
        workflow: EnterpriseWorkflow,
        health: EnterpriseWorkflowHealthReport,
        severity: EnterpriseWorkflowIntelligenceSeverity,
        findings: Sequence[
            EnterpriseWorkflowIntelligenceFinding
        ],
        actions: Sequence[
            EnterpriseWorkflowRecommendedAction
        ],
    ) -> str:
        return (
            f"Workflow {workflow.workflow_id} is {workflow.status.value} "
            f"with health score {health.health_score:.2f}/100 "
            f"({health.health_label}). Intelligence severity is "
            f"{severity.value}; {len(findings)} finding(s) and "
            f"{len(actions)} recommended action(s) were generated."
        )

    @staticmethod
    def _severity_from_values(
        severities: Iterable[
            EnterpriseWorkflowIntelligenceSeverity
        ],
    ) -> EnterpriseWorkflowIntelligenceSeverity:
        items = tuple(severities)

        if not items:
            return EnterpriseWorkflowIntelligenceSeverity.INFO

        return max(
            items,
            key=EnterpriseWorkflowIntelligence._severity_rank,
        )

    @staticmethod
    def _severity_rank(
        severity: EnterpriseWorkflowIntelligenceSeverity,
    ) -> int:
        return {
            EnterpriseWorkflowIntelligenceSeverity.INFO: 0,
            EnterpriseWorkflowIntelligenceSeverity.LOW: 1,
            EnterpriseWorkflowIntelligenceSeverity.MEDIUM: 2,
            EnterpriseWorkflowIntelligenceSeverity.HIGH: 3,
            EnterpriseWorkflowIntelligenceSeverity.CRITICAL: 4,
        }[severity]


_enterprise_workflow_intelligence: (
    EnterpriseWorkflowIntelligence | None
) = None
_enterprise_workflow_intelligence_lock = RLock()


def get_enterprise_workflow_intelligence(
    *,
    coordinator: EnterpriseWorkflowCoordinator | None = None,
) -> EnterpriseWorkflowIntelligence:
    """Return the process-wide workflow intelligence service."""

    global _enterprise_workflow_intelligence

    with _enterprise_workflow_intelligence_lock:
        if _enterprise_workflow_intelligence is None:
            _enterprise_workflow_intelligence = (
                EnterpriseWorkflowIntelligence(
                    coordinator=coordinator
                )
            )

        return _enterprise_workflow_intelligence


# Backward-compatible aliases for earlier Package V integrations.
WorkflowIntelligenceSeverity = EnterpriseWorkflowIntelligenceSeverity
WorkflowIntelligenceCategory = EnterpriseWorkflowIntelligenceCategory
WorkflowRecommendedActionType = EnterpriseWorkflowRecommendedActionType
WorkflowIntelligenceFinding = EnterpriseWorkflowIntelligenceFinding
WorkflowRecommendedAction = EnterpriseWorkflowRecommendedAction
WorkflowIntelligenceReport = EnterpriseWorkflowIntelligenceReport
WorkflowPortfolioIntelligenceReport = (
    EnterpriseWorkflowPortfolioIntelligenceReport
)
WorkflowIntelligence = EnterpriseWorkflowIntelligence
get_workflow_intelligence = get_enterprise_workflow_intelligence