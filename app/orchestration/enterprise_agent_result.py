"""Results produced by the enterprise AI agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_agent_models import EnterpriseAgentTask


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseAgentExecutionResult:
    task: EnterpriseAgentTask
    successful: bool
    output: dict[str, Any]
    error: str = ""
    completed_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", redact_mapping(self.output))
        object.__setattr__(self, "error", str(self.error or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.as_dict(),
            "successful": self.successful,
            "output": redact_mapping(self.output),
            "error": self.error,
            "completed_at": self.completed_at,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseAgentRuntimeResult:
    completed: tuple[EnterpriseAgentExecutionResult, ...]
    failed: tuple[EnterpriseAgentExecutionResult, ...]
    blocked_tasks: tuple[EnterpriseAgentTask, ...]
    policy_id: str = ""
    policy_version: str = ""
    evaluated_at: str = dataclass_field(default_factory=utc_timestamp)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "completed", tuple(self.completed))
        object.__setattr__(self, "failed", tuple(self.failed))
        object.__setattr__(self, "blocked_tasks", tuple(self.blocked_tasks))
        object.__setattr__(self, "policy_id", str(self.policy_id or "").strip())
        object.__setattr__(
            self,
            "policy_version",
            str(self.policy_version or "").strip(),
        )
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "completed_count": len(self.completed),
            "failed_count": len(self.failed),
            "blocked_count": len(self.blocked_tasks),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "evaluated_at": self.evaluated_at,
            "completed": [item.as_dict() for item in self.completed],
            "failed": [item.as_dict() for item in self.failed],
            "blocked_tasks": [item.as_dict() for item in self.blocked_tasks],
            "metadata": redact_mapping(self.metadata),
        }