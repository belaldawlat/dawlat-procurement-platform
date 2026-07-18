"""
Enterprise Recommendation Intelligence Engine.

Produces governed, explainable and auditable recommendations for the Dawlat AI
Procurement Intelligence Platform.

The engine transforms enterprise decisions and risk assessments into ranked
actions. It does not execute commercial, legal or financial actions. Binding
steps always require authorised human approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from models.decision import (
    DecisionOutcome,
    EnterpriseDecision,
    RecommendedAction,
    RiskSeverity,
)
from services.intelligence.risk_intelligence_engine import (
    RiskAssessment,
    assess_enterprise_risk,
)


@dataclass(frozen=True)
class RecommendationFactor:
    name: str
    score: int
    maximum: int
    explanation: str


@dataclass(frozen=True)
class RankedRecommendation:
    rank: int
    title: str
    action: str
    owner_role: str
    score: int
    confidence_score: int
    priority: str
    approval_required: bool
    blocking: bool
    rationale: tuple[str, ...] = ()
    expected_outcome: str = ""
    prerequisites: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    evidence_labels: tuple[str, ...] = ()


@dataclass
class RecommendationReport:
    decision_id: str
    recommendation_status: str
    executive_recommendation: str
    confidence_score: int
    ranked_recommendations: list[RankedRecommendation] = field(
        default_factory=list
    )
    factors: list[RecommendationFactor] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


class RecommendationIntelligenceEngine:
    """Create one consistent recommendation set for all platform modules."""

    def recommend(
        self,
        decision: EnterpriseDecision,
        *,
        risk_assessment: RiskAssessment | None = None,
    ) -> RecommendationReport:
        risk = risk_assessment or assess_enterprise_risk(decision)

        factors = self._score_factors(decision, risk)
        base_score = sum(item.score for item in factors)
        confidence = self._confidence(decision, risk)

        ranked = self._rank_actions(
            decision=decision,
            risk=risk,
            base_score=base_score,
            confidence=confidence,
        )

        return RecommendationReport(
            decision_id=decision.decision_id,
            recommendation_status=self._status(decision, risk),
            executive_recommendation=self._executive_recommendation(
                decision,
                risk,
                ranked,
            ),
            confidence_score=confidence,
            ranked_recommendations=ranked,
            factors=factors,
            alternatives=self._alternatives(decision, risk),
        )

    @staticmethod
    def _score_factors(
        decision: EnterpriseDecision,
        risk: RiskAssessment,
    ) -> list[RecommendationFactor]:
        buyer_ready = bool(
            decision.buyer_commitment
            and decision.buyer_commitment.accepted_in_writing
            and decision.buyer_funds_cleared()
        )
        supplier_ready = bool(
            decision.supplier_offer
            and decision.supplier_offer.supplier_verified
            and decision.supplier_offer.bank_details_verified
        )
        margin_ready = bool(
            decision.margin_protection
            and decision.margin_protection.margin_protected
        )
        approvals_ready = bool(
            decision.approvals
            and all(
                item.status.value in {"Approved", "Not Required"}
                for item in decision.approvals
            )
        )
        evidence_score = min(15, len(decision.evidence) * 3)
        data_quality_score = max(
            0,
            15 - min(15, len(decision.data_gaps) * 3),
        )
        risk_score = max(0, 20 - round(risk.overall_score * 0.2))

        return [
            RecommendationFactor(
                "Buyer readiness",
                15 if buyer_ready else 0,
                15,
                (
                    "Buyer accepted final terms and cleared funds are confirmed."
                    if buyer_ready
                    else "Buyer acceptance or cleared funds are incomplete."
                ),
            ),
            RecommendationFactor(
                "Supplier readiness",
                15 if supplier_ready else 0,
                15,
                (
                    "Supplier identity and bank details are verified."
                    if supplier_ready
                    else "Supplier verification is incomplete."
                ),
            ),
            RecommendationFactor(
                "Margin protection",
                15 if margin_ready else 0,
                15,
                (
                    "Approved minimum margin is protected."
                    if margin_ready
                    else "Margin is missing or below policy."
                ),
            ),
            RecommendationFactor(
                "Approvals",
                10 if approvals_ready else 0,
                10,
                (
                    "Required approvals are complete."
                    if approvals_ready
                    else "Required approvals remain incomplete."
                ),
            ),
            RecommendationFactor(
                "Evidence quality",
                evidence_score,
                15,
                f"{len(decision.evidence)} evidence record(s) attached.",
            ),
            RecommendationFactor(
                "Data completeness",
                data_quality_score,
                15,
                f"{len(decision.data_gaps)} material data gap(s) remain.",
            ),
            RecommendationFactor(
                "Risk position",
                risk_score,
                20,
                (
                    f"Overall risk score is {risk.overall_score}/100 "
                    f"({risk.overall_severity.value})."
                ),
            ),
        ]

    def _rank_actions(
        self,
        *,
        decision: EnterpriseDecision,
        risk: RiskAssessment,
        base_score: int,
        confidence: int,
    ) -> list[RankedRecommendation]:
        candidates: list[RecommendedAction] = list(
            decision.recommendations
        )

        if risk.is_blocked:
            candidates.insert(
                0,
                RecommendedAction(
                    priority=0,
                    action="Resolve all blocking risk and control failures.",
                    owner_role="Managing Director",
                    reason="The current deal is not safe to proceed.",
                    approval_required=True,
                    blocking=True,
                ),
            )

        ranked: list[RankedRecommendation] = []

        for index, item in enumerate(candidates, start=1):
            action_score = base_score

            if item.blocking:
                action_score += 15
            if item.approval_required:
                action_score += 5

            action_score += max(0, 10 - item.priority)
            action_score = max(0, min(100, action_score))

            ranked.append(
                RankedRecommendation(
                    rank=index,
                    title=self._title_for_action(item.action),
                    action=item.action,
                    owner_role=item.owner_role,
                    score=action_score,
                    confidence_score=confidence,
                    priority=self._priority_label(
                        item.blocking,
                        action_score,
                    ),
                    approval_required=item.approval_required,
                    blocking=item.blocking,
                    rationale=tuple(
                        value
                        for value in (
                            item.reason,
                            risk.proceed_recommendation,
                        )
                        if value
                    ),
                    expected_outcome=self._expected_outcome(item),
                    prerequisites=tuple(
                        risk.mitigations[:5]
                        if item.blocking
                        else []
                    ),
                    risks=tuple(
                        risk.blocking_reasons[:5]
                    ),
                    evidence_labels=tuple(
                        evidence.label
                        for evidence in decision.evidence[:5]
                    ),
                )
            )

        ranked.sort(
            key=lambda item: (
                item.blocking,
                item.score,
                -item.rank,
            ),
            reverse=True,
        )

        return [
            RankedRecommendation(
                rank=index,
                title=item.title,
                action=item.action,
                owner_role=item.owner_role,
                score=item.score,
                confidence_score=item.confidence_score,
                priority=item.priority,
                approval_required=item.approval_required,
                blocking=item.blocking,
                rationale=item.rationale,
                expected_outcome=item.expected_outcome,
                prerequisites=item.prerequisites,
                risks=item.risks,
                evidence_labels=item.evidence_labels,
            )
            for index, item in enumerate(ranked, start=1)
        ]

    @staticmethod
    def _status(
        decision: EnterpriseDecision,
        risk: RiskAssessment,
    ) -> str:
        if risk.is_blocked:
            return "Blocked"
        if decision.outcome == DecisionOutcome.APPROVED:
            return "Proceed"
        if decision.outcome == DecisionOutcome.CONDITIONALLY_APPROVED:
            return "Proceed Conditionally"
        if decision.outcome in {
            DecisionOutcome.PENDING_APPROVAL,
            DecisionOutcome.PENDING_INFORMATION,
        }:
            return "Hold"
        return "Reject or Reassess"

    @staticmethod
    def _executive_recommendation(
        decision: EnterpriseDecision,
        risk: RiskAssessment,
        ranked: list[RankedRecommendation],
    ) -> str:
        top_action = (
            ranked[0].action
            if ranked
            else "No action recommendation is available."
        )

        if risk.is_blocked:
            return (
                f"BLOCK the deal. {len(risk.blocking_reasons)} mandatory "
                f"control issue(s) remain. First action: {top_action}"
            )

        if decision.outcome == DecisionOutcome.APPROVED:
            return (
                f"Proceed through controlled execution. "
                f"First action: {top_action}"
            )

        return (
            f"Hold the deal until outstanding conditions are complete. "
            f"First action: {top_action}"
        )

    @staticmethod
    def _alternatives(
        decision: EnterpriseDecision,
        risk: RiskAssessment,
    ) -> list[str]:
        alternatives = []

        if decision.supplier_offer is None:
            alternatives.append(
                "Run global and local supplier discovery."
            )
        else:
            alternatives.append(
                "Compare at least two additional verified supplier offers."
            )

        if not decision.margin_protection or not (
            decision.margin_protection.margin_protected
        ):
            alternatives.append(
                "Renegotiate supplier pricing or revise buyer pricing."
            )

        if risk.overall_severity in {
            RiskSeverity.HIGH,
            RiskSeverity.CRITICAL,
        }:
            alternatives.append(
                "Use a lower-risk supplier, route or payment structure."
            )

        alternatives.append(
            "Stop the deal if trust, compliance or minimum margin cannot be protected."
        )

        return list(dict.fromkeys(alternatives))

    @staticmethod
    def _confidence(
        decision: EnterpriseDecision,
        risk: RiskAssessment,
    ) -> int:
        score = round(
            decision.confidence_score * 0.6
            + risk.confidence_score * 0.4
        )
        return max(0, min(100, score))

    @staticmethod
    def _priority_label(
        blocking: bool,
        score: int,
    ) -> str:
        if blocking:
            return "Critical"
        if score >= 80:
            return "High"
        if score >= 60:
            return "Medium"
        return "Low"

    @staticmethod
    def _title_for_action(action: str) -> str:
        cleaned = action.strip().rstrip(".")
        return cleaned[:80] or "Recommended Action"

    @staticmethod
    def _expected_outcome(
        action: RecommendedAction,
    ) -> str:
        if action.blocking:
            return (
                "Remove a mandatory blocker and reduce financial, legal "
                "or operational exposure."
            )
        if action.approval_required:
            return (
                "Move the deal safely to the next approved control stage."
            )
        return "Improve decision completeness and execution readiness."


_engine = RecommendationIntelligenceEngine()


def generate_enterprise_recommendations(
    decision: EnterpriseDecision,
    *,
    risk_assessment: RiskAssessment | None = None,
) -> RecommendationReport:
    """Public recommendation entry point."""

    return _engine.recommend(
        decision,
        risk_assessment=risk_assessment,
    )