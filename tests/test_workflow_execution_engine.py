"""Tests for Phase 21 Package C workflow execution engine."""

from __future__ import annotations

import pytest

from app.orchestration import (
    ExecutionOutcome,
    FailureStrategy,
    InMemoryExecutionStore,
    StepExecutor,
    StepHandlerRegistry,
    StepStatus,
    WorkflowDefinition,
    WorkflowExecutionEngine,
    WorkflowIntegrityError,
    WorkflowNotFoundError,
    WorkflowStatus,
    WorkflowStepDefinition,
    WorkflowValidationError,
    create_workflow_context,
)
from app.resilience.exceptions import (
    NetworkError,
    ValidationError,
)


def build_definition() -> WorkflowDefinition:
    """Create a valid three-step workflow."""

    return WorkflowDefinition(
        workflow_id="supplier-procurement",
        name="Supplier Procurement Workflow",
        version="1.0.0",
        initial_step_id="verify-buyer",
        terminal_step_ids=("issue-order",),
        steps=(
            WorkflowStepDefinition(
                step_id="verify-buyer",
                name="Verify Buyer",
            ),
            WorkflowStepDefinition(
                step_id="compare-quotes",
                name="Compare Quotations",
                dependencies=("verify-buyer",),
            ),
            WorkflowStepDefinition(
                step_id="issue-order",
                name="Issue Purchase Order",
                dependencies=("compare-quotes",),
            ),
        ),
    )


def build_engine(
    registry: StepHandlerRegistry | None = None,
) -> WorkflowExecutionEngine:
    """Create an isolated execution engine."""

    return WorkflowExecutionEngine(
        step_executor=StepExecutor(
            registry or StepHandlerRegistry()
        ),
        execution_store=InMemoryExecutionStore(),
    )


def register_success_handlers(
    registry: StepHandlerRegistry,
) -> None:
    """Register handlers for the standard workflow."""

    registry.register(
        "verify-buyer",
        lambda context, data: {
            "buyer_verified": True,
            "instance_id": context.instance_id,
        },
    )
    registry.register(
        "compare-quotes",
        lambda context, data: {
            "selected_supplier": "SUP-100",
        },
    )
    registry.register(
        "issue-order",
        lambda context, data: {
            "purchase_order": "PO-100",
        },
    )


def test_handler_registry_registers_handler() -> None:
    registry = StepHandlerRegistry()

    handler = lambda context, data: "ok"

    registry.register("verify-buyer", handler)

    assert registry.contains("verify-buyer") is True
    assert registry.get("verify-buyer") is handler


def test_handler_registry_rejects_duplicate() -> None:
    registry = StepHandlerRegistry()

    registry.register(
        "verify-buyer",
        lambda context, data: "first",
    )

    with pytest.raises(WorkflowIntegrityError):
        registry.register(
            "verify-buyer",
            lambda context, data: "second",
        )


def test_handler_registry_allows_replacement() -> None:
    registry = StepHandlerRegistry()

    first = lambda context, data: "first"
    second = lambda context, data: "second"

    registry.register("verify-buyer", first)
    registry.register(
        "verify-buyer",
        second,
        replace_existing=True,
    )

    assert registry.get("verify-buyer") is second


def test_missing_handler_fails_closed() -> None:
    registry = StepHandlerRegistry()

    with pytest.raises(WorkflowIntegrityError):
        registry.get("missing-step")


def test_execution_store_creates_instance() -> None:
    store = InMemoryExecutionStore()
    engine = WorkflowExecutionEngine(
        execution_store=store,
    )

    instance = engine.create_instance(
        build_definition()
    )

    assert store.get(instance.instance_id) is instance

    statuses = store.get_step_statuses(
        instance.instance_id
    )

    assert all(
        status is StepStatus.PENDING
        for status in statuses.values()
    )


def test_execution_store_rejects_duplicate_instance() -> None:
    store = InMemoryExecutionStore()
    engine = WorkflowExecutionEngine(
        execution_store=store,
    )

    instance = engine.create_instance(
        build_definition()
    )

    with pytest.raises(WorkflowIntegrityError):
        store.create(
            instance,
            {
                "verify-buyer": StepStatus.PENDING,
            },
        )


def test_execution_store_returns_defensive_copy() -> None:
    store = InMemoryExecutionStore()
    engine = WorkflowExecutionEngine(
        execution_store=store,
    )

    instance = engine.create_instance(
        build_definition()
    )

    statuses = store.get_step_statuses(
        instance.instance_id
    )
    statuses["verify-buyer"] = StepStatus.FAILED

    persisted = store.get_step_statuses(
        instance.instance_id
    )

    assert (
        persisted["verify-buyer"]
        is StepStatus.PENDING
    )


def test_execution_store_rejects_unknown_instance() -> None:
    store = InMemoryExecutionStore()

    with pytest.raises(WorkflowNotFoundError):
        store.get("missing-instance")


def test_engine_rejects_invalid_definition() -> None:
    engine = build_engine()

    invalid = WorkflowDefinition(
        workflow_id="",
        name="",
        version="",
        steps=(),
    )

    with pytest.raises(WorkflowValidationError):
        engine.create_instance(invalid)


def test_step_executor_executes_handler() -> None:
    registry = StepHandlerRegistry()
    registry.register(
        "verify-buyer",
        lambda context, data: {
            "verified": True,
        },
    )

    executor = StepExecutor(registry)

    record = executor.execute(
        WorkflowStepDefinition(
            step_id="verify-buyer",
            name="Verify Buyer",
        ),
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
        workflow_data={},
    )

    assert record.successful is True
    assert record.status is StepStatus.SUCCEEDED
    assert record.output == {"verified": True}
    assert record.attempt_count == 1


def test_step_executor_converts_failure_to_record() -> None:
    registry = StepHandlerRegistry()

    def failing_handler(context, data):
        raise ValidationError("Buyer data invalid.")

    registry.register(
        "verify-buyer",
        failing_handler,
    )

    executor = StepExecutor(registry)

    record = executor.execute(
        WorkflowStepDefinition(
            step_id="verify-buyer",
            name="Verify Buyer",
        ),
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
        workflow_data={},
    )

    assert record.failed is True
    assert record.status is StepStatus.FAILED
    assert record.error_code == "DAWLAT_VALIDATION_ERROR"


def test_step_executor_retries_retryable_failure() -> None:
    registry = StepHandlerRegistry()
    state = {"attempts": 0}

    def handler(context, data):
        state["attempts"] += 1

        if state["attempts"] < 3:
            raise NetworkError("Temporary failure.")

        return {"status": "recovered"}

    registry.register("compare-quotes", handler)

    executor = StepExecutor(registry)

    record = executor.execute(
        WorkflowStepDefinition(
            step_id="compare-quotes",
            name="Compare Quotations",
            failure_strategy=FailureStrategy.RETRY,
            maximum_attempts=3,
        ),
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
        workflow_data={},
    )

    assert record.successful is True
    assert record.attempt_count == 3
    assert state["attempts"] == 3


def test_step_executor_records_retry_exhaustion() -> None:
    registry = StepHandlerRegistry()
    state = {"attempts": 0}

    def handler(context, data):
        state["attempts"] += 1
        raise NetworkError("Still unavailable.")

    registry.register("compare-quotes", handler)

    executor = StepExecutor(registry)

    record = executor.execute(
        WorkflowStepDefinition(
            step_id="compare-quotes",
            name="Compare Quotations",
            failure_strategy=FailureStrategy.RETRY,
            maximum_attempts=3,
        ),
        context=create_workflow_context(
            "supplier-procurement",
            "1.0.0",
        ),
        workflow_data={},
    )

    assert record.failed is True
    assert record.attempt_count == 3
    assert record.error_code == "DAWLAT_RETRY_EXHAUSTED"
    assert state["attempts"] == 3


def test_engine_executes_complete_workflow() -> None:
    registry = StepHandlerRegistry()
    register_success_handlers(registry)

    engine = build_engine(registry)

    result = engine.execute(
        build_definition(),
        data={
            "buyer_id": "BUY-100",
        },
    )

    assert result.successful is True
    assert result.outcome is ExecutionOutcome.SUCCEEDED
    assert result.instance.status is WorkflowStatus.COMPLETED
    assert result.step_count == 3
    assert result.instance.completed_step_ids == (
        "verify-buyer",
        "compare-quotes",
        "issue-order",
    )


def test_engine_executes_steps_in_dependency_order() -> None:
    registry = StepHandlerRegistry()
    execution_order: list[str] = []

    registry.register(
        "verify-buyer",
        lambda context, data: execution_order.append(
            "verify-buyer"
        ),
    )
    registry.register(
        "compare-quotes",
        lambda context, data: execution_order.append(
            "compare-quotes"
        ),
    )
    registry.register(
        "issue-order",
        lambda context, data: execution_order.append(
            "issue-order"
        ),
    )

    engine = build_engine(registry)
    engine.execute(build_definition())

    assert execution_order == [
        "verify-buyer",
        "compare-quotes",
        "issue-order",
    ]


def test_engine_stores_step_outputs() -> None:
    registry = StepHandlerRegistry()
    register_success_handlers(registry)

    engine = build_engine(registry)
    result = engine.execute(build_definition())

    outputs = result.instance.data["step_outputs"]

    assert outputs["verify-buyer"]["buyer_verified"] is True
    assert (
        outputs["compare-quotes"]["selected_supplier"]
        == "SUP-100"
    )
    assert (
        outputs["issue-order"]["purchase_order"]
        == "PO-100"
    )


def test_engine_stops_after_failed_step() -> None:
    registry = StepHandlerRegistry()
    executed: list[str] = []

    registry.register(
        "verify-buyer",
        lambda context, data: executed.append(
            "verify-buyer"
        ),
    )

    def fail_quote_comparison(context, data):
        executed.append("compare-quotes")
        raise ValidationError("No compliant quotation.")

    registry.register(
        "compare-quotes",
        fail_quote_comparison,
    )
    registry.register(
        "issue-order",
        lambda context, data: executed.append(
            "issue-order"
        ),
    )

    engine = build_engine(registry)
    result = engine.execute(build_definition())

    assert result.failed is True
    assert result.instance.status is WorkflowStatus.FAILED
    assert result.failed_step_ids == ("compare-quotes",)
    assert executed == [
        "verify-buyer",
        "compare-quotes",
    ]


def test_engine_records_failed_step_on_instance() -> None:
    registry = StepHandlerRegistry()

    registry.register(
        "verify-buyer",
        lambda context, data: (
            _ for _ in ()
        ).throw(
            ValidationError("Invalid buyer.")
        ),
    )

    engine = build_engine(registry)
    result = engine.execute(build_definition())

    assert result.instance.failed_step_ids == (
        "verify-buyer",
    )
    assert result.step_count == 1


def test_engine_uses_supplied_context() -> None:
    registry = StepHandlerRegistry()
    observed: dict[str, str] = {}

    def verify_handler(context, data):
        observed["actor_id"] = context.actor_id
        observed["instance_id"] = context.instance_id
        return {"verified": True}

    registry.register("verify-buyer", verify_handler)
    registry.register(
        "compare-quotes",
        lambda context, data: {},
    )
    registry.register(
        "issue-order",
        lambda context, data: {},
    )

    engine = build_engine(registry)

    context = create_workflow_context(
        "supplier-procurement",
        "1.0.0",
        actor_id="USER-500",
    )

    result = engine.execute(
        build_definition(),
        context=context,
    )

    assert observed["actor_id"] == "USER-500"
    assert (
        observed["instance_id"]
        == result.instance.instance_id
    )


def test_execution_result_serialises_safely() -> None:
    registry = StepHandlerRegistry()
    register_success_handlers(registry)

    result = build_engine(registry).execute(
        build_definition()
    )

    payload = result.as_dict()

    assert payload["successful"] is True
    assert payload["outcome"] == "succeeded"
    assert payload["workflow_status"] == "completed"
    assert len(payload["step_records"]) == 3


def test_store_lists_instances_deterministically() -> None:
    store = InMemoryExecutionStore()
    engine = WorkflowExecutionEngine(
        execution_store=store,
    )

    first = engine.create_instance(build_definition())
    second = engine.create_instance(build_definition())

    instances = store.list_instances()

    assert set(
        instance.instance_id
        for instance in instances
    ) == {
        first.instance_id,
        second.instance_id,
    }


def test_store_deletes_instance() -> None:
    store = InMemoryExecutionStore()
    engine = WorkflowExecutionEngine(
        execution_store=store,
    )

    instance = engine.create_instance(build_definition())
    removed = store.delete(instance.instance_id)

    assert removed.instance_id == instance.instance_id

    with pytest.raises(WorkflowNotFoundError):
        store.get(instance.instance_id)