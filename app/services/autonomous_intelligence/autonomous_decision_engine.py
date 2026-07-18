"""Enterprise autonomous decision engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DecisionOutcome(str, Enum):
    REJECT = "Reject"
    HOLD = "Hold"
    REVIEW = "Review"
    PROCEED = "Proceed"


@dataclass(frozen=True)
class DecisionInput:
    case_id: str
    opportunity_score: int
    risk_score: int
    trust_score: int
    approval_allowed: bool
    compliance_cleared: bool
    funds_cleared: bool
    contract_ready: bool
    health_score: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionResult:
    case_id: str
    outcome: DecisionOutcome
    score: int
    execution_allowed: bool
    blockers: tuple[str, ...]
    reasons: tuple[str, ...]
    explanation: str
    decided_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class AutonomousDecisionEngine:
    def decide(self, item: DecisionInput) -> DecisionResult:
        blockers: list[str] = []
        reasons: list[str] = []

        if item.risk_score >= 80:
            blockers.append("Risk score is critically high.")
        if item.trust_score < 50:
            blockers.append("Trust score is below threshold.")
        if not item.approval_allowed:
            blockers.append("Required approval has not been granted.")
        if not item.compliance_cleared:
            blockers.append("Compliance clearance is incomplete.")
        if not item.funds_cleared:
            blockers.append("Buyer funds are not cleared.")
        if not item.contract_ready:
            blockers.append("Contract readiness is incomplete.")
        if item.health_score < 70:
            blockers.append("Platform health is below threshold.")

        score = round(
            item.opportunity_score * 0.30
            + (100 - item.risk_score) * 0.20
            + item.trust_score * 0.20
            + item.health_score * 0.10
            + (100 if item.approval_allowed else 0) * 0.10
            + (100 if item.compliance_cleared else 0) * 0.10
        )
        score = max(0, min(100, score))

        if blockers:
            outcome = DecisionOutcome.HOLD
        elif score >= 75:
            outcome = DecisionOutcome.PROCEED
            reasons.append("All mandatory controls passed.")
        elif score >= 55:
            outcome = DecisionOutcome.REVIEW
        else:
            outcome = DecisionOutcome.REJECT

        execution_allowed = (
            outcome == DecisionOutcome.PROCEED
            and not blockers
        )

        return DecisionResult(
            case_id=item.case_id,
            outcome=outcome,
            score=score,
            execution_allowed=execution_allowed,
            blockers=tuple(blockers),
            reasons=tuple(reasons),
            explanation=(
                f"Decision score is {score}/100. Outcome: "
                f"{outcome.value}. Execution is "
                f"{'allowed' if execution_allowed else 'not allowed'}."
            ),
        )


_engine = AutonomousDecisionEngine()


def get_autonomous_decision_engine() -> AutonomousDecisionEngine:
    return _engine