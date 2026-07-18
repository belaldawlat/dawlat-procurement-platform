"""Immutable models for enterprise workflow compensation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field as dataclass_field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


class CompensationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIALLY_COMPENSATED = "partially_compensated"
    COMPENSATED = "compensated"
    FAILED = "failed"
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"
    CANCELLED = "cancelled"


class CompensationStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class CompensationFailureStrategy(str, Enum):
    STOP = "stop"
    CONTINUE = "continue"
    REQUIRE_MANUAL_INTERVENTION = "require_manual_intervention"


@dataclass(frozen=True)
class CompensationStepDefinition:
    step_id: str
    name: str
    original_step_id: str
    handler_key: str
    order: int
    maximum_attempts: int = 1
    failure_strategy: CompensationFailureStrategy = CompensationFailureStrategy.STOP
    idempotency_key: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        step_id = str(self.step_id or "").strip()
        name = str(self.name or "").strip()
        original_step_id = str(self.original_step_id or "").strip()
        handler_key = str(self.handler_key or "").strip()
        if not step_id:
            raise ValueError("Compensation step ID is required.")
        if not name:
            raise ValueError("Compensation step name is required.")
        if not original_step_id:
            raise ValueError("Original workflow step ID is required.")
        if not handler_key:
            raise ValueError("Compensation handler key is required.")
        if self.order < 0:
            raise ValueError("Compensation order cannot be negative.")
        if self.maximum_attempts < 1:
            raise ValueError("Compensation maximum attempts must be at least 1.")
        object.__setattr__(self, "step_id", step_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "original_step_id", original_step_id)
        object.__setattr__(self, "handler_key", handler_key)
        object.__setattr__(self, "idempotency_key", str(self.idempotency_key or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["failure_strategy"] = self.failure_strategy.value
        payload["metadata"] = redact_mapping(self.metadata)
        return payload


@dataclass(frozen=True)
class CompensationStepRecord:
    step_id: str
    original_step_id: str
    status: CompensationStepStatus
    attempt_count: int
    started_at: str
    completed_at: str
    output: Any = None
    error_code: str = ""
    error_id: str = ""
    safe_error_message: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", str(self.step_id or "").strip())
        object.__setattr__(self, "original_step_id", str(self.original_step_id or "").strip())
        object.__setattr__(self, "error_code", str(self.error_code or "").strip())
        object.__setattr__(self, "error_id", str(self.error_id or "").strip())
        object.__setattr__(self, "safe_error_message", str(self.safe_error_message or "").strip())
        object.__setattr__(self, "output", redact_mapping(self.output) if isinstance(self.output, dict) else self.output)
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def successful(self) -> bool:
        return self.status is CompensationStepStatus.SUCCEEDED

    @property
    def failed(self) -> bool:
        return self.status is CompensationStepStatus.FAILED

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["metadata"] = redact_mapping(self.metadata)
        return payload


@dataclass(frozen=True)
class CompensationPlan:
    workflow_instance_id: str
    workflow_id: str
    workflow_version: str
    steps: tuple[CompensationStepDefinition, ...]
    plan_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    status: CompensationStatus = CompensationStatus.PENDING
    current_step_id: str = ""
    records: tuple[CompensationStepRecord, ...] = ()
    created_at: str = dataclass_field(default_factory=utc_timestamp)
    updated_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        workflow_instance_id = str(self.workflow_instance_id or "").strip()
        workflow_id = str(self.workflow_id or "").strip()
        workflow_version = str(self.workflow_version or "").strip()
        plan_id = str(self.plan_id or uuid4().hex).strip()
        if not workflow_instance_id:
            raise ValueError("Workflow instance ID is required.")
        if not workflow_id:
            raise ValueError("Workflow ID is required.")
        if not workflow_version:
            raise ValueError("Workflow version is required.")
        if not self.steps:
            raise ValueError("A compensation plan requires at least one step.")
        object.__setattr__(self, "workflow_instance_id", workflow_instance_id)
        object.__setattr__(self, "workflow_id", workflow_id)
        object.__setattr__(self, "workflow_version", workflow_version)
        object.__setattr__(self, "plan_id", plan_id)
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "current_step_id", str(self.current_step_id or "").strip())
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            CompensationStatus.COMPENSATED,
            CompensationStatus.FAILED,
            CompensationStatus.MANUAL_INTERVENTION_REQUIRED,
            CompensationStatus.CANCELLED,
        }

    @property
    def completed_step_ids(self) -> frozenset[str]:
        return frozenset(record.step_id for record in self.records if record.successful)

    @property
    def failed_step_ids(self) -> tuple[str, ...]:
        return tuple(record.step_id for record in self.records if record.failed)

    def append_record(
        self,
        record: CompensationStepRecord,
        *,
        status: CompensationStatus,
        current_step_id: str = "",
    ) -> "CompensationPlan":
        return replace(
            self,
            status=status,
            current_step_id=current_step_id,
            records=(*self.records, record),
            updated_at=utc_timestamp(),
        )

    def with_status(
        self,
        status: CompensationStatus,
        *,
        current_step_id: str = "",
    ) -> "CompensationPlan":
        return replace(
            self,
            status=status,
            current_step_id=current_step_id,
            updated_at=utc_timestamp(),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "workflow_instance_id": self.workflow_instance_id,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "status": self.status.value,
            "current_step_id": self.current_step_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": redact_mapping(self.metadata),
            "steps": [step.as_dict() for step in self.steps],
            "records": [record.as_dict() for record in self.records],
        }