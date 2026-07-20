"""Integration tests for Package V - Enterprise Workflow Intelligence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestration.enterprise_workflow_analytics import (
    EnterpriseWorkflowAnalytics,
)
from app.orchestration.enterprise_workflow_approval import (
    EnterpriseWorkflowApprovalDecision,
    EnterpriseWorkflowApprovalManager,
    EnterpriseWorkflowApprovalStatus,
)
from app.orchestration.enterprise_workflow_coordinator import (
    EnterpriseWorkflowCommandContext,
    EnterpriseWorkflowCoordinator,
    EnterpriseWorkflowCoordinatorOutcome,
)
from app.orchestration.enterprise_workflow_intelligence import (
    EnterpriseWorkflowIntelligence,
    EnterpriseWorkflowIntelligenceSeverity,
    EnterpriseWorkflowRecommendedActionType,
)
from app.orchestration.enterprise_workflow_models import (
    EnterpriseWorkflow,
    EnterpriseWorkflowApprovalMode,
    EnterpriseWorkflowPriority,
    EnterpriseWorkflowStage,
    EnterpriseWorkflowStageStatus,
    EnterpriseWorkflowStatus,
    EnterpriseWorkflowTask,
    EnterpriseWorkflowTaskStatus,
)
from app.orchestration.enterprise_workflow_store import (
    EnterpriseWorkflowStore,
)
from app.orchestration.enterprise_workflow_transition import (
    EnterpriseWorkflowTransitionEngine,
    EnterpriseWorkflowTransitionOutcome,
)


def build_workflow(
    *,
    workflow_id: str = "workflow-001",
    priority: EnterpriseWorkflowPriority = (
        EnterpriseWorkflowPriority.HIGH
    ),
) -> EnterpriseWorkflow:
    """Build a deterministic workflow fixture."""

    validate_demand = EnterpriseWorkflowTask(
        task_id="task-validate-demand",
        name="Validate buyer demand",
        handler_id="validate_buyer_demand",
        status=EnterpriseWorkflowTaskStatus.READY,
        requires_approval=False,
    )
    approve_demand = EnterpriseWorkflowTask(
        task_id="task-approve-demand",
        name="Approve buyer commitment",
        handler_id="approve_buyer_commitment",
        status=EnterpriseWorkflowTaskStatus.PENDING,
        requires_approval=True,
        depends_on=("task-validate-demand",),
    )
    sourcing = EnterpriseWorkflowTask(
        task_id="task-source-suppliers",
        name="Source compliant suppliers",
        handler_id="source_compliant_suppliers",
        status=EnterpriseWorkflowTaskStatus.PENDING,
        requires_approval=False,
    )

    demand_stage = EnterpriseWorkflowStage(
        stage_id="stage-demand",
        name="Buyer Demand Validation",
        status=EnterpriseWorkflowStageStatus.READY,
        tasks=(validate_demand, approve_demand),
        approval_mode=EnterpriseWorkflowApprovalMode.SINGLE,
        required_approvals=1,
        approver_roles=("procurement_manager",),
    )
    sourcing_stage = EnterpriseWorkflowStage(
        stage_id="stage-sourcing",
        name="Supplier Sourcing",
        status=EnterpriseWorkflowStageStatus.PENDING,
        tasks=(sourcing,),
        depends_on=("stage-demand",),
        approval_mode=EnterpriseWorkflowApprovalMode.NONE,
    )

    return EnterpriseWorkflow(
        workflow_id=workflow_id,
        case_id="case-001",
        template_id="procurement-template-v1",
        name="Buyer-to-supplier procurement workflow",
        status=EnterpriseWorkflowStatus.DRAFT,
        priority=priority,
        stages=(demand_stage, sourcing_stage),
        correlation_id="corr-001",
    )


@pytest.fixture()
def services() -> tuple[
    EnterpriseWorkflowStore,
    EnterpriseWorkflowApprovalManager,
    EnterpriseWorkflowTransitionEngine,
    EnterpriseWorkflowAnalytics,
    EnterpriseWorkflowCoordinator,
    EnterpriseWorkflowIntelligence,
]:
    """Build isolated Package V services."""

    store = EnterpriseWorkflowStore()
    approval_manager = EnterpriseWorkflowApprovalManager()
    transition_engine = EnterpriseWorkflowTransitionEngine(store=store)
    analytics = EnterpriseWorkflowAnalytics()
    coordinator = EnterpriseWorkflowCoordinator(
        store=store,
        approval_manager=approval_manager,
        transition_engine=transition_engine,
        analytics=analytics,
    )
    intelligence = EnterpriseWorkflowIntelligence(
        coordinator=coordinator
    )

    return (
        store,
        approval_manager,
        transition_engine,
        analytics,
        coordinator,
        intelligence,
    )


def test_create_load_and_save_workflow(
    services: tuple,
) -> None:
    """Workflow persistence should retain immutable domain state."""

    store, _, _, _, coordinator, _ = services
    workflow = build_workflow()
    context = EnterpriseWorkflowCommandContext(
        actor_id="tester",
        idempotency_key="create-workflow-001",
    )

    created = coordinator.create(workflow, context=context)

    assert created.succeeded
    assert created.store_record is not None
    assert created.store_record.revision == 1
    assert store.get_record(workflow.workflow_id).workflow == workflow

    updated = replace(
        workflow,
        status=EnterpriseWorkflowStatus.VALIDATED,
    )
    saved = coordinator.save(
        updated,
        context=EnterpriseWorkflowCommandContext(
            actor_id="tester",
            expected_revision=1,
        ),
    )

    assert saved.succeeded
    assert saved.store_record is not None
    assert saved.store_record.revision == 2
    assert (
        store.get_record(workflow.workflow_id).workflow.status
        is EnterpriseWorkflowStatus.VALIDATED
    )


def test_optimistic_concurrency_rejects_stale_revision(
    services: tuple,
) -> None:
    """A stale revision must never overwrite newer workflow state."""

    _, _, _, _, coordinator, _ = services
    workflow = build_workflow()

    coordinator.create(
        workflow,
        context=EnterpriseWorkflowCommandContext(actor_id="tester"),
    )

    coordinator.save(
        replace(
            workflow,
            status=EnterpriseWorkflowStatus.VALIDATED,
        ),
        context=EnterpriseWorkflowCommandContext(
            actor_id="tester",
            expected_revision=1,
        ),
    )

    with pytest.raises((ValueError, RuntimeError)):
        coordinator.save(
            replace(
                workflow,
                status=EnterpriseWorkflowStatus.ACTIVE,
            ),
            context=EnterpriseWorkflowCommandContext(
                actor_id="tester",
                expected_revision=1,
            ),
        )


def test_idempotency_replays_original_result(
    services: tuple,
) -> None:
    """Repeated commands with one key should not duplicate writes."""

    _, _, _, _, coordinator, _ = services
    workflow = build_workflow()
    context = EnterpriseWorkflowCommandContext(
        actor_id="tester",
        idempotency_key="same-create-command",
    )

    first = coordinator.create(workflow, context=context)
    second = coordinator.create(workflow, context=context)

    assert first.succeeded
    assert (
        second.outcome
        is EnterpriseWorkflowCoordinatorOutcome.IDEMPOTENT_REPLAY
    )
    assert second.store_record == first.store_record


def test_valid_workflow_lifecycle_transition(
    services: tuple,
) -> None:
    """A valid workflow transition should be applied and audited."""

    _, _, transition_engine, _, _, _ = services
    workflow = build_workflow()

    result = transition_engine.transition_workflow(
        workflow,
        EnterpriseWorkflowStatus.VALIDATED,
        actor_id="tester",
        persist=False,
    )

    assert not result.rejected
    assert (
        result.event.outcome
        is EnterpriseWorkflowTransitionOutcome.APPLIED
    )
    assert (
        result.workflow.status
        is EnterpriseWorkflowStatus.VALIDATED
    )
    assert transition_engine.history(
        workflow_id=workflow.workflow_id
    )


def test_invalid_workflow_transition_is_rejected(
    services: tuple,
) -> None:
    """Policy must reject unsupported lifecycle jumps."""

    _, _, transition_engine, _, _, _ = services
    workflow = build_workflow()

    result = transition_engine.transition_workflow(
        workflow,
        EnterpriseWorkflowStatus.COMPLETED,
        actor_id="tester",
        persist=False,
    )

    assert result.rejected
    assert (
        result.event.outcome
        is EnterpriseWorkflowTransitionOutcome.REJECTED
    )
    assert result.event.violations


def test_task_dependencies_are_enforced(
    services: tuple,
) -> None:
    """Dependent tasks must not run before prerequisites succeed."""

    _, _, transition_engine, _, _, _ = services
    workflow = build_workflow()

    result = transition_engine.transition_task(
        workflow,
        "stage-demand",
        "task-approve-demand",
        EnterpriseWorkflowTaskStatus.RUNNING,
        actor_id="tester",
        persist=False,
    )

    assert result.rejected
    assert result.event.violations


def test_readiness_refresh_promotes_eligible_tasks(
    services: tuple,
) -> None:
    """Readiness refresh should promote dependency-satisfied work."""

    _, _, transition_engine, _, _, _ = services
    workflow = build_workflow()
    demand_stage = workflow.stages[0]
    completed_task = replace(
        demand_stage.tasks[0],
        status=EnterpriseWorkflowTaskStatus.SUCCEEDED,
    )
    updated_stage = replace(
        demand_stage,
        tasks=(completed_task, demand_stage.tasks[1]),
    )
    updated_workflow = replace(
        workflow,
        status=EnterpriseWorkflowStatus.ACTIVE,
        stages=(updated_stage, workflow.stages[1]),
    )

    refreshed = transition_engine.refresh_readiness(
        updated_workflow
    )

    assert (
        refreshed.stages[0].tasks[1].status
        is EnterpriseWorkflowTaskStatus.READY
    )


def test_stage_approval_lifecycle(
    services: tuple,
) -> None:
    """Stage approval should be requested, decided, and applied."""

    _, approval_manager, _, _, coordinator, _ = services
    workflow = build_workflow()

    requested = coordinator.request_stage_approval(
        workflow,
        "stage-demand",
        reason="Buyer commercial commitment requires approval.",
        context=EnterpriseWorkflowCommandContext(actor_id="requester"),
    )

    assert requested.succeeded
    assert requested.approval_request is not None
    assert (
        requested.approval_request.status
        is EnterpriseWorkflowApprovalStatus.PENDING
    )

    decided = coordinator.decide_approval(
        requested.approval_request.request_id,
        EnterpriseWorkflowApprovalDecision.APPROVE,
        approver_roles=("procurement_manager",),
        comment="Buyer readiness verified.",
        context=EnterpriseWorkflowCommandContext(actor_id="approver"),
    )

    assert decided.succeeded
    assert decided.approval_result is not None
    assert decided.approval_result.accepted
    assert (
        approval_manager.get(
            requested.approval_request.request_id
        ).status
        is EnterpriseWorkflowApprovalStatus.APPROVED
    )


def test_approval_rejects_duplicate_vote(
    services: tuple,
) -> None:
    """One approver must not cast duplicate decisions."""

    _, approval_manager, _, _, _, _ = services
    workflow = build_workflow()
    request = approval_manager.create_for_stage(
        workflow,
        "stage-demand",
        requested_by="requester",
    )

    first = approval_manager.decide(
        request.request_id,
        approver_id="approver-1",
        decision=EnterpriseWorkflowApprovalDecision.APPROVE,
        approver_roles=("procurement_manager",),
    )
    second = approval_manager.decide(
        request.request_id,
        approver_id="approver-1",
        decision=EnterpriseWorkflowApprovalDecision.APPROVE,
        approver_roles=("procurement_manager",),
    )

    assert first.accepted
    assert not second.accepted
    assert second.violations


def test_analytics_detects_failed_task_and_blocked_stage(
    services: tuple,
) -> None:
    """Analytics should surface operational degradation."""

    _, _, _, analytics, _, _ = services
    workflow = build_workflow()
    failed_task = replace(
        workflow.stages[0].tasks[0],
        status=EnterpriseWorkflowTaskStatus.FAILED,
    )
    blocked_stage = replace(
        workflow.stages[0],
        status=EnterpriseWorkflowStageStatus.BLOCKED,
        tasks=(failed_task, workflow.stages[0].tasks[1]),
    )
    degraded = replace(
        workflow,
        status=EnterpriseWorkflowStatus.ACTIVE,
        stages=(blocked_stage, workflow.stages[1]),
    )

    report = analytics.analyse(degraded)

    assert report.task_metrics.failed == 1
    assert report.stage_metrics.blocked == 1
    assert report.health_score < 100.0
    assert report.health_label in {
        "watch",
        "at_risk",
        "critical",
    }
    assert report.bottlenecks


def test_intelligence_generates_explainable_actions(
    services: tuple,
) -> None:
    """Intelligence should explain risk and recommend intervention."""

    _, _, _, _, _, intelligence = services
    workflow = build_workflow(
        priority=EnterpriseWorkflowPriority.CRITICAL
    )
    failed_task = replace(
        workflow.stages[0].tasks[0],
        status=EnterpriseWorkflowTaskStatus.FAILED,
    )
    blocked_stage = replace(
        workflow.stages[0],
        status=EnterpriseWorkflowStageStatus.BLOCKED,
        tasks=(failed_task, workflow.stages[0].tasks[1]),
    )
    degraded = replace(
        workflow,
        status=EnterpriseWorkflowStatus.ACTIVE,
        stages=(blocked_stage, workflow.stages[1]),
    )

    report = intelligence.analyse(degraded)

    assert report.findings
    assert report.recommended_actions
    assert report.overall_severity in {
        EnterpriseWorkflowIntelligenceSeverity.HIGH,
        EnterpriseWorkflowIntelligenceSeverity.CRITICAL,
    }
    assert any(
        action.action_type
        in {
            EnterpriseWorkflowRecommendedActionType.RESOLVE_BLOCKER,
            EnterpriseWorkflowRecommendedActionType.INVESTIGATE_FAILURE,
            EnterpriseWorkflowRecommendedActionType.PAUSE_WORKFLOW,
        }
        for action in report.recommended_actions
    )
    assert report.summary


def test_safe_automatic_readiness_action(
    services: tuple,
) -> None:
    """A non-sensitive readiness action may execute automatically."""

    _, _, _, _, _, intelligence = services
    workflow = replace(
        build_workflow(),
        status=EnterpriseWorkflowStatus.ACTIVE,
        stages=tuple(
            replace(
                stage,
                status=EnterpriseWorkflowStageStatus.PENDING,
                tasks=tuple(
                    replace(
                        task,
                        status=EnterpriseWorkflowTaskStatus.PENDING,
                    )
                    for task in stage.tasks
                ),
            )
            for stage in build_workflow().stages
        ),
    )

    report = intelligence.analyse(
        workflow,
        context=EnterpriseWorkflowCommandContext(
            actor_id="intelligence-engine",
            persist=False,
        ),
    )
    action = next(
        item
        for item in report.recommended_actions
        if item.action_type
        is EnterpriseWorkflowRecommendedActionType.REFRESH_READINESS
    )

    result = intelligence.execute_recommended_action(
        workflow,
        action,
        context=EnterpriseWorkflowCommandContext(
            actor_id="intelligence-engine",
            persist=False,
        ),
    )

    assert result.succeeded
    assert result.workflow is not None


def test_sensitive_recommended_action_requires_approval(
    services: tuple,
) -> None:
    """Sensitive intelligence actions must not execute automatically."""

    _, _, _, _, _, intelligence = services
    workflow = build_workflow(
        priority=EnterpriseWorkflowPriority.CRITICAL
    )
    failed_task = replace(
        workflow.stages[0].tasks[0],
        status=EnterpriseWorkflowTaskStatus.FAILED,
    )
    degraded = replace(
        workflow,
        status=EnterpriseWorkflowStatus.ACTIVE,
        stages=(
            replace(
                workflow.stages[0],
                status=EnterpriseWorkflowStageStatus.BLOCKED,
                tasks=(
                    failed_task,
                    workflow.stages[0].tasks[1],
                ),
            ),
            workflow.stages[1],
        ),
    )
    report = intelligence.analyse(degraded)
    protected_action = next(
        action
        for action in report.recommended_actions
        if action.requires_approval
    )

    with pytest.raises(PermissionError):
        intelligence.execute_recommended_action(
            degraded,
            protected_action,
            context=EnterpriseWorkflowCommandContext(
                actor_id="intelligence-engine",
                persist=False,
            ),
        )


def test_archive_and_restore_workflow(
    services: tuple,
) -> None:
    """Archive and restore should preserve workflow history."""

    store, _, _, _, coordinator, _ = services
    workflow = build_workflow()

    coordinator.create(
        workflow,
        context=EnterpriseWorkflowCommandContext(actor_id="tester"),
    )
    archived = coordinator.archive(
        workflow.workflow_id,
        context=EnterpriseWorkflowCommandContext(
            actor_id="tester",
            expected_revision=1,
        ),
    )

    assert archived.succeeded
    assert archived.store_record is not None
    assert archived.store_record.archived

    restored = coordinator.restore(
        workflow.workflow_id,
        context=EnterpriseWorkflowCommandContext(
            actor_id="tester",
            expected_revision=archived.store_record.revision,
        ),
    )

    assert restored.succeeded
    assert restored.store_record is not None
    assert not restored.store_record.archived
    assert store.get_record(workflow.workflow_id).workflow.workflow_id == (
        workflow.workflow_id
    )


def test_portfolio_intelligence_aggregates_workflows(
    services: tuple,
) -> None:
    """Portfolio intelligence should aggregate health and risk."""

    _, _, _, _, coordinator, intelligence = services
    healthy = build_workflow(workflow_id="workflow-healthy")
    critical = build_workflow(
        workflow_id="workflow-critical",
        priority=EnterpriseWorkflowPriority.CRITICAL,
    )
    failed_task = replace(
        critical.stages[0].tasks[0],
        status=EnterpriseWorkflowTaskStatus.FAILED,
    )
    critical = replace(
        critical,
        status=EnterpriseWorkflowStatus.FAILED,
        stages=(
            replace(
                critical.stages[0],
                status=EnterpriseWorkflowStageStatus.BLOCKED,
                tasks=(
                    failed_task,
                    critical.stages[0].tasks[1],
                ),
            ),
            critical.stages[1],
        ),
    )

    coordinator.create(
        healthy,
        context=EnterpriseWorkflowCommandContext(actor_id="tester"),
    )
    coordinator.create(
        critical,
        context=EnterpriseWorkflowCommandContext(actor_id="tester"),
    )

    report = intelligence.analyse_portfolio()

    assert report.portfolio_report.total_workflows == 2
    assert report.portfolio_report.failed_workflows == 1
    assert report.findings
    assert report.summary


def test_metadata_is_redacted_in_public_results(
    services: tuple,
) -> None:
    """Sensitive metadata should not leak through coordinator results."""

    _, _, _, _, coordinator, _ = services
    workflow = build_workflow()
    result = coordinator.create(
        workflow,
        context=EnterpriseWorkflowCommandContext(
            actor_id="tester",
            metadata={
                "api_key": "secret-value",
                "safe_reference": "case-001",
            },
        ),
    )

    serialised = result.as_dict()
    metadata = serialised["event"]["metadata"]

    assert metadata["safe_reference"] == "case-001"
    assert metadata["api_key"] != "secret-value"


def test_runtime_histories_can_be_cleared(
    services: tuple,
) -> None:
    """Test isolation and controlled runtime cleanup."""

    _, _, transition_engine, _, coordinator, intelligence = services
    workflow = build_workflow()

    transition_engine.transition_workflow(
        workflow,
        EnterpriseWorkflowStatus.VALIDATED,
        actor_id="tester",
        persist=False,
    )
    intelligence.analyse(
        workflow,
        context=EnterpriseWorkflowCommandContext(
            actor_id="tester",
            persist=False,
        ),
    )

    assert transition_engine.history()
    assert intelligence.history()

    transition_engine.clear_history()
    intelligence.clear_history()
    coordinator.clear_runtime_state()

    assert transition_engine.history() == ()
    assert intelligence.history() == ()
    assert coordinator.events() == ()
