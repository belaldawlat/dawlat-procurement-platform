"""Results produced by the enterprise procurement orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_models import (
    EnterpriseCommand,
    EnterpriseStage,
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseOrchestrationResult:
    """Immutable enterprise orchestration result."""

    case_id: str
    stage: EnterpriseStage
    command: EnterpriseCommand
    successful: bool
    message: str
    execution_allowed: bool
    compensation_required: bool
    evaluated_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise ValueError("Procurement case ID is required.")

        if not str(self.message or "").strip():
            raise ValueError("Enterprise orchestration message is required.")

        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "message", str(self.message).strip())
        object.__setattr__(self, "policy_id", str(self.policy_id or "").strip())
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "stage": self.stage.value,
            "command": self.command.value,
            "successful": self.successful,
            "message": self.message,
            "execution_allowed": self.execution_allowed,
            "compensation_required": self.compensation_required,
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "metadata": redact_mapping(self.metadata),
        }