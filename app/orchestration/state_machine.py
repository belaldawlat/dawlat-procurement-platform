"""Enterprise state machine for workflows and workflow steps."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime, timezone

from app.observability.logging_config import get_logger
from app.orchestration.exceptions import (
    WorkflowStateError,
)
from app.orchestration.transition_policy import (
    TransitionPolicy,
    get_default_transition_policy,
)
from app.orchestration.transition_result import (
    StepTransitionResult,
    WorkflowTransitionResult,
)
from app.orchestration.workflow_models import (
    StepStatus,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowTransition,
)


def _utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class WorkflowStateMachine:
    """Apply deterministic workflow and step transitions."""

    def __init__(
        self,
        policy: TransitionPolicy | None = None,
        *,
        raise_on_rejection: bool = True,
    ) -> None:
        self._policy = (
            policy or get_default_transition_policy()
        )
        self._raise_on_rejection = raise_on_rejection
        self._lock = threading.RLock()
        self._logger = get_logger(
            "orchestration.state_machine"
        )

    @property
    def policy(self) -> TransitionPolicy:
        """Return the active transition policy."""

        return self._policy

    @property
    def raise_on_rejection(self) -> bool:
        """Return whether rejected transitions raise errors."""

        return self._raise_on_rejection

    def transition_workflow(
        self,
        instance: WorkflowInstance,
        target_status: WorkflowStatus,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Attempt a workflow-level state transition."""

        if not isinstance(instance, WorkflowInstance):
            raise TypeError(
                "Workflow instance must be a "
                "WorkflowInstance object."
            )

        if not isinstance(target_status, WorkflowStatus):
            raise TypeError(
                "Target workflow status must be "
                "a WorkflowStatus value."
            )

        cleaned_reason = str(reason or "").strip()
        cleaned_actor_id = str(actor_id or "").strip()

        with self._lock:
            violations = (
                self._policy.validate_workflow_transition(
                    instance,
                    target_status,
                )
            )

            if violations:
                result = WorkflowTransitionResult(
                    accepted=False,
                    previous_status=instance.status,
                    requested_status=target_status,
                    instance=instance,
                    reason=cleaned_reason,
                    actor_id=cleaned_actor_id,
                    violations=violations,
                )

                self._log_rejection(result)

                if self._raise_on_rejection:
                    raise WorkflowStateError(
                        technical_message=(
                            f"Workflow transition from "
                            f"{instance.status.value!r} to "
                            f"{target_status.value!r} "
                            "was rejected."
                        ),
                        metadata={
                            "workflow_id": instance.workflow_id,
                            "workflow_version": (
                                instance.workflow_version
                            ),
                            "instance_id": instance.instance_id,
                            "current_status": (
                                instance.status.value
                            ),
                            "requested_status": (
                                target_status.value
                            ),
                            "violations": [
                                violation.as_dict()
                                for violation in violations
                            ],
                        },
                    )

                return result

            if instance.status is target_status:
                return WorkflowTransitionResult(
                    accepted=True,
                    previous_status=instance.status,
                    requested_status=target_status,
                    instance=instance,
                    reason=cleaned_reason,
                    actor_id=cleaned_actor_id,
                )

            occurred_at = _utc_timestamp()

            transition = WorkflowTransition(
                from_status=instance.status,
                to_status=target_status,
                reason=cleaned_reason,
                actor_id=cleaned_actor_id,
                occurred_at=occurred_at,
            )

            updated_instance = replace(
                instance,
                status=target_status,
                transitions=(
                    *instance.transitions,
                    transition,
                ),
                updated_at=occurred_at,
            )

            result = WorkflowTransitionResult(
                accepted=True,
                previous_status=instance.status,
                requested_status=target_status,
                instance=updated_instance,
                reason=cleaned_reason,
                actor_id=cleaned_actor_id,
                occurred_at=occurred_at,
            )

            self._log_acceptance(result)
            return result

    def transition_step(
        self,
        current_status: StepStatus,
        target_status: StepStatus,
        *,
        step_id: str,
        reason: str = "",
        actor_id: str = "",
    ) -> StepTransitionResult:
        """Attempt a workflow-step state transition."""

        if not isinstance(current_status, StepStatus):
            raise TypeError(
                "Current step status must be a StepStatus value."
            )

        if not isinstance(target_status, StepStatus):
            raise TypeError(
                "Target step status must be a StepStatus value."
            )

        cleaned_step_id = str(step_id or "").strip()
        cleaned_reason = str(reason or "").strip()
        cleaned_actor_id = str(actor_id or "").strip()

        with self._lock:
            violations = self._policy.validate_step_transition(
                current_status,
                target_status,
                step_id=cleaned_step_id,
            )

            result = StepTransitionResult(
                accepted=not violations,
                step_id=cleaned_step_id,
                previous_status=current_status,
                requested_status=target_status,
                reason=cleaned_reason,
                actor_id=cleaned_actor_id,
                violations=violations,
            )

            if violations:
                self._logger.warning(
                    "Workflow step transition rejected.",
                    extra={
                        "step_id": cleaned_step_id,
                        "current_status": (
                            current_status.value
                        ),
                        "requested_status": (
                            target_status.value
                        ),
                        "violations": [
                            violation.as_dict()
                            for violation in violations
                        ],
                    },
                )

                if self._raise_on_rejection:
                    raise WorkflowStateError(
                        technical_message=(
                            f"Step transition from "
                            f"{current_status.value!r} to "
                            f"{target_status.value!r} "
                            "was rejected."
                        ),
                        metadata={
                            "step_id": cleaned_step_id,
                            "current_status": (
                                current_status.value
                            ),
                            "requested_status": (
                                target_status.value
                            ),
                            "violations": [
                                violation.as_dict()
                                for violation in violations
                            ],
                        },
                    )

                return result

            self._logger.info(
                "Workflow step transition accepted.",
                extra={
                    "step_id": cleaned_step_id,
                    "previous_status": (
                        current_status.value
                    ),
                    "new_status": target_status.value,
                    "reason": cleaned_reason,
                    "actor_id": cleaned_actor_id,
                },
            )

            return result

    def prepare(
        self,
        instance: WorkflowInstance,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Move a created workflow into ready state."""

        return self.transition_workflow(
            instance,
            WorkflowStatus.READY,
            reason=reason,
            actor_id=actor_id,
        )

    def start(
        self,
        instance: WorkflowInstance,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Start or resume workflow execution."""

        return self.transition_workflow(
            instance,
            WorkflowStatus.RUNNING,
            reason=reason,
            actor_id=actor_id,
        )

    def wait(
        self,
        instance: WorkflowInstance,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Place a running workflow into waiting state."""

        return self.transition_workflow(
            instance,
            WorkflowStatus.WAITING,
            reason=reason,
            actor_id=actor_id,
        )

    def pause(
        self,
        instance: WorkflowInstance,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Pause an active workflow."""

        return self.transition_workflow(
            instance,
            WorkflowStatus.PAUSED,
            reason=reason,
            actor_id=actor_id,
        )

    def complete(
        self,
        instance: WorkflowInstance,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Complete a running workflow."""

        return self.transition_workflow(
            instance,
            WorkflowStatus.COMPLETED,
            reason=reason,
            actor_id=actor_id,
        )

    def fail(
        self,
        instance: WorkflowInstance,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Fail an active workflow."""

        return self.transition_workflow(
            instance,
            WorkflowStatus.FAILED,
            reason=reason,
            actor_id=actor_id,
        )

    def cancel(
        self,
        instance: WorkflowInstance,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Cancel a non-terminal workflow."""

        return self.transition_workflow(
            instance,
            WorkflowStatus.CANCELLED,
            reason=reason,
            actor_id=actor_id,
        )

    def begin_compensation(
        self,
        instance: WorkflowInstance,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Start compensation after a workflow failure."""

        return self.transition_workflow(
            instance,
            WorkflowStatus.COMPENSATING,
            reason=reason,
            actor_id=actor_id,
        )

    def finish_compensation(
        self,
        instance: WorkflowInstance,
        *,
        reason: str = "",
        actor_id: str = "",
    ) -> WorkflowTransitionResult:
        """Complete workflow compensation."""

        return self.transition_workflow(
            instance,
            WorkflowStatus.COMPENSATED,
            reason=reason,
            actor_id=actor_id,
        )

    def can_transition_workflow(
        self,
        instance: WorkflowInstance,
        target_status: WorkflowStatus,
    ) -> bool:
        """Return whether a workflow transition is permitted."""

        return not self._policy.validate_workflow_transition(
            instance,
            target_status,
        )

    def can_transition_step(
        self,
        current_status: StepStatus,
        target_status: StepStatus,
        *,
        step_id: str,
    ) -> bool:
        """Return whether a step transition is permitted."""

        return not self._policy.validate_step_transition(
            current_status,
            target_status,
            step_id=step_id,
        )

    def _log_acceptance(
        self,
        result: WorkflowTransitionResult,
    ) -> None:
        """Log an accepted workflow transition."""

        self._logger.info(
            "Workflow transition accepted.",
            extra={
                "workflow_id": result.instance.workflow_id,
                "workflow_version": (
                    result.instance.workflow_version
                ),
                "instance_id": result.instance.instance_id,
                "previous_status": (
                    result.previous_status.value
                ),
                "new_status": (
                    result.requested_status.value
                ),
                "reason": result.reason,
                "actor_id": result.actor_id,
            },
        )

    def _log_rejection(
        self,
        result: WorkflowTransitionResult,
    ) -> None:
        """Log a rejected workflow transition."""

        self._logger.warning(
            "Workflow transition rejected.",
            extra={
                "workflow_id": result.instance.workflow_id,
                "workflow_version": (
                    result.instance.workflow_version
                ),
                "instance_id": result.instance.instance_id,
                "current_status": (
                    result.previous_status.value
                ),
                "requested_status": (
                    result.requested_status.value
                ),
                "violations": [
                    violation.as_dict()
                    for violation in result.violations
                ],
            },
        )


_default_state_machine = WorkflowStateMachine()


def get_workflow_state_machine() -> WorkflowStateMachine:
    """Return the shared workflow state machine."""

    return _default_state_machine