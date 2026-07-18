"""Deterministic policies governing workflow state transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.observability.redaction import redact_mapping
from app.orchestration.transition_result import (
    TransitionViolation,
)
from app.orchestration.workflow_models import (
    StepStatus,
    WorkflowInstance,
    WorkflowStatus,
)


WorkflowGuard = Callable[
    [WorkflowInstance, WorkflowStatus],
    bool,
]


@dataclass(frozen=True)
class TransitionGuard:
    """Named guard that may approve or reject a transition."""

    name: str
    predicate: WorkflowGuard
    failure_code: str = "TRANSITION_GUARD_REJECTED"
    failure_message: str = (
        "A workflow transition guard rejected the request."
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate guard configuration."""

        cleaned_name = str(self.name or "").strip()

        if not cleaned_name:
            raise ValueError("Transition guard name is required.")

        if not callable(self.predicate):
            raise TypeError(
                "Transition guard predicate must be callable."
            )

        object.__setattr__(self, "name", cleaned_name)
        object.__setattr__(
            self,
            "failure_code",
            str(self.failure_code or "").strip()
            or "TRANSITION_GUARD_REJECTED",
        )
        object.__setattr__(
            self,
            "failure_message",
            str(self.failure_message or "").strip()
            or (
                "A workflow transition guard rejected "
                "the request."
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def evaluate(
        self,
        instance: WorkflowInstance,
        target_status: WorkflowStatus,
    ) -> TransitionViolation | None:
        """Return a violation when the guard rejects a transition."""

        try:
            accepted = bool(
                self.predicate(
                    instance,
                    target_status,
                )
            )
        except Exception as error:
            return TransitionViolation(
                code="TRANSITION_GUARD_ERROR",
                message=(
                    f"Transition guard {self.name!r} failed "
                    "during evaluation."
                ),
                current_state=instance.status.value,
                requested_state=target_status.value,
                metadata={
                    "guard_name": self.name,
                    "guard_error_type": (
                        error.__class__.__name__
                    ),
                },
            )

        if accepted:
            return None

        return TransitionViolation(
            code=self.failure_code,
            message=self.failure_message,
            current_state=instance.status.value,
            requested_state=target_status.value,
            metadata={
                "guard_name": self.name,
                **self.metadata,
            },
        )


@dataclass(frozen=True)
class TransitionPolicy:
    """Immutable workflow and step transition policy."""

    workflow_transitions: dict[
        WorkflowStatus,
        frozenset[WorkflowStatus],
    ]
    step_transitions: dict[
        StepStatus,
        frozenset[StepStatus],
    ]
    workflow_terminal_states: frozenset[WorkflowStatus]
    step_terminal_states: frozenset[StepStatus]
    allow_idempotent_transitions: bool = True
    guards: tuple[TransitionGuard, ...] = ()

    def allowed_workflow_targets(
        self,
        current_status: WorkflowStatus,
    ) -> frozenset[WorkflowStatus]:
        """Return workflow states reachable from the current state."""

        return self.workflow_transitions.get(
            current_status,
            frozenset(),
        )

    def allowed_step_targets(
        self,
        current_status: StepStatus,
    ) -> frozenset[StepStatus]:
        """Return step states reachable from the current state."""

        return self.step_transitions.get(
            current_status,
            frozenset(),
        )

    def is_workflow_terminal(
        self,
        status: WorkflowStatus,
    ) -> bool:
        """Return whether a workflow state is terminal."""

        return status in self.workflow_terminal_states

    def is_step_terminal(
        self,
        status: StepStatus,
    ) -> bool:
        """Return whether a step state is terminal."""

        return status in self.step_terminal_states

    def validate_workflow_transition(
        self,
        instance: WorkflowInstance,
        target_status: WorkflowStatus,
    ) -> tuple[TransitionViolation, ...]:
        """Validate a workflow-level transition."""

        current_status = instance.status
        violations: list[TransitionViolation] = []

        if current_status is target_status:
            if self.allow_idempotent_transitions:
                return ()

            return (
                TransitionViolation(
                    code="IDEMPOTENT_TRANSITION_NOT_ALLOWED",
                    message=(
                        "An identical workflow status transition "
                        "is not permitted."
                    ),
                    current_state=current_status.value,
                    requested_state=target_status.value,
                ),
            )

        if self.is_workflow_terminal(current_status):
            return (
                TransitionViolation(
                    code="TERMINAL_WORKFLOW_STATE",
                    message=(
                        "A workflow in a terminal state cannot "
                        "transition further."
                    ),
                    current_state=current_status.value,
                    requested_state=target_status.value,
                ),
            )

        allowed_targets = self.allowed_workflow_targets(
            current_status
        )

        if target_status not in allowed_targets:
            violations.append(
                TransitionViolation(
                    code="INVALID_WORKFLOW_TRANSITION",
                    message=(
                        f"Workflow transition from "
                        f"{current_status.value!r} to "
                        f"{target_status.value!r} is not allowed."
                    ),
                    current_state=current_status.value,
                    requested_state=target_status.value,
                    metadata={
                        "allowed_targets": sorted(
                            status.value
                            for status in allowed_targets
                        ),
                    },
                )
            )

        if not violations:
            for guard in self.guards:
                violation = guard.evaluate(
                    instance,
                    target_status,
                )

                if violation is not None:
                    violations.append(violation)

        return tuple(
            sorted(
                violations,
                key=lambda item: (
                    item.code,
                    item.message,
                ),
            )
        )

    def validate_step_transition(
        self,
        current_status: StepStatus,
        target_status: StepStatus,
        *,
        step_id: str,
    ) -> tuple[TransitionViolation, ...]:
        """Validate a workflow-step transition."""

        cleaned_step_id = str(step_id or "").strip()

        if not cleaned_step_id:
            return (
                TransitionViolation(
                    code="STEP_ID_REQUIRED",
                    message=(
                        "Workflow step ID is required for "
                        "a step transition."
                    ),
                    field="step_id",
                    current_state=current_status.value,
                    requested_state=target_status.value,
                ),
            )

        if current_status is target_status:
            if self.allow_idempotent_transitions:
                return ()

            return (
                TransitionViolation(
                    code="IDEMPOTENT_TRANSITION_NOT_ALLOWED",
                    message=(
                        "An identical workflow step transition "
                        "is not permitted."
                    ),
                    current_state=current_status.value,
                    requested_state=target_status.value,
                    metadata={
                        "step_id": cleaned_step_id,
                    },
                ),
            )

        if self.is_step_terminal(current_status):
            return (
                TransitionViolation(
                    code="TERMINAL_STEP_STATE",
                    message=(
                        "A workflow step in a terminal state "
                        "cannot transition further."
                    ),
                    current_state=current_status.value,
                    requested_state=target_status.value,
                    metadata={
                        "step_id": cleaned_step_id,
                    },
                ),
            )

        allowed_targets = self.allowed_step_targets(
            current_status
        )

        if target_status not in allowed_targets:
            return (
                TransitionViolation(
                    code="INVALID_STEP_TRANSITION",
                    message=(
                        f"Step transition from "
                        f"{current_status.value!r} to "
                        f"{target_status.value!r} is not allowed."
                    ),
                    current_state=current_status.value,
                    requested_state=target_status.value,
                    metadata={
                        "step_id": cleaned_step_id,
                        "allowed_targets": sorted(
                            status.value
                            for status in allowed_targets
                        ),
                    },
                ),
            )

        return ()


def build_default_transition_policy() -> TransitionPolicy:
    """Build the platform's secure default transition policy."""

    workflow_transitions = {
        WorkflowStatus.CREATED: frozenset(
            {
                WorkflowStatus.READY,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.READY: frozenset(
            {
                WorkflowStatus.RUNNING,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.RUNNING: frozenset(
            {
                WorkflowStatus.WAITING,
                WorkflowStatus.PAUSED,
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
                WorkflowStatus.COMPENSATING,
            }
        ),
        WorkflowStatus.WAITING: frozenset(
            {
                WorkflowStatus.RUNNING,
                WorkflowStatus.PAUSED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.PAUSED: frozenset(
            {
                WorkflowStatus.RUNNING,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.FAILED: frozenset(
            {
                WorkflowStatus.COMPENSATING,
            }
        ),
        WorkflowStatus.COMPENSATING: frozenset(
            {
                WorkflowStatus.COMPENSATED,
                WorkflowStatus.FAILED,
            }
        ),
        WorkflowStatus.COMPLETED: frozenset(),
        WorkflowStatus.CANCELLED: frozenset(),
        WorkflowStatus.COMPENSATED: frozenset(),
    }

    step_transitions = {
        StepStatus.PENDING: frozenset(
            {
                StepStatus.READY,
                StepStatus.SKIPPED,
                StepStatus.CANCELLED,
            }
        ),
        StepStatus.READY: frozenset(
            {
                StepStatus.RUNNING,
                StepStatus.SKIPPED,
                StepStatus.CANCELLED,
            }
        ),
        StepStatus.RUNNING: frozenset(
            {
                StepStatus.WAITING,
                StepStatus.SUCCEEDED,
                StepStatus.FAILED,
                StepStatus.CANCELLED,
                StepStatus.COMPENSATING,
            }
        ),
        StepStatus.WAITING: frozenset(
            {
                StepStatus.RUNNING,
                StepStatus.FAILED,
                StepStatus.CANCELLED,
            }
        ),
        StepStatus.FAILED: frozenset(
            {
                StepStatus.READY,
                StepStatus.COMPENSATING,
            }
        ),
        StepStatus.COMPENSATING: frozenset(
            {
                StepStatus.COMPENSATED,
                StepStatus.FAILED,
            }
        ),
        StepStatus.SUCCEEDED: frozenset(),
        StepStatus.SKIPPED: frozenset(),
        StepStatus.CANCELLED: frozenset(),
        StepStatus.COMPENSATED: frozenset(),
    }

    return TransitionPolicy(
        workflow_transitions=workflow_transitions,
        step_transitions=step_transitions,
        workflow_terminal_states=frozenset(
            {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.CANCELLED,
                WorkflowStatus.COMPENSATED,
            }
        ),
        step_terminal_states=frozenset(
            {
                StepStatus.SUCCEEDED,
                StepStatus.SKIPPED,
                StepStatus.CANCELLED,
                StepStatus.COMPENSATED,
            }
        ),
        allow_idempotent_transitions=True,
    )


_default_transition_policy = build_default_transition_policy()


def get_default_transition_policy() -> TransitionPolicy:
    """Return the shared default transition policy."""

    return _default_transition_policy