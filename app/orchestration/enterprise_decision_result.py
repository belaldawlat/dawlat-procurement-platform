"""Results produced by the enterprise decision brain."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionFinding,
    EnterpriseDecisionOutcome,
    EnterpriseDecisionRecommendation,
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseDecisionResult:
    request_id: str
    case_id: str
    outcome: EnterpriseDecisionOutcome
    score: float
    confidence: float
    findings: tuple[EnterpriseDecisionFinding, ...]
    requires_human_approval: bool
    decided_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.request_id or "").strip():
            raise ValueError("Decision result request ID is required.")
        if not str(self.case_id or "").strip():
            raise ValueError("Decision result case ID is required.")
        if not 0 <= self.score <= 100:
            raise ValueError("Decision score must be between 0 and 100.")
        if not 0 <= self.confidence <= 100:
            raise ValueError("Decision confidence must be between 0 and 100.")

        object.__setattr__(self, "request_id", str(self.request_id).strip())
        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "findings", tuple(self.findings))
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
    def blocking_findings(
        self,
    ) -> tuple[EnterpriseDecisionFinding, ...]:
        return tuple(
            finding
            for finding in self.findings
            if finding.blocking
        )

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
            "blocking_finding_count": len(self.blocking_findings),
            "findings": [finding.as_dict() for finding in self.findings],
            "metadata": redact_mapping(self.metadata),
        }

@dataclass(frozen=True)
class EnterpriseDecisionEngineResult:
    """Unified Package T decision result."""

    context_id: str
    case_id: str
    outcome: EnterpriseDecisionOutcome
    score: float
    confidence: float
    recommendations: tuple["EnterpriseDecisionRecommendation", ...]
    explanation: str
    requires_human_approval: bool
    decision_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    decided_at: str = dataclass_field(default_factory=utc_timestamp)
    policy_id: str = ""
    policy_version: str = ""
    audit_reference: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.decision_id or "").strip():
            raise ValueError("Decision engine result ID is required.")
        if not str(self.context_id or "").strip():
            raise ValueError("Decision context ID is required.")
        if not str(self.case_id or "").strip():
            raise ValueError("Decision case ID is required.")
        if not str(self.explanation or "").strip():
            raise ValueError("Decision explanation is required.")
        if not 0 <= self.score <= 100:
            raise ValueError("Decision engine score must be between 0 and 100.")
        if not 0 <= self.confidence <= 100:
            raise ValueError(
                "Decision engine confidence must be between 0 and 100."
            )

        object.__setattr__(self, "decision_id", str(self.decision_id).strip())
        object.__setattr__(self, "context_id", str(self.context_id).strip())
        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "recommendations", tuple(self.recommendations))
        object.__setattr__(self, "explanation", str(self.explanation).strip())
        object.__setattr__(
            self,
            "audit_reference",
            str(self.audit_reference or "").strip(),
        )
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "context_id": self.context_id,
            "case_id": self.case_id,
            "outcome": self.outcome.value,
            "score": self.score,
            "confidence": self.confidence,
            "requires_human_approval": self.requires_human_approval,
            "explanation": self.explanation,
            "recommendations": [
                item.as_dict()
                for item in self.recommendations
            ],
            "decided_at": self.decided_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "audit_reference": self.audit_reference,
            "metadata": redact_mapping(self.metadata),
        }