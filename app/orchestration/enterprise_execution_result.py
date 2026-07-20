"""Results produced by enterprise execution intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_execution_models import (
    EnterpriseExecution,
    EnterpriseExecutionStep,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class EnterpriseExecutionIssueSeverity(str, Enum):
    """Severity levels for execution findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class EnterpriseExecutionIssue:
    """One execution validation, runtime or recovery issue."""

    code: str
    message: str
    severity: EnterpriseExecutionIssueSeverity
    blocking: bool = False
    entity_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("Execution issue code is required.")
        if not str(self.message or "").strip():
            raise ValueError("Execution issue message is required.")

        object.__setattr__(
            self,
            "code",
            str(self.code).strip(),
        )
        object.__setattr__(
            self,
            "message",
            str(self.message).strip(),
        )
        object.__setattr__(
            self,
            "entity_id",
            str(self.entity_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "blocking": self.blocking,
            "entity_id": self.entity_id,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseExecutionStepResult:
    """Result of one execution step."""

    step: EnterpriseExecutionStep
    successful: bool
    output: dict[str, Any]
    error: str = ""
    started_at: str = dataclass_field(default_factory=utc_timestamp)
    completed_at: str = dataclass_field(default_factory=utc_timestamp)
    duration_ms: float = 0.0
    checkpoint_id: str = ""
    telemetry_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError(
                "Execution step duration cannot be negative."
            )

        object.__setattr__(
            self,
            "output",
            redact_mapping(self.output),
        )
        object.__setattr__(
            self,
            "error",
            str(self.error or "").strip(),
        )
        object.__setattr__(
            self,
            "checkpoint_id",
            str(self.checkpoint_id or "").strip(),
        )
        object.__setattr__(
            self,
            "telemetry_id",
            str(self.telemetry_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "step": self.step.as_dict(),
            "successful": self.successful,
            "output": redact_mapping(self.output),
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "checkpoint_id": self.checkpoint_id,
            "telemetry_id": self.telemetry_id,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseExecutionResult:
    """Top-level enterprise execution result."""

    execution: EnterpriseExecution
    successful: bool
    completed_steps: tuple[EnterpriseExecutionStepResult, ...]
    failed_steps: tuple[EnterpriseExecutionStepResult, ...]
    blocked_steps: tuple[EnterpriseExecutionStep, ...]
    issues: tuple[EnterpriseExecutionIssue, ...]
    started_at: str = dataclass_field(default_factory=utc_timestamp)
    completed_at: str = dataclass_field(default_factory=utc_timestamp)
    duration_ms: float = 0.0
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError(
                "Enterprise execution duration cannot be negative."
            )

        object.__setattr__(
            self,
            "completed_steps",
            tuple(self.completed_steps),
        )
        object.__setattr__(
            self,
            "failed_steps",
            tuple(self.failed_steps),
        )
        object.__setattr__(
            self,
            "blocked_steps",
            tuple(self.blocked_steps),
        )
        object.__setattr__(
            self,
            "issues",
            tuple(self.issues),
        )
        object.__setattr__(
            self,
            "policy_id",
            str(self.policy_id or "").strip(),
        )
        object.__setattr__(
            self,
            "policy_version",
            str(self.policy_version or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def blocking_issues(
        self,
    ) -> tuple[EnterpriseExecutionIssue, ...]:
        """Return all blocking issues."""

        return tuple(
            issue
            for issue in self.issues
            if issue.blocking
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "execution": self.execution.as_dict(),
            "successful": self.successful,
            "completed_step_count": len(self.completed_steps),
            "failed_step_count": len(self.failed_steps),
            "blocked_step_count": len(self.blocked_steps),
            "blocking_issue_count": len(self.blocking_issues),
            "completed_steps": [
                item.as_dict()
                for item in self.completed_steps
            ],
            "failed_steps": [
                item.as_dict()
                for item in self.failed_steps
            ],
            "blocked_steps": [
                item.as_dict()
                for item in self.blocked_steps
            ],
            "issues": [
                item.as_dict()
                for item in self.issues
            ],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "metadata": redact_mapping(self.metadata),
        }