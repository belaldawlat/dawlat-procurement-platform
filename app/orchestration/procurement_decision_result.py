"""Results returned by the procurement decision engine."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.procurement_decision_models import (
    DecisionFinding,
    ProcurementDecision,
)


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProcurementDecisionResult:
    """Immutable procurement decision result."""

    case_id: str
    decision: ProcurementDecision
    score: float
    findings: tuple[DecisionFinding, ...]
    evaluated_at: str = dataclass_field(
        default_factory=utc_timestamp
    )
    policy_id: str = ""
    policy_version: str = ""
    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Validate and normalise result values."""

        case_id = str(self.case_id or "").strip()

        if not case_id:
            raise ValueError("Procurement case ID is required.")

        if not 0 <= self.score <= 100:
            raise ValueError(
                "Procurement decision score must be between 0 and 100."
            )

        object.__setattr__(self, "case_id", case_id)
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
    def blocking_findings(self) -> tuple[DecisionFinding, ...]:
        """Return all findings that block execution."""

        return tuple(
            finding
            for finding in self.findings
            if finding.blocking
        )

    @property
    def can_proceed(self) -> bool:
        """Return whether the final decision permits execution."""

        return self.decision is ProcurementDecision.PROCEED

    @property
    def requires_attention(self) -> bool:
        """Return whether intervention is needed."""

        return self.decision in {
            ProcurementDecision.HOLD,
            ProcurementDecision.MANUAL_REVIEW,
            ProcurementDecision.REJECT,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "case_id": self.case_id,
            "decision": self.decision.value,
            "score": self.score,
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "can_proceed": self.can_proceed,
            "requires_attention": self.requires_attention,
            "blocking_finding_count": len(
                self.blocking_findings
            ),
            "metadata": redact_mapping(self.metadata),
            "findings": [
                finding.as_dict()
                for finding in self.findings
            ],
        }