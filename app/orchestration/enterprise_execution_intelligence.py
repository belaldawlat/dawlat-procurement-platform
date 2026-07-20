"""Enterprise execution intelligence service."""

from __future__ import annotations

from dataclasses import replace

from app.orchestration.enterprise_execution_checkpoint import (
    EnterpriseExecutionCheckpointStore,
)
from app.orchestration.enterprise_execution_coordinator import (
    EnterpriseExecutionCoordinator,
)
from app.orchestration.enterprise_execution_event_bridge import (
    EnterpriseExecutionEventBridge,
)
from app.orchestration.enterprise_execution_models import (
    EnterpriseExecution,
    EnterpriseExecutionSideEffect,
    EnterpriseExecutionStatus,
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
)
from app.orchestration.enterprise_execution_store import (
    EnterpriseExecutionStore,
)
from app.orchestration.enterprise_execution_telemetry import (
    EnterpriseExecutionTelemetry,
)


class EnterpriseExecutionIntelligence:
    """Validate, coordinate, persist and publish enterprise execution."""

    def __init__(
        self,
        *,
        policy: EnterpriseExecutionPolicy | None = None,
        registry: EnterpriseExecutionRegistry | None = None,
        store: EnterpriseExecutionStore | None = None,
        checkpoint_store: EnterpriseExecutionCheckpointStore | None = None,
        telemetry: EnterpriseExecutionTelemetry | None = None,
        recovery: EnterpriseExecutionRecovery | None = None,
        event_bridge: EnterpriseExecutionEventBridge | None = None,
        coordinator: EnterpriseExecutionCoordinator | None = None,
    ) -> None:
        self._policy = policy or EnterpriseExecutionPolicy(
            policy_id="default-enterprise-execution-intelligence",
            name="Default Enterprise Execution Intelligence Policy",
        )
        self._registry = registry or EnterpriseExecutionRegistry()
        self._store = store or EnterpriseExecutionStore()
        self._checkpoint_store = (
            checkpoint_store
            or EnterpriseExecutionCheckpointStore()
        )
        self._telemetry = telemetry or EnterpriseExecutionTelemetry()
        self._recovery = recovery or EnterpriseExecutionRecovery()
        self._event_bridge = (
            event_bridge or EnterpriseExecutionEventBridge()
        )
        self._coordinator = coordinator or EnterpriseExecutionCoordinator(
            registry=self._registry,
            checkpoint_store=self._checkpoint_store,
            telemetry=self._telemetry,
            recovery=self._recovery,
            policy=self._policy,
        )

    @property
    def policy(self) -> EnterpriseExecutionPolicy:
        return self._policy

    @property
    def registry(self) -> EnterpriseExecutionRegistry:
        return self._registry

    @property
    def store(self) -> EnterpriseExecutionStore:
        return self._store

    @property
    def checkpoint_store(
        self,
    ) -> EnterpriseExecutionCheckpointStore:
        return self._checkpoint_store

    @property
    def telemetry(self) -> EnterpriseExecutionTelemetry:
        return self._telemetry

    @property
    def event_bridge(self) -> EnterpriseExecutionEventBridge:
        return self._event_bridge

    def execute(
        self,
        execution: EnterpriseExecution,
        *,
        approved_step_ids: tuple[str, ...] = (),
        persist: bool = True,
    ) -> EnterpriseExecutionResult:
        """Execute one validated enterprise execution."""

        if not isinstance(execution, EnterpriseExecution):
            raise TypeError(
                "Execution intelligence requires an EnterpriseExecution."
            )

        if not self._policy.enabled:
            raise ValueError(
                "Enterprise execution policy is disabled."
            )

        validation_issues = self._validate(
            execution,
            approved_step_ids=set(approved_step_ids),
        )

        if any(issue.blocking for issue in validation_issues):
            failed_execution = replace(
                execution,
                status=EnterpriseExecutionStatus.FAILED,
            )
            result = EnterpriseExecutionResult(
                execution=failed_execution,
                successful=False,
                completed_steps=(),
                failed_steps=(),
                blocked_steps=execution.steps,
                issues=tuple(validation_issues),
                policy_id=self._policy.policy_id,
                policy_version=self._policy.version,
                metadata={"validation_failed": True},
            )

            if persist:
                self._store.create(failed_execution)

            if self._policy.emit_events:
                self._event_bridge.publish(
                    execution.execution_id,
                    "execution.validation_failed",
                    result.as_dict(),
                )

            return result

        running_execution = replace(
            execution,
            status=EnterpriseExecutionStatus.RUNNING,
        )

        if self._policy.emit_events:
            self._event_bridge.publish(
                execution.execution_id,
                "execution.started",
                {
                    "case_id": execution.case_id,
                    "decision_id": execution.decision_id,
                    "plan_id": execution.plan_id,
                },
            )

        result = self._coordinator.execute(
            running_execution
        )

        if persist:
            self._store.create(result.execution)

        if self._policy.emit_events:
            self._event_bridge.publish(
                execution.execution_id,
                (
                    "execution.completed"
                    if result.successful
                    else "execution.failed"
                ),
                {
                    "successful": result.successful,
                    "completed_step_count": len(
                        result.completed_steps
                    ),
                    "failed_step_count": len(
                        result.failed_steps
                    ),
                    "blocked_step_count": len(
                        result.blocked_steps
                    ),
                },
            )

        return result

    def get_execution(
        self,
        execution_id: str,
    ) -> EnterpriseExecution:
        """Return one persisted execution."""

        return self._store.get(execution_id)

    def _validate(
        self,
        execution: EnterpriseExecution,
        *,
        approved_step_ids: set[str],
    ) -> tuple[EnterpriseExecutionIssue, ...]:
        issues: list[EnterpriseExecutionIssue] = []

        if len(execution.steps) > self._policy.maximum_execution_steps:
            issues.append(
                EnterpriseExecutionIssue(
                    code="MAXIMUM_EXECUTION_STEPS_EXCEEDED",
                    message=(
                        "Execution exceeds the maximum permitted "
                        "number of steps."
                    ),
                    severity=EnterpriseExecutionIssueSeverity.CRITICAL,
                    blocking=True,
                    entity_id=execution.execution_id,
                )
            )

        cycle_ids = self._find_cycle_ids(execution)

        if cycle_ids:
            issues.append(
                EnterpriseExecutionIssue(
                    code="EXECUTION_DEPENDENCY_CYCLE",
                    message=(
                        "Execution contains a dependency cycle."
                    ),
                    severity=EnterpriseExecutionIssueSeverity.CRITICAL,
                    blocking=True,
                    entity_id=execution.execution_id,
                    metadata={"cycle_step_ids": list(cycle_ids)},
                )
            )

        depth = self._dependency_depth(execution)

        if depth > self._policy.maximum_dependency_depth:
            issues.append(
                EnterpriseExecutionIssue(
                    code="MAXIMUM_EXECUTION_DEPTH_EXCEEDED",
                    message=(
                        "Execution dependency depth exceeds policy."
                    ),
                    severity=EnterpriseExecutionIssueSeverity.ERROR,
                    blocking=True,
                    entity_id=execution.execution_id,
                    metadata={"dependency_depth": depth},
                )
            )

        for step in execution.steps:
            if (
                step.maximum_attempts
                > self._policy.maximum_step_attempts
            ):
                issues.append(
                    EnterpriseExecutionIssue(
                        code="STEP_ATTEMPT_LIMIT_EXCEEDED",
                        message=(
                            f"Step {step.step_id!r} exceeds the "
                            "configured attempt limit."
                        ),
                        severity=EnterpriseExecutionIssueSeverity.ERROR,
                        blocking=True,
                        entity_id=step.step_id,
                    )
                )

            if (
                step.timeout_seconds
                > self._policy.maximum_step_timeout_seconds
            ):
                issues.append(
                    EnterpriseExecutionIssue(
                        code="STEP_TIMEOUT_LIMIT_EXCEEDED",
                        message=(
                            f"Step {step.step_id!r} exceeds the "
                            "configured timeout limit."
                        ),
                        severity=EnterpriseExecutionIssueSeverity.ERROR,
                        blocking=True,
                        entity_id=step.step_id,
                    )
                )

            requires_approval = (
                step.requires_human_approval
                or (
                    step.side_effect
                    is EnterpriseExecutionSideEffect.FINANCIAL
                    and self._policy
                    .require_human_approval_for_financial_side_effects
                )
                or (
                    step.side_effect
                    in {
                        EnterpriseExecutionSideEffect.EXTERNAL,
                        EnterpriseExecutionSideEffect.LEGAL,
                        EnterpriseExecutionSideEffect.LOGISTICS,
                    }
                    and self._policy.pause_on_external_side_effect
                )
            )

            if (
                requires_approval
                and step.step_id not in approved_step_ids
            ):
                issues.append(
                    EnterpriseExecutionIssue(
                        code="STEP_APPROVAL_REQUIRED",
                        message=(
                            f"Step {step.step_id!r} requires "
                            "human approval."
                        ),
                        severity=EnterpriseExecutionIssueSeverity.WARNING,
                        blocking=True,
                        entity_id=step.step_id,
                    )
                )

        return tuple(issues)

    @staticmethod
    def _find_cycle_ids(
        execution: EnterpriseExecution,
    ) -> tuple[str, ...]:
        indegree = {
            step.step_id: 0
            for step in execution.steps
        }
        children: dict[str, list[str]] = {
            step.step_id: []
            for step in execution.steps
        }

        for step in execution.steps:
            for dependency_id in step.depends_on:
                indegree[step.step_id] += 1
                children[dependency_id].append(step.step_id)

        queue = sorted(
            step_id
            for step_id, value in indegree.items()
            if value == 0
        )
        processed = 0

        while queue:
            current = queue.pop(0)
            processed += 1

            for child_id in sorted(children[current]):
                indegree[child_id] -= 1

                if indegree[child_id] == 0:
                    queue.append(child_id)
                    queue.sort()

        if processed == len(execution.steps):
            return ()

        return tuple(
            sorted(
                step_id
                for step_id, value in indegree.items()
                if value > 0
            )
        )

    @staticmethod
    def _dependency_depth(
        execution: EnterpriseExecution,
    ) -> int:
        if EnterpriseExecutionIntelligence._find_cycle_ids(
            execution
        ):
            return len(execution.steps)

        depth: dict[str, int] = {}
        remaining = {
            step.step_id: step
            for step in execution.steps
        }

        while remaining:
            progress = False

            for step_id, step in list(remaining.items()):
                if all(
                    dependency_id in depth
                    for dependency_id in step.depends_on
                ):
                    depth[step_id] = (
                        0
                        if not step.depends_on
                        else 1 + max(
                            depth[item]
                            for item in step.depends_on
                        )
                    )
                    del remaining[step_id]
                    progress = True

            if not progress:
                break

        return max(depth.values(), default=0)


_default_enterprise_execution_intelligence = (
    EnterpriseExecutionIntelligence()
)


def get_enterprise_execution_intelligence(
) -> EnterpriseExecutionIntelligence:
    """Return the process-local execution intelligence service."""

    return _default_enterprise_execution_intelligence