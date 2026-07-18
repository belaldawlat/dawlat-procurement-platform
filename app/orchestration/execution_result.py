"""Immutable workflow execution results and records."""

from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field as dataclass_field,
)
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.workflow_models import (
    StepStatus,
    WorkflowInstance,
)


def _utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class ExecutionOutcome(str, Enum):
    """Supported execution outcomes."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    WAITING = "waiting"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class StepExecutionRecord:
    """Immutable result of a single workflow-step execution."""

    step_id: str
    step_name: str
    outcome: ExecutionOutcome
    status: StepStatus
    attempt_count: int
    started_at: str
    completed_at: str
    output: Any = None
    error_code: str = ""
    error_id: str = ""
    safe_error_message: str = ""
    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Normalise and redact record data."""

        object.__setattr__(
            self,
            "step_id",
            str(self.step_id or "").strip(),
        )
        object.__setattr__(
            self,
            "step_name",
            str(self.step_name or "").strip(),
        )
        object.__setattr__(
            self,
            "error_code",
            str(self.error_code or "").strip(),
        )
        object.__setattr__(
            self,
            "error_id",
            str(self.error_id or "").strip(),
        )
        object.__setattr__(
            self,
            "safe_error_message",
            str(self.safe_error_message or "").strip(),
        )
        object.__setattr__(
            self,
            "output",
            (
                redact_mapping(self.output)
                if isinstance(self.output, dict)
                else self.output
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def successful(self) -> bool:
        """Return whether the step succeeded."""

        return self.outcome is ExecutionOutcome.SUCCEEDED

    @property
    def failed(self) -> bool:
        """Return whether the step failed."""

        return self.outcome is ExecutionOutcome.FAILED

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        payload = asdict(self)
        payload["outcome"] = self.outcome.value
        payload["status"] = self.status.value
        payload["metadata"] = redact_mapping(self.metadata)

        if isinstance(self.output, dict):
            payload["output"] = redact_mapping(self.output)

        return payload


@dataclass(frozen=True)
class WorkflowExecutionResult:
    """Complete result of a workflow execution run."""

    instance: WorkflowInstance
    outcome: ExecutionOutcome
    step_records: tuple[StepExecutionRecord, ...]
    started_at: str
    completed_at: str = dataclass_field(
        default_factory=_utc_timestamp
    )
    message: str = ""
    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Normalise immutable result values."""

        object.__setattr__(
            self,
            "step_records",
            tuple(self.step_records),
        )
        object.__setattr__(
            self,
            "message",
            str(self.message or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def successful(self) -> bool:
        """Return whether the workflow succeeded."""

        return self.outcome is ExecutionOutcome.SUCCEEDED

    @property
    def failed(self) -> bool:
        """Return whether the workflow failed."""

        return self.outcome is ExecutionOutcome.FAILED

    @property
    def step_count(self) -> int:
        """Return the number of executed steps."""

        return len(self.step_records)

    @property
    def failed_step_ids(self) -> tuple[str, ...]:
        """Return failed step identifiers."""

        return tuple(
            record.step_id
            for record in self.step_records
            if record.failed
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""

        return {
            "instance_id": self.instance.instance_id,
            "workflow_id": self.instance.workflow_id,
            "workflow_version": (
                self.instance.workflow_version
            ),
            "workflow_status": self.instance.status.value,
            "outcome": self.outcome.value,
            "successful": self.successful,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "message": self.message,
            "metadata": redact_mapping(self.metadata),
            "step_records": [
                record.as_dict()
                for record in self.step_records
            ],
        }