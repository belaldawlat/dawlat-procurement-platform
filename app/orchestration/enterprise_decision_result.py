"""Results produced by the enterprise decision brain."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionFinding,
    EnterpriseDecisionOutcome,
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