"""Results produced by the enterprise AI decision network."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_ai_decision_models import (
    AIDecisionExplanation,
    AIDecisionOutcome,
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseAIDecisionResult:
    request_id: str
    case_id: str
    outcome: AIDecisionOutcome
    score: float
    confidence: float
    explanations: tuple[AIDecisionExplanation, ...]
    requires_human_approval: bool
    decided_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    replay_of: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.request_id or "").strip():
            raise ValueError("AI decision result request ID is required.")
        if not str(self.case_id or "").strip():
            raise ValueError("AI decision result case ID is required.")
        if not 0 <= self.score <= 100:
            raise ValueError("AI decision score must be between 0 and 100.")
        if not 0 <= self.confidence <= 100:
            raise ValueError("AI decision confidence must be between 0 and 100.")

        object.__setattr__(self, "request_id", str(self.request_id).strip())
        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "explanations", tuple(self.explanations))
        object.__setattr__(self, "policy_id", str(self.policy_id or "").strip())
        object.__setattr__(self, "policy_version", str(self.policy_version or "").strip())
        object.__setattr__(self, "replay_of", str(self.replay_of or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    @property
    def blocking_explanations(self) -> tuple[AIDecisionExplanation, ...]:
        return tuple(item for item in self.explanations if item.blocking)

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "case_id": self.case_id,
            "outcome": self.outcome.value,
            "score": self.score,
            "confidence": self.confidence,
            "requires_human_approval": self.requires_human_approval,
            "decided_at": self.decided_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "replay_of": self.replay_of,
            "blocking_explanation_count": len(self.blocking_explanations),
            "explanations": [item.as_dict() for item in self.explanations],
            "metadata": redact_mapping(self.metadata),
        }