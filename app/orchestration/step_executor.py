"""Workflow-step handler registration and execution."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from app.observability.logging_config import get_logger
from app.orchestration.execution_result import (
    ExecutionOutcome,
    StepExecutionRecord,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
)
from app.orchestration.workflow_context import (
    WorkflowContext,
)
from app.orchestration.workflow_models import (
    FailureStrategy,
    StepStatus,
    WorkflowStepDefinition,
)
from app.resilience.exceptions import (
    DawlatPlatformError,
    normalise_exception,
)
from app.resilience.retry_policy import (
    RetryExecutor,
    RetryPolicy,
)


StepHandler = Callable[
    [WorkflowContext, dict[str, Any]],
    Any,
]


def _utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class StepHandlerRegistry:
    """Thread-safe registry of workflow-step handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, StepHandler] = {}
        self._lock = threading.RLock()

    def register(
        self,
        step_id: str,
        handler: StepHandler,
        *,
        replace_existing: bool = False,
    ) -> None:
        """Register a handler for a workflow step."""

        cleaned_step_id = str(step_id or "").strip()

        if not cleaned_step_id:
            raise ValueError("Workflow step ID is required.")

        if not callable(handler):
            raise TypeError("Step handler must be callable.")

        with self._lock:
            if (
                cleaned_step_id in self._handlers
                and not replace_existing
            ):
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"A handler for step "
                        f"{cleaned_step_id!r} "
                        "is already registered."
                    ),
                    metadata={
                        "step_id": cleaned_step_id,
                    },
                )

            self._handlers[cleaned_step_id] = handler

    def get(
        self,
        step_id: str,
    ) -> StepHandler:
        """Return the registered handler for a step."""

        cleaned_step_id = str(step_id or "").strip()

        if not cleaned_step_id:
            raise ValueError("Workflow step ID is required.")

        with self._lock:
            handler = self._handlers.get(cleaned_step_id)

        if handler is None:
            raise WorkflowIntegrityError(
                technical_message=(
                    f"No execution handler is registered for "
                    f"step {cleaned_step_id!r}."
                ),
                metadata={
                    "step_id": cleaned_step_id,
                },
            )

        return handler

    def contains(
        self,
        step_id: str,
    ) -> bool:
        """Return whether a step handler exists."""

        cleaned_step_id = str(step_id or "").strip()

        with self._lock:
            return cleaned_step_id in self._handlers

    def unregister(
        self,
        step_id: str,
    ) -> StepHandler:
        """Remove and return a registered handler."""

        cleaned_step_id = str(step_id or "").strip()

        with self._lock:
            handler = self._handlers.pop(
                cleaned_step_id,
                None,
            )

        if handler is None:
            raise WorkflowIntegrityError(
                technical_message=(
                    f"No handler exists for step "
                    f"{cleaned_step_id!r}."
                )
            )

        return handler

    def clear(self) -> None:
        """Remove all registered handlers."""

        with self._lock:
            self._handlers.clear()


class StepExecutor:
    """Execute individual workflow steps safely."""

    def __init__(
        self,
        handler_registry: StepHandlerRegistry | None = None,
    ) -> None:
        self._handler_registry = (
            handler_registry or StepHandlerRegistry()
        )
        self._logger = get_logger(
            "orchestration.step_executor"
        )

    @property
    def handler_registry(self) -> StepHandlerRegistry:
        """Return the active handler registry."""

        return self._handler_registry

    def execute(
        self,
        step: WorkflowStepDefinition,
        *,
        context: WorkflowContext,
        workflow_data: dict[str, Any],
    ) -> StepExecutionRecord:
        """Execute a workflow step and return a stable record."""

        if not isinstance(step, WorkflowStepDefinition):
            raise TypeError(
                "Step must be a WorkflowStepDefinition."
            )

        if not isinstance(context, WorkflowContext):
            raise TypeError(
                "Context must be a WorkflowContext."
            )

        handler = self._handler_registry.get(step.step_id)
        step_context = context.for_step(step.step_id)
        started_at = _utc_timestamp()

        try:
            if (
                step.failure_strategy
                is FailureStrategy.RETRY
                and step.maximum_attempts > 1
            ):
                retry_executor = RetryExecutor(
                    RetryPolicy(
                        max_attempts=step.maximum_attempts,
                        initial_delay_seconds=0,
                        maximum_delay_seconds=0,
                        jitter_ratio=0,
                    ),
                    sleep_function=lambda _: None,
                )

                retry_result = retry_executor.execute(
                    lambda: handler(
                        step_context,
                        dict(workflow_data),
                    ),
                    operation_name=step.step_id,
                )

                output = retry_result.value
                attempt_count = len(
                    retry_result.attempts
                )

            else:
                output = handler(
                    step_context,
                    dict(workflow_data),
                )
                attempt_count = 1

            completed_at = _utc_timestamp()

            record = StepExecutionRecord(
                step_id=step.step_id,
                step_name=step.name,
                outcome=ExecutionOutcome.SUCCEEDED,
                status=StepStatus.SUCCEEDED,
                attempt_count=attempt_count,
                started_at=started_at,
                completed_at=completed_at,
                output=output,
            )

            self._logger.info(
                "Workflow step execution succeeded.",
                extra={
                    "workflow_id": context.workflow_id,
                    "workflow_version": (
                        context.workflow_version
                    ),
                    "instance_id": context.instance_id,
                    "step_id": step.step_id,
                    "attempt_count": attempt_count,
                },
            )

            return record

        except Exception as error:
            normalised = normalise_exception(error)
            completed_at = _utc_timestamp()

            attempt_count = self._resolve_attempt_count(
                step,
                normalised,
            )

            record = StepExecutionRecord(
                step_id=step.step_id,
                step_name=step.name,
                outcome=ExecutionOutcome.FAILED,
                status=StepStatus.FAILED,
                attempt_count=attempt_count,
                started_at=started_at,
                completed_at=completed_at,
                error_code=normalised.code,
                error_id=normalised.error_id,
                safe_error_message=(
                    normalised.safe_message
                ),
                metadata={
                    "failure_strategy": (
                        step.failure_strategy.value
                    ),
                },
            )

            self._logger.error(
                "Workflow step execution failed.",
                extra={
                    "workflow_id": context.workflow_id,
                    "workflow_version": (
                        context.workflow_version
                    ),
                    "instance_id": context.instance_id,
                    "step_id": step.step_id,
                    "error": normalised.diagnostic_payload(),
                },
            )

            return record

    @staticmethod
    def _resolve_attempt_count(
        step: WorkflowStepDefinition,
        error: DawlatPlatformError,
    ) -> int:
        """Resolve deterministic attempt count after failure."""

        if (
            step.failure_strategy
            is FailureStrategy.RETRY
            and step.maximum_attempts > 1
        ):
            if error.code == "DAWLAT_RETRY_EXHAUSTED":
                return step.maximum_attempts

        return 1