"""Saga-style enterprise workflow compensation engine."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.observability.logging_config import get_logger
from app.orchestration.compensation_models import (
    CompensationFailureStrategy,
    CompensationPlan,
    CompensationStatus,
    CompensationStepDefinition,
    CompensationStepRecord,
    CompensationStepStatus,
)
from app.orchestration.compensation_policy import (
    CompensationPolicy,
    CompensationPolicyViolation,
)
from app.orchestration.compensation_store import InMemoryCompensationStore
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowStateError,
    WorkflowValidationError,
)
from app.orchestration.workflow_context import WorkflowContext
from app.resilience.exceptions import normalise_exception
from app.resilience.retry_policy import RetryExecutor, RetryPolicy


CompensationHandler = Callable[
    [WorkflowContext, dict[str, Any]],
    Any,
]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class CompensationExecutionResult:
    plan: CompensationPlan
    accepted: bool
    violations: tuple[CompensationPolicyViolation, ...] = ()

    @property
    def successful(self) -> bool:
        return (
            self.accepted
            and self.plan.status is CompensationStatus.COMPENSATED
        )

    @property
    def requires_manual_intervention(self) -> bool:
        return (
            self.plan.status
            is CompensationStatus.MANUAL_INTERVENTION_REQUIRED
        )


class CompensationHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, CompensationHandler] = {}
        self._lock = threading.RLock()

    def register(
        self,
        handler_key: str,
        handler: CompensationHandler,
        *,
        replace_existing: bool = False,
    ) -> None:
        cleaned_key = str(handler_key or "").strip()

        if not cleaned_key:
            raise ValueError("Compensation handler key is required.")

        if not callable(handler):
            raise TypeError("Compensation handler must be callable.")

        with self._lock:
            if cleaned_key in self._handlers and not replace_existing:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Compensation handler {cleaned_key!r} already exists."
                    ),
                    metadata={"handler_key": cleaned_key},
                )
            self._handlers[cleaned_key] = handler

    def get(self, handler_key: str) -> CompensationHandler:
        cleaned_key = str(handler_key or "").strip()

        if not cleaned_key:
            raise ValueError("Compensation handler key is required.")

        with self._lock:
            handler = self._handlers.get(cleaned_key)

        if handler is None:
            raise WorkflowIntegrityError(
                technical_message=(
                    f"No compensation handler is registered for "
                    f"{cleaned_key!r}."
                ),
                metadata={"handler_key": cleaned_key},
            )

        return handler

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()


class CompensationEngine:
    def __init__(
        self,
        *,
        store: InMemoryCompensationStore | None = None,
        handler_registry: CompensationHandlerRegistry | None = None,
        raise_on_validation_failure: bool = True,
    ) -> None:
        self._store = store or InMemoryCompensationStore()
        self._handler_registry = (
            handler_registry or CompensationHandlerRegistry()
        )
        self._raise_on_validation_failure = raise_on_validation_failure
        self._logger = get_logger("orchestration.compensation_engine")

    @property
    def store(self) -> InMemoryCompensationStore:
        return self._store

    @property
    def handler_registry(self) -> CompensationHandlerRegistry:
        return self._handler_registry

    def register_policy(
        self,
        policy: CompensationPolicy,
        *,
        replace_existing: bool = False,
    ) -> CompensationPolicy:
        return self._store.register_policy(
            policy,
            replace_existing=replace_existing,
        )

    def create_plan(
        self,
        *,
        policy_id: str,
        workflow_instance_id: str,
        workflow_id: str,
        workflow_version: str,
        steps: tuple[CompensationStepDefinition, ...],
        metadata: dict[str, Any] | None = None,
    ) -> CompensationPlan:
        policy = self._store.get_policy(policy_id)

        plan = CompensationPlan(
            workflow_instance_id=workflow_instance_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            steps=steps,
            metadata={**(metadata or {}), "policy_id": policy_id},
        )

        violations = policy.validate_plan(plan)

        if violations:
            raise WorkflowValidationError(
                technical_message=(
                    "Compensation plan failed policy validation."
                ),
                metadata={
                    "policy_id": policy_id,
                    "workflow_instance_id": workflow_instance_id,
                    "violations": [
                        {
                            "code": violation.code,
                            "message": violation.message,
                            "step_id": violation.step_id,
                            "field_name": violation.field_name,
                        }
                        for violation in violations
                    ],
                },
            )

        self._store.create_plan(plan)
        return plan

    def execute(
        self,
        plan_id: str,
        *,
        context: WorkflowContext,
        workflow_data: dict[str, Any] | None = None,
    ) -> CompensationExecutionResult:
        if not isinstance(context, WorkflowContext):
            raise TypeError(
                "Compensation context must be a WorkflowContext."
            )

        plan = self._store.get_plan(plan_id)

        if plan.is_terminal:
            if plan.status is CompensationStatus.COMPENSATED:
                return CompensationExecutionResult(
                    plan=plan,
                    accepted=True,
                )

            raise WorkflowStateError(
                technical_message=(
                    "A terminal compensation plan cannot execute again."
                ),
                metadata={
                    "plan_id": plan.plan_id,
                    "status": plan.status.value,
                },
            )

        policy_id = str(plan.metadata.get("policy_id", "")).strip()
        policy = self._store.get_policy(policy_id)
        violations = policy.validate_plan(plan)

        if violations:
            result = CompensationExecutionResult(
                plan=plan,
                accepted=False,
                violations=violations,
            )

            if self._raise_on_validation_failure:
                raise WorkflowValidationError(
                    technical_message=(
                        "Compensation plan failed execution validation."
                    )
                )

            return result

        plan = plan.with_status(CompensationStatus.RUNNING)
        self._store.save_plan(plan)
        data = dict(workflow_data or {})

        for step in policy.order_steps(plan.steps):
            if (
                step.step_id in plan.completed_step_ids
                and not policy.allow_reexecution_of_successful_steps
            ):
                continue

            plan = plan.with_status(
                CompensationStatus.RUNNING,
                current_step_id=step.step_id,
            )
            self._store.save_plan(plan)

            record = self._execute_step(
                step,
                context=context,
                workflow_data=data,
            )

            if record.successful:
                self._store.save_idempotency_result(
                    step.idempotency_key,
                    record.output,
                )
                plan = plan.append_record(
                    record,
                    status=CompensationStatus.RUNNING,
                    current_step_id="",
                )
                self._store.save_plan(plan)
                continue

            next_status = self._resolve_failure_status(step)
            plan = plan.append_record(
                record,
                status=next_status,
                current_step_id="",
            )
            self._store.save_plan(plan)

            if (
                step.failure_strategy
                is CompensationFailureStrategy.CONTINUE
            ):
                plan = plan.with_status(
                    CompensationStatus.PARTIALLY_COMPENSATED
                )
                self._store.save_plan(plan)
                continue

            return CompensationExecutionResult(
                plan=plan,
                accepted=True,
            )

        final_status = (
            CompensationStatus.COMPENSATED
            if not plan.failed_step_ids
            else CompensationStatus.PARTIALLY_COMPENSATED
        )

        plan = plan.with_status(final_status)
        self._store.save_plan(plan)

        return CompensationExecutionResult(
            plan=plan,
            accepted=True,
        )

    def cancel(
        self,
        plan_id: str,
        *,
        actor_id: str,
        reason: str = "",
    ) -> CompensationPlan:
        plan = self._store.get_plan(plan_id)

        if plan.is_terminal:
            raise WorkflowStateError(
                technical_message=(
                    "A terminal compensation plan cannot be cancelled."
                ),
                metadata={
                    "plan_id": plan.plan_id,
                    "status": plan.status.value,
                },
            )

        cancelled = plan.with_status(CompensationStatus.CANCELLED)
        self._store.save_plan(cancelled)

        self._logger.warning(
            "Compensation plan cancelled.",
            extra={
                "plan_id": cancelled.plan_id,
                "actor_id": str(actor_id or "").strip(),
                "reason": str(reason or "").strip(),
            },
        )

        return cancelled

    def _execute_step(
        self,
        step: CompensationStepDefinition,
        *,
        context: WorkflowContext,
        workflow_data: dict[str, Any],
    ) -> CompensationStepRecord:
        started_at = _utc_timestamp()

        if self._store.has_idempotency_result(
            step.idempotency_key
        ):
            output = self._store.get_idempotency_result(
                step.idempotency_key
            )
            return CompensationStepRecord(
                step_id=step.step_id,
                original_step_id=step.original_step_id,
                status=CompensationStepStatus.SUCCEEDED,
                attempt_count=0,
                started_at=started_at,
                completed_at=_utc_timestamp(),
                output=output,
                metadata={"idempotent_replay": True},
            )

        handler = self._handler_registry.get(step.handler_key)

        try:
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
                    context.for_step(step.step_id),
                    dict(workflow_data),
                ),
                operation_name=step.step_id,
            )

            return CompensationStepRecord(
                step_id=step.step_id,
                original_step_id=step.original_step_id,
                status=CompensationStepStatus.SUCCEEDED,
                attempt_count=len(retry_result.attempts),
                started_at=started_at,
                completed_at=_utc_timestamp(),
                output=retry_result.value,
            )

        except Exception as error:
            normalised = normalise_exception(error)
            attempt_count = (
                step.maximum_attempts
                if normalised.code == "DAWLAT_RETRY_EXHAUSTED"
                else 1
            )

            return CompensationStepRecord(
                step_id=step.step_id,
                original_step_id=step.original_step_id,
                status=CompensationStepStatus.FAILED,
                attempt_count=attempt_count,
                started_at=started_at,
                completed_at=_utc_timestamp(),
                error_code=normalised.code,
                error_id=normalised.error_id,
                safe_error_message=normalised.safe_message,
            )

    @staticmethod
    def _resolve_failure_status(
        step: CompensationStepDefinition,
    ) -> CompensationStatus:
        if (
            step.failure_strategy
            is CompensationFailureStrategy.REQUIRE_MANUAL_INTERVENTION
        ):
            return CompensationStatus.MANUAL_INTERVENTION_REQUIRED

        if (
            step.failure_strategy
            is CompensationFailureStrategy.CONTINUE
        ):
            return CompensationStatus.PARTIALLY_COMPENSATED

        return CompensationStatus.FAILED


_default_compensation_engine = CompensationEngine()


def get_compensation_engine() -> CompensationEngine:
    return _default_compensation_engine