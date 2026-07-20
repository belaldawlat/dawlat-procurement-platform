"""Execution coordinator for enterprise execution intelligence."""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter
from typing import Any

from app.orchestration.enterprise_execution_checkpoint import (
    EnterpriseExecutionCheckpointStore,
)
from app.orchestration.enterprise_execution_models import (
    EnterpriseExecution,
    EnterpriseExecutionStatus,
    EnterpriseExecutionStep,
    EnterpriseExecutionStepStatus,
)
from app.orchestration.enterprise_execution_policy import (
    EnterpriseExecutionPolicy,
)
from app.orchestration.enterprise_execution_recovery import (
    EnterpriseExecutionRecovery,
)
from app.orchestration.enterprise_execution_registry import (
    EnterpriseExecutionRegistry,
)
from app.orchestration.enterprise_execution_result import (
    EnterpriseExecutionIssue,
    EnterpriseExecutionIssueSeverity,
    EnterpriseExecutionResult,
    EnterpriseExecutionStepResult,
)
from app.orchestration.enterprise_execution_telemetry import (
    EnterpriseExecutionTelemetry,
)


class EnterpriseExecutionCoordinator:
    """Coordinate dependency-aware and policy-governed execution."""

    def __init__(
        self,
        *,
        registry: EnterpriseExecutionRegistry,
        checkpoint_store: EnterpriseExecutionCheckpointStore,
        telemetry: EnterpriseExecutionTelemetry,
        recovery: EnterpriseExecutionRecovery,
        policy: EnterpriseExecutionPolicy,
    ) -> None:
        self._registry = registry
        self._checkpoint_store = checkpoint_store
        self._telemetry = telemetry
        self._recovery = recovery
        self._policy = policy

    def execute(
        self,
        execution: EnterpriseExecution,
    ) -> EnterpriseExecutionResult:
        """Execute all currently valid steps in deterministic order."""

        started = perf_counter()
        completed_results: list[EnterpriseExecutionStepResult] = []
        failed_results: list[EnterpriseExecutionStepResult] = []
        blocked_steps: list[EnterpriseExecutionStep] = []
        issues: list[EnterpriseExecutionIssue] = []

        step_map = {
            step.step_id: step
            for step in execution.steps
        }
        completed_step_ids: set[str] = {
            step.step_id
            for step in execution.steps
            if step.status is EnterpriseExecutionStepStatus.SUCCEEDED
        }

        pending = [
            step
            for step in execution.steps
            if not step.is_terminal
        ]

        ordered = sorted(
            pending,
            key=lambda step: (
                -self._priority_rank(step.priority.value),
                step.step_id,
            ),
        )

        progress_made = True

        while ordered and progress_made:
            progress_made = False
            remaining: list[EnterpriseExecutionStep] = []

            for step in ordered:
                if not set(step.depends_on).issubset(
                    completed_step_ids
                ):
                    remaining.append(step)
                    continue

                progress_made = True
                result = self._execute_step(
                    execution=execution,
                    step=step,
                )

                if result.successful:
                    completed_results.append(result)
                    completed_step_ids.add(step.step_id)
                else:
                    failed_results.append(result)

                    if (
                        result.step.status
                        is EnterpriseExecutionStepStatus.BLOCKED
                    ):
                        blocked_steps.append(result.step)

                    issues.append(
                        EnterpriseExecutionIssue(
                            code="EXECUTION_STEP_FAILED",
                            message=(
                                f"Execution step {step.step_id!r} failed."
                            ),
                            severity=(
                                EnterpriseExecutionIssueSeverity.ERROR
                            ),
                            blocking=True,
                            entity_id=step.step_id,
                            metadata={"error": result.error},
                        )
                    )

            ordered = remaining

        for step in ordered:
            blocked = replace(
                step,
                status=EnterpriseExecutionStepStatus.BLOCKED,
            )
            blocked_steps.append(blocked)
            issues.append(
                EnterpriseExecutionIssue(
                    code="UNRESOLVED_STEP_DEPENDENCIES",
                    message=(
                        f"Execution step {step.step_id!r} could not run "
                        "because dependencies were not completed."
                    ),
                    severity=EnterpriseExecutionIssueSeverity.ERROR,
                    blocking=True,
                    entity_id=step.step_id,
                    metadata={
                        "depends_on": list(step.depends_on),
                    },
                )
            )

        successful = (
            not failed_results
            and not blocked_steps
            and not any(issue.blocking for issue in issues)
        )

        final_status = (
            EnterpriseExecutionStatus.COMPLETED
            if successful
            else EnterpriseExecutionStatus.FAILED
        )
        updated_steps = self._merge_step_states(
            original_steps=execution.steps,
            completed_results=tuple(completed_results),
            failed_results=tuple(failed_results),
            blocked_steps=tuple(blocked_steps),
        )
        updated_execution = replace(
            execution,
            status=final_status,
            steps=updated_steps,
        )

        duration_ms = round(
            (perf_counter() - started) * 1000.0,
            3,
        )

        if self._policy.telemetry_enabled:
            self._telemetry.record(
                execution_id=execution.execution_id,
                metric_name="execution_duration_ms",
                metric_value=duration_ms,
                unit="ms",
                metadata={
                    "successful": successful,
                    "completed_step_count": len(completed_results),
                    "failed_step_count": len(failed_results),
                    "blocked_step_count": len(blocked_steps),
                },
            )

        return EnterpriseExecutionResult(
            execution=updated_execution,
            successful=successful,
            completed_steps=tuple(completed_results),
            failed_steps=tuple(failed_results),
            blocked_steps=tuple(blocked_steps),
            issues=tuple(issues),
            duration_ms=duration_ms,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "completed_step_count": len(completed_results),
                "failed_step_count": len(failed_results),
                "blocked_step_count": len(blocked_steps),
            },
        )

    def _execute_step(
        self,
        *,
        execution: EnterpriseExecution,
        step: EnterpriseExecutionStep,
    ) -> EnterpriseExecutionStepResult:
        started = perf_counter()
        running_step = replace(
            step,
            status=EnterpriseExecutionStepStatus.RUNNING,
            attempts=step.attempts + 1,
        )

        try:
            handler = self._registry.get(running_step.handler_id)
            output = handler(running_step.payload)

            if not isinstance(output, dict):
                raise TypeError(
                    "Enterprise execution handlers must return a dictionary."
                )

            completed_step = replace(
                running_step,
                status=EnterpriseExecutionStepStatus.SUCCEEDED,
            )
            checkpoint_id = ""

            if self._policy.checkpoint_after_each_step:
                checkpoint = self._checkpoint_store.create(
                    execution,
                    completed_step,
                    metadata={"successful": True},
                )
                checkpoint_id = checkpoint.checkpoint_id

            duration_ms = round(
                (perf_counter() - started) * 1000.0,
                3,
            )
            telemetry_id = ""

            if self._policy.telemetry_enabled:
                telemetry = self._telemetry.record(
                    execution_id=execution.execution_id,
                    step_id=step.step_id,
                    metric_name="step_duration_ms",
                    metric_value=duration_ms,
                    unit="ms",
                    metadata={"successful": True},
                )
                telemetry_id = telemetry.telemetry_id

            return EnterpriseExecutionStepResult(
                step=completed_step,
                successful=True,
                output=output,
                duration_ms=duration_ms,
                checkpoint_id=checkpoint_id,
                telemetry_id=telemetry_id,
            )

        except Exception as exc:
            failed_step = replace(
                running_step,
                status=EnterpriseExecutionStepStatus.FAILED,
            )

            recovery_result = self._recovery.recover(
                step=failed_step,
                policy=self._policy,
                retry_handler=self._build_retry_handler(failed_step),
                compensation_handler=self._build_compensation_handler(
                    failed_step
                ),
            )
            terminal_status = self._recovery.terminal_status(
                recovery_result
            )
            terminal_step = replace(
                failed_step,
                status=terminal_status,
            )
            successful = terminal_status in {
                EnterpriseExecutionStepStatus.SUCCEEDED,
                EnterpriseExecutionStepStatus.COMPENSATED,
            }

            duration_ms = round(
                (perf_counter() - started) * 1000.0,
                3,
            )
            telemetry_id = ""

            if self._policy.telemetry_enabled:
                telemetry = self._telemetry.record(
                    execution_id=execution.execution_id,
                    step_id=step.step_id,
                    metric_name="step_duration_ms",
                    metric_value=duration_ms,
                    unit="ms",
                    metadata={
                        "successful": successful,
                        "recovered": recovery_result.recovered,
                        "compensated": recovery_result.compensated,
                    },
                )
                telemetry_id = telemetry.telemetry_id

            return EnterpriseExecutionStepResult(
                step=terminal_step,
                successful=successful,
                output=recovery_result.output,
                error=(
                    recovery_result.error
                    or str(exc)
                ),
                duration_ms=duration_ms,
                telemetry_id=telemetry_id,
                metadata={
                    "recovered": recovery_result.recovered,
                    "compensated": recovery_result.compensated,
                    "retry_allowed": recovery_result.retry_allowed,
                },
            )

    def _build_retry_handler(
        self,
        step: EnterpriseExecutionStep,
    ):
        if not self._policy.recover_failed_steps:
            return None

        def retry_handler(
            failed_step: EnterpriseExecutionStep,
        ) -> dict[str, Any]:
            handler = self._registry.get(
                failed_step.handler_id
            )
            return handler(failed_step.payload)

        return retry_handler

    def _build_compensation_handler(
        self,
        step: EnterpriseExecutionStep,
    ):
        if not step.compensation_handler_id:
            return None

        def compensation_handler(
            failed_step: EnterpriseExecutionStep,
        ) -> dict[str, Any]:
            handler = self._registry.get(
                failed_step.compensation_handler_id
            )
            return handler(failed_step.payload)

        return compensation_handler

    @staticmethod
    def _priority_rank(priority_value: str) -> int:
        return {
            "critical": 4,
            "high": 3,
            "normal": 2,
            "low": 1,
        }[priority_value]

    @staticmethod
    def _merge_step_states(
        *,
        original_steps: tuple[EnterpriseExecutionStep, ...],
        completed_results: tuple[EnterpriseExecutionStepResult, ...],
        failed_results: tuple[EnterpriseExecutionStepResult, ...],
        blocked_steps: tuple[EnterpriseExecutionStep, ...],
    ) -> tuple[EnterpriseExecutionStep, ...]:
        replacements = {
            item.step.step_id: item.step
            for item in completed_results + failed_results
        }
        replacements.update(
            {
                item.step_id: item
                for item in blocked_steps
            }
        )

        return tuple(
            replacements.get(step.step_id, step)
            for step in original_steps
        )