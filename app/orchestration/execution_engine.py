"""Dependency-aware enterprise workflow execution engine."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from app.observability.logging_config import get_logger
from app.orchestration.execution_result import (
    ExecutionOutcome,
    StepExecutionRecord,
    WorkflowExecutionResult,
)
from app.orchestration.execution_store import (
    ExecutionStore,
    InMemoryExecutionStore,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowValidationError,
)
from app.orchestration.state_machine import (
    WorkflowStateMachine,
)
from app.orchestration.step_executor import (
    StepExecutor,
)
from app.orchestration.workflow_context import (
    WorkflowContext,
    create_workflow_context,
    workflow_context,
)
from app.orchestration.workflow_models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from app.orchestration.workflow_validation import (
    WorkflowDefinitionValidator,
)


def _utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class WorkflowExecutionEngine:
    """Create, execute and persist workflow instances."""

    def __init__(
        self,
        *,
        step_executor: StepExecutor | None = None,
        execution_store: ExecutionStore | None = None,
        state_machine: WorkflowStateMachine | None = None,
        validator: WorkflowDefinitionValidator | None = None,
    ) -> None:
        self._step_executor = (
            step_executor or StepExecutor()
        )
        self._execution_store = (
            execution_store or InMemoryExecutionStore()
        )
        self._state_machine = (
            state_machine or WorkflowStateMachine()
        )
        self._validator = (
            validator or WorkflowDefinitionValidator()
        )
        self._logger = get_logger(
            "orchestration.execution_engine"
        )

    @property
    def step_executor(self) -> StepExecutor:
        """Return the active step executor."""

        return self._step_executor

    @property
    def execution_store(self) -> ExecutionStore:
        """Return the active execution store."""

        return self._execution_store

    def create_instance(
        self,
        definition: WorkflowDefinition,
        *,
        data: dict[str, Any] | None = None,
    ) -> WorkflowInstance:
        """Validate a definition and create a workflow instance."""

        validation = self._validator.validate(definition)

        if not validation.valid:
            raise WorkflowValidationError(
                technical_message=(
                    "Workflow definition validation failed "
                    "before execution."
                ),
                metadata={
                    "workflow_id": definition.workflow_id,
                    "workflow_version": definition.version,
                    "issues": [
                        {
                            "code": issue.code,
                            "message": issue.message,
                            "field": issue.field,
                            "step_id": issue.step_id,
                        }
                        for issue in validation.issues
                    ],
                },
            )

        instance = WorkflowInstance(
            workflow_id=definition.workflow_id,
            workflow_version=definition.version,
            status=WorkflowStatus.CREATED,
            current_step_id=(
                definition.initial_step_id
                or definition.steps[0].step_id
            ),
            data=data or {},
        )

        step_statuses = {
            step.step_id: StepStatus.PENDING
            for step in definition.steps
        }

        self._execution_store.create(
            instance,
            step_statuses,
        )

        return instance

    def execute(
        self,
        definition: WorkflowDefinition,
        *,
        data: dict[str, Any] | None = None,
        context: WorkflowContext | None = None,
    ) -> WorkflowExecutionResult:
        """Create and execute a workflow to completion or failure."""

        started_at = _utc_timestamp()
        instance = self.create_instance(
            definition,
            data=data,
        )

        active_context = context or create_workflow_context(
            definition.workflow_id,
            definition.version,
            correlation_id=instance.instance_id,
        )

        if active_context.instance_id != instance.instance_id:
            active_context = replace(
                active_context,
                instance_id=instance.instance_id,
                correlation_id=(
                    active_context.correlation_id
                    or instance.instance_id
                ),
            )

        records: list[StepExecutionRecord] = []

        with workflow_context(active_context):
            ready_result = self._state_machine.prepare(
                instance,
                reason="Workflow definition validated.",
                actor_id=active_context.actor_id,
            )
            instance = ready_result.instance
            self._execution_store.save(instance)

            running_result = self._state_machine.start(
                instance,
                reason="Workflow execution started.",
                actor_id=active_context.actor_id,
            )
            instance = running_result.instance
            self._execution_store.save(instance)

            while True:
                statuses = (
                    self._execution_store
                    .get_step_statuses(
                        instance.instance_id
                    )
                )

                if self._all_steps_successful(statuses):
                    completed = self._state_machine.complete(
                        instance,
                        reason="All workflow steps succeeded.",
                        actor_id=active_context.actor_id,
                    )
                    instance = completed.instance
                    self._execution_store.save(instance)

                    return WorkflowExecutionResult(
                        instance=instance,
                        outcome=ExecutionOutcome.SUCCEEDED,
                        step_records=tuple(records),
                        started_at=started_at,
                        message=(
                            "Workflow completed successfully."
                        ),
                    )

                next_step = self._find_next_ready_step(
                    definition,
                    statuses,
                )

                if next_step is None:
                    failed = self._state_machine.fail(
                        instance,
                        reason=(
                            "Workflow could not identify an "
                            "executable step."
                        ),
                        actor_id=active_context.actor_id,
                    )
                    instance = failed.instance
                    self._execution_store.save(instance)

                    return WorkflowExecutionResult(
                        instance=instance,
                        outcome=ExecutionOutcome.FAILED,
                        step_records=tuple(records),
                        started_at=started_at,
                        message=(
                            "Workflow execution stopped because "
                            "remaining dependencies could not "
                            "be satisfied."
                        ),
                    )

                instance = replace(
                    instance,
                    current_step_id=next_step.step_id,
                    updated_at=_utc_timestamp(),
                )
                self._execution_store.save(instance)

                self._execution_store.update_step_status(
                    instance.instance_id,
                    next_step.step_id,
                    StepStatus.READY,
                )
                self._execution_store.update_step_status(
                    instance.instance_id,
                    next_step.step_id,
                    StepStatus.RUNNING,
                )

                record = self._step_executor.execute(
                    next_step,
                    context=active_context,
                    workflow_data=instance.data,
                )
                records.append(record)

                self._execution_store.update_step_status(
                    instance.instance_id,
                    next_step.step_id,
                    record.status,
                )

                if record.failed:
                    instance = replace(
                        instance,
                        failed_step_ids=(
                            *instance.failed_step_ids,
                            next_step.step_id,
                        ),
                        updated_at=_utc_timestamp(),
                    )
                    self._execution_store.save(instance)

                    failed_result = self._state_machine.fail(
                        instance,
                        reason=(
                            f"Workflow step "
                            f"{next_step.step_id!r} failed."
                        ),
                        actor_id=active_context.actor_id,
                    )
                    instance = failed_result.instance
                    self._execution_store.save(instance)

                    return WorkflowExecutionResult(
                        instance=instance,
                        outcome=ExecutionOutcome.FAILED,
                        step_records=tuple(records),
                        started_at=started_at,
                        message=(
                            f"Workflow failed at step "
                            f"{next_step.step_id!r}."
                        ),
                    )

                updated_data = self._merge_step_output(
                    instance.data,
                    next_step.step_id,
                    record.output,
                )

                instance = replace(
                    instance,
                    completed_step_ids=(
                        *instance.completed_step_ids,
                        next_step.step_id,
                    ),
                    data=updated_data,
                    updated_at=_utc_timestamp(),
                )
                self._execution_store.save(instance)

    @staticmethod
    def _find_next_ready_step(
        definition: WorkflowDefinition,
        statuses: dict[str, StepStatus],
    ):
        """Return the next dependency-ready step."""

        successful_states = {
            StepStatus.SUCCEEDED,
            StepStatus.SKIPPED,
        }

        for step in definition.steps:
            current_status = statuses.get(
                step.step_id,
                StepStatus.PENDING,
            )

            if current_status is not StepStatus.PENDING:
                continue

            dependencies_satisfied = all(
                statuses.get(dependency)
                in successful_states
                for dependency in step.dependencies
            )

            if dependencies_satisfied:
                return step

        return None

    @staticmethod
    def _all_steps_successful(
        statuses: dict[str, StepStatus],
    ) -> bool:
        """Return whether every step completed successfully."""

        if not statuses:
            return False

        return all(
            status in {
                StepStatus.SUCCEEDED,
                StepStatus.SKIPPED,
            }
            for status in statuses.values()
        )

    @staticmethod
    def _merge_step_output(
        workflow_data: dict[str, Any],
        step_id: str,
        output: Any,
    ) -> dict[str, Any]:
        """Store step output without mutating original data."""

        existing_outputs = workflow_data.get(
            "step_outputs",
            {},
        )

        if not isinstance(existing_outputs, dict):
            raise WorkflowIntegrityError(
                technical_message=(
                    "Workflow step output storage is corrupted."
                ),
                metadata={
                    "step_id": step_id,
                },
            )

        return {
            **workflow_data,
            "step_outputs": {
                **existing_outputs,
                step_id: output,
            },
        }


_default_execution_engine = WorkflowExecutionEngine()


def get_workflow_execution_engine() -> WorkflowExecutionEngine:
    """Return the shared workflow execution engine."""

    return _default_execution_engine