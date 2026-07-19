"""Results produced by the autonomous procurement brain."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.autonomous_procurement_models import (
    AutonomousProcurementAction,
    BrainConfidence,
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AutonomousProcurementResult:
    case_id: str
    confidence_score: float
    confidence: BrainConfidence
    actions: tuple[AutonomousProcurementAction, ...]
    safe_to_execute: bool
    evaluated_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise ValueError("Procurement case ID is required.")
        if not 0 <= self.confidence_score <= 100:
            raise ValueError("Confidence score must be between 0 and 100.")

        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "policy_id", str(self.policy_id or "").strip())
        object.__setattr__(self, "policy_version", str(self.policy_version or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def executable_actions(self) -> tuple[AutonomousProcurementAction, ...]:
        return tuple(action for action in self.actions if action.executable)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "confidence_score": self.confidence_score,
            "confidence": self.confidence.value,
            "safe_to_execute": self.safe_to_execute,
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "metadata": redact_mapping(self.metadata),
            "actions": [action.as_dict() for action in self.actions],
        }