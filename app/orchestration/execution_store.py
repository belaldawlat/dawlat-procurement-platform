"""Thread-safe storage for workflow execution state."""

from __future__ import annotations

import threading
from dataclasses import replace
from typing import Protocol

from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)
from app.orchestration.workflow_models import (
    StepStatus,
    WorkflowInstance,
)


class ExecutionStore(Protocol):
    """Contract for workflow execution persistence."""

    def create(
        self,
        instance: WorkflowInstance,
        step_statuses: dict[str, StepStatus],
    ) -> WorkflowInstance:
        """Persist a new workflow instance."""

    def get(
        self,
        instance_id: str,
    ) -> WorkflowInstance:
        """Return a workflow instance."""

    def save(
        self,
        instance: WorkflowInstance,
    ) -> WorkflowInstance:
        """Persist an updated workflow instance."""

    def get_step_statuses(
        self,
        instance_id: str,
    ) -> dict[str, StepStatus]:
        """Return workflow step statuses."""

    def update_step_status(
        self,
        instance_id: str,
        step_id: str,
        status: StepStatus,
    ) -> None:
        """Update a workflow step status."""


class InMemoryExecutionStore:
    """Thread-safe in-memory execution store."""

    def __init__(self) -> None:
        self._instances: dict[str, WorkflowInstance] = {}
        self._step_statuses: dict[
            str,
            dict[str, StepStatus],
        ] = {}
        self._lock = threading.RLock()

    def create(
        self,
        instance: WorkflowInstance,
        step_statuses: dict[str, StepStatus],
    ) -> WorkflowInstance:
        """Persist a new workflow instance."""

        if not isinstance(instance, WorkflowInstance):
            raise TypeError(
                "Execution store requires a WorkflowInstance."
            )

        instance_id = instance.instance_id

        with self._lock:
            if instance_id in self._instances:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Workflow instance {instance_id!r} "
                        "already exists."
                    ),
                    metadata={
                        "instance_id": instance_id,
                    },
                )

            self._instances[instance_id] = instance
            self._step_statuses[instance_id] = dict(
                step_statuses
            )

        return instance

    def get(
        self,
        instance_id: str,
    ) -> WorkflowInstance:
        """Return an exact workflow instance."""

        cleaned_id = self._clean_identifier(
            instance_id,
            "Workflow instance ID",
        )

        with self._lock:
            instance = self._instances.get(cleaned_id)

        if instance is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Workflow instance {cleaned_id!r} "
                    "was not found."
                ),
                metadata={
                    "instance_id": cleaned_id,
                },
            )

        return instance

    def save(
        self,
        instance: WorkflowInstance,
    ) -> WorkflowInstance:
        """Persist an updated workflow instance."""

        if not isinstance(instance, WorkflowInstance):
            raise TypeError(
                "Execution store requires a WorkflowInstance."
            )

        with self._lock:
            if instance.instance_id not in self._instances:
                raise WorkflowNotFoundError(
                    technical_message=(
                        f"Workflow instance "
                        f"{instance.instance_id!r} "
                        "was not found."
                    ),
                    metadata={
                        "instance_id": instance.instance_id,
                    },
                )

            self._instances[instance.instance_id] = instance

        return instance

    def get_step_statuses(
        self,
        instance_id: str,
    ) -> dict[str, StepStatus]:
        """Return a defensive copy of step statuses."""

        cleaned_id = self._clean_identifier(
            instance_id,
            "Workflow instance ID",
        )

        with self._lock:
            statuses = self._step_statuses.get(cleaned_id)

            if statuses is None:
                raise WorkflowNotFoundError(
                    technical_message=(
                        f"Workflow instance {cleaned_id!r} "
                        "was not found."
                    ),
                    metadata={
                        "instance_id": cleaned_id,
                    },
                )

            return dict(statuses)

    def update_step_status(
        self,
        instance_id: str,
        step_id: str,
        status: StepStatus,
    ) -> None:
        """Update an existing step status."""

        cleaned_instance_id = self._clean_identifier(
            instance_id,
            "Workflow instance ID",
        )
        cleaned_step_id = self._clean_identifier(
            step_id,
            "Workflow step ID",
        )

        if not isinstance(status, StepStatus):
            raise TypeError(
                "Step status must be a StepStatus value."
            )

        with self._lock:
            statuses = self._step_statuses.get(
                cleaned_instance_id
            )

            if statuses is None:
                raise WorkflowNotFoundError(
                    technical_message=(
                        f"Workflow instance "
                        f"{cleaned_instance_id!r} "
                        "was not found."
                    )
                )

            if cleaned_step_id not in statuses:
                raise WorkflowIntegrityError(
                    technical_message=(
                        f"Step {cleaned_step_id!r} does not "
                        "belong to workflow instance "
                        f"{cleaned_instance_id!r}."
                    ),
                    metadata={
                        "instance_id": cleaned_instance_id,
                        "step_id": cleaned_step_id,
                    },
                )

            statuses[cleaned_step_id] = status

    def list_instances(
        self,
    ) -> tuple[WorkflowInstance, ...]:
        """Return all instances deterministically."""

        with self._lock:
            return tuple(
                self._instances[instance_id]
                for instance_id in sorted(self._instances)
            )

    def delete(
        self,
        instance_id: str,
    ) -> WorkflowInstance:
        """Delete and return a workflow instance."""

        cleaned_id = self._clean_identifier(
            instance_id,
            "Workflow instance ID",
        )

        with self._lock:
            instance = self._instances.pop(
                cleaned_id,
                None,
            )
            self._step_statuses.pop(cleaned_id, None)

        if instance is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Workflow instance {cleaned_id!r} "
                    "was not found."
                )
            )

        return instance

    def clear(self) -> None:
        """Remove all workflow execution state."""

        with self._lock:
            self._instances.clear()
            self._step_statuses.clear()

    @staticmethod
    def _clean_identifier(
        value: str,
        label: str,
    ) -> str:
        cleaned = str(value or "").strip()

        if not cleaned:
            raise ValueError(f"{label} is required.")

        return cleaned


_default_execution_store = InMemoryExecutionStore()


def get_execution_store() -> InMemoryExecutionStore:
    """Return the shared in-memory execution store."""

    return _default_execution_store