"""Tests for Phase 21 workflow orchestration foundation."""

from __future__ import annotations

import pytest

from app.orchestration import (
    DuplicateWorkflowError,
    FailureStrategy,
    StepType,
    WorkflowDefinition,
    WorkflowDefinitionValidator,
    WorkflowNotFoundError,
    WorkflowRegistry,
    WorkflowStepDefinition,
    WorkflowValidationError,
    create_workflow_context,
    get_workflow_context,
    workflow_context,
)


def build_valid_workflow(
    *,
    version: str = "1.0.0",
    enabled: bool = True,
) -> WorkflowDefinition:
    """Create a valid deterministic workflow definition."""

    return WorkflowDefinition(
        workflow_id="procurement-order",
        name="Procurement Order Workflow",
        version=version,
        description=(
            "Controls buyer approval through supplier ordering."
        ),
        initial_step_id="verify-buyer",
        terminal_step_ids=("issue-order",),
        enabled=enabled,
        tags=("procurement", "enterprise"),
        steps=(
            WorkflowStepDefinition(
                step_id="verify-buyer",
                name="Verify Buyer",
                step_type=StepType.DECISION,
            ),
            WorkflowStepDefinition(
                step_id="approve-commercials",
                name="Approve Commercial Terms",
                step_type=StepType.APPROVAL,
                dependencies=("verify-buyer",),
                required_roles=("commercial_manager",),
            ),
            WorkflowStepDefinition(
                step_id="issue-order",
                name="Issue Purchase Order",
                dependencies=("approve-commercials",),
                failure_strategy=FailureStrategy.RETRY,
                maximum_attempts=3,
                timeout_seconds=30,
            ),
        ),
    )


def test_workflow_context_generates_identity() -> None:
    context = create_workflow_context(
        "supplier-onboarding",
        "1.0.0",
        request_id="REQ-100",
        actor_id="USER-1",
        country_code="au",
        metadata={"api_key": "secret-value"},
    )

    assert context.workflow_id == "supplier-onboarding"
    assert context.workflow_version == "1.0.0"
    assert context.instance_id
    assert context.correlation_id == "REQ-100"
    assert context.country_code == "AU"
    assert context.metadata["api_key"] != "secret-value"


def test_workflow_context_requires_identity() -> None:
    with pytest.raises(ValueError):
        create_workflow_context("", "1.0.0")

    with pytest.raises(ValueError):
        create_workflow_context("workflow", "")


def test_workflow_context_supports_step_and_attempt() -> None:
    context = create_workflow_context(
        "quotation",
        "1.0.0",
    )

    step_context = context.for_step("compare-quotes")
    retry_context = step_context.next_attempt()

    assert step_context.current_step_id == "compare-quotes"
    assert retry_context.attempt_number == 2
    assert retry_context.instance_id == context.instance_id


def test_workflow_context_manager_restores_previous() -> None:
    previous = get_workflow_context()
    active = create_workflow_context(
        "shipment",
        "1.0.0",
    )

    with workflow_context(active):
        assert get_workflow_context() is active

    assert get_workflow_context() is previous


def test_workflow_definition_exposes_stable_registry_key() -> None:
    definition = build_valid_workflow()

    assert (
        definition.registry_key
        == "procurement-order:1.0.0"
    )
    assert definition.step_ids == (
        "verify-buyer",
        "approve-commercials",
        "issue-order",
    )
    assert (
        definition.get_step("issue-order").maximum_attempts
        == 3
    )


def test_valid_workflow_passes_validation() -> None:
    result = WorkflowDefinitionValidator().validate(
        build_valid_workflow()
    )

    assert result.valid is True
    assert result.error_count == 0
    assert result.issues == ()


def test_validator_rejects_duplicate_step_ids() -> None:
    definition = WorkflowDefinition(
        workflow_id="duplicate-test",
        name="Duplicate Test",
        version="1.0.0",
        initial_step_id="step-one",
        steps=(
            WorkflowStepDefinition(
                step_id="step-one",
                name="First",
            ),
            WorkflowStepDefinition(
                step_id="step-one",
                name="Duplicate",
            ),
        ),
    )

    result = WorkflowDefinitionValidator().validate(
        definition
    )

    assert result.valid is False
    assert any(
        issue.code == "DUPLICATE_STEP_ID"
        for issue in result.issues
    )


def test_validator_rejects_unknown_dependency() -> None:
    definition = WorkflowDefinition(
        workflow_id="dependency-test",
        name="Dependency Test",
        version="1.0.0",
        initial_step_id="step-one",
        steps=(
            WorkflowStepDefinition(
                step_id="step-one",
                name="First",
                dependencies=("missing-step",),
            ),
        ),
    )

    result = WorkflowDefinitionValidator().validate(
        definition
    )

    assert any(
        issue.code == "UNKNOWN_STEP_DEPENDENCY"
        for issue in result.issues
    )


def test_validator_detects_dependency_cycle() -> None:
    definition = WorkflowDefinition(
        workflow_id="cycle-test",
        name="Cycle Test",
        version="1.0.0",
        initial_step_id="step-one",
        steps=(
            WorkflowStepDefinition(
                step_id="step-one",
                name="First",
                dependencies=("step-two",),
            ),
            WorkflowStepDefinition(
                step_id="step-two",
                name="Second",
                dependencies=("step-one",),
            ),
        ),
    )

    result = WorkflowDefinitionValidator().validate(
        definition
    )

    assert any(
        issue.code == "CYCLIC_DEPENDENCY"
        for issue in result.issues
    )


def test_validator_requires_compensation_step() -> None:
    definition = WorkflowDefinition(
        workflow_id="compensation-test",
        name="Compensation Test",
        version="1.0.0",
        initial_step_id="payment",
        steps=(
            WorkflowStepDefinition(
                step_id="payment",
                name="Payment",
                failure_strategy=FailureStrategy.COMPENSATE,
            ),
        ),
    )

    result = WorkflowDefinitionValidator().validate(
        definition
    )

    assert any(
        issue.code == "COMPENSATION_STEP_REQUIRED"
        for issue in result.issues
    )


def test_registry_registers_and_reads_workflow() -> None:
    registry = WorkflowRegistry()
    definition = build_valid_workflow()

    registered = registry.register(definition)

    assert registered is definition
    assert registry.contains(
        "procurement-order",
        "1.0.0",
    )
    assert (
        registry.get(
            "procurement-order",
            "1.0.0",
        )
        is definition
    )


def test_registry_rejects_duplicate_workflow() -> None:
    registry = WorkflowRegistry()
    definition = build_valid_workflow()

    registry.register(definition)

    with pytest.raises(DuplicateWorkflowError):
        registry.register(definition)


def test_registry_allows_explicit_replacement() -> None:
    registry = WorkflowRegistry()
    first = build_valid_workflow()
    replacement = build_valid_workflow()

    registry.register(first)
    registry.register(
        replacement,
        replace_existing=True,
    )

    assert (
        registry.get(
            "procurement-order",
            "1.0.0",
        )
        is replacement
    )


def test_registry_rejects_invalid_workflow() -> None:
    registry = WorkflowRegistry()

    invalid = WorkflowDefinition(
        workflow_id="",
        name="",
        version="",
        steps=(),
    )

    with pytest.raises(WorkflowValidationError):
        registry.register(invalid)


def test_registry_returns_latest_version() -> None:
    registry = WorkflowRegistry()

    registry.register(
        build_valid_workflow(version="1.0.0")
    )
    registry.register(
        build_valid_workflow(version="2.0.0")
    )

    latest = registry.get_latest(
        "procurement-order"
    )

    assert latest.version == "2.0.0"


def test_registry_lists_workflows_deterministically() -> None:
    registry = WorkflowRegistry()

    registry.register(
        build_valid_workflow(
            version="2.0.0",
            enabled=False,
        )
    )
    registry.register(
        build_valid_workflow(version="1.0.0")
    )

    all_definitions = registry.list_definitions()
    enabled_definitions = registry.list_definitions(
        enabled_only=True
    )

    assert [
        definition.version
        for definition in all_definitions
    ] == ["1.0.0", "2.0.0"]

    assert [
        definition.version
        for definition in enabled_definitions
    ] == ["1.0.0"]


def test_registry_unregisters_workflow() -> None:
    registry = WorkflowRegistry()
    registry.register(build_valid_workflow())

    removed = registry.unregister(
        "procurement-order",
        "1.0.0",
    )

    assert removed.workflow_id == "procurement-order"
    assert registry.contains(
        "procurement-order",
        "1.0.0",
    ) is False

    with pytest.raises(WorkflowNotFoundError):
        registry.get(
            "procurement-order",
            "1.0.0",
        )