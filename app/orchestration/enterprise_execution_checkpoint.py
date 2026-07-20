"""Checkpoint persistence for enterprise execution intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
import threading
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_execution_models import (
    EnterpriseExecution,
    EnterpriseExecutionStep,
)
from app.orchestration.exceptions import (
    WorkflowIntegrityError,
    WorkflowNotFoundError,
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseExecutionCheckpoint:
    execution_id: str
    step_id: str
    execution_snapshot: dict[str, Any]
    step_snapshot: dict[str, Any]
    checkpoint_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.checkpoint_id or "").strip():
            raise ValueError("Execution checkpoint ID is required.")
        if not str(self.execution_id or "").strip():
            raise ValueError("Execution checkpoint execution ID is required.")
        if not str(self.step_id or "").strip():
            raise ValueError("Execution checkpoint step ID is required.")

        object.__setattr__(self, "checkpoint_id", str(self.checkpoint_id).strip())
        object.__setattr__(self, "execution_id", str(self.execution_id).strip())
        object.__setattr__(self, "step_id", str(self.step_id).strip())
        object.__setattr__(
            self,
            "execution_snapshot",
            redact_mapping(self.execution_snapshot),
        )
        object.__setattr__(
            self,
            "step_snapshot",
            redact_mapping(self.step_snapshot),
        )
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "execution_id": self.execution_id,
            "step_id": self.step_id,
            "execution_snapshot": redact_mapping(self.execution_snapshot),
            "step_snapshot": redact_mapping(self.step_snapshot),
            "created_at": self.created_at,
            "metadata": redact_mapping(self.metadata),
        }


class EnterpriseExecutionCheckpointStore:
    def __init__(self) -> None:
        self._checkpoints: dict[str, EnterpriseExecutionCheckpoint] = {}
        self._execution_index: dict[str, list[str]] = {}
        self._lock = threading.RLock()

    def create(
        self,
        execution: EnterpriseExecution,
        step: EnterpriseExecutionStep,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> EnterpriseExecutionCheckpoint:
        if step.step_id not in {item.step_id for item in execution.steps}:
            raise WorkflowIntegrityError(
                technical_message=(
                    "Checkpoint step must belong to the execution."
                )
            )

        checkpoint = EnterpriseExecutionCheckpoint(
            execution_id=execution.execution_id,
            step_id=step.step_id,
            execution_snapshot=execution.as_dict(),
            step_snapshot=step.as_dict(),
            metadata=metadata or {},
        )

        with self._lock:
            self._checkpoints[checkpoint.checkpoint_id] = checkpoint
            self._execution_index.setdefault(
                execution.execution_id,
                [],
            ).append(checkpoint.checkpoint_id)

        return checkpoint

    def get(
        self,
        checkpoint_id: str,
    ) -> EnterpriseExecutionCheckpoint:
        cleaned_id = str(checkpoint_id or "").strip()

        if not cleaned_id:
            raise ValueError("Execution checkpoint ID is required.")

        with self._lock:
            checkpoint = self._checkpoints.get(cleaned_id)

        if checkpoint is None:
            raise WorkflowNotFoundError(
                technical_message=(
                    f"Execution checkpoint {cleaned_id!r} was not found."
                )
            )

        return checkpoint

    def latest_for_execution(
        self,
        execution_id: str,
    ) -> EnterpriseExecutionCheckpoint:
        cleaned_id = str(execution_id or "").strip()

        with self._lock:
            checkpoint_ids = self._execution_index.get(cleaned_id, [])

            if not checkpoint_ids:
                raise WorkflowNotFoundError(
                    technical_message=(
                        f"No checkpoints exist for execution {cleaned_id!r}."
                    )
                )

            return self._checkpoints[checkpoint_ids[-1]]

    def list_for_execution(
        self,
        execution_id: str,
    ) -> tuple[EnterpriseExecutionCheckpoint, ...]:
        cleaned_id = str(execution_id or "").strip()

        with self._lock:
            return tuple(
                self._checkpoints[item]
                for item in self._execution_index.get(cleaned_id, [])
            )

    def clear(self) -> None:
        with self._lock:
            self._checkpoints.clear()
            self._execution_index.clear()


_default_enterprise_execution_checkpoint_store = (
    EnterpriseExecutionCheckpointStore()
)


def get_enterprise_execution_checkpoint_store(
) -> EnterpriseExecutionCheckpointStore:
    return _default_enterprise_execution_checkpoint_store