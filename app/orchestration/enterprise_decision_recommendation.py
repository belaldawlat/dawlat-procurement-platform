"""Ranked recommendations for Package T enterprise decisions."""

from __future__ import annotations

from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionContext,
    EnterpriseDecisionOutcome,
    EnterpriseDecisionRecommendation,
    EnterpriseRecommendationType,
)
from app.orchestration.enterprise_decision_policy import (
    EnterpriseDecisionEnginePolicy,
)


class EnterpriseDecisionRecommendationEngine:
    """Generate deterministic next-best actions."""

    def generate(
        self,
        *,
        context: EnterpriseDecisionContext,
        outcome: EnterpriseDecisionOutcome,
        score: float,
        confidence: float,
        policy: EnterpriseDecisionEnginePolicy,
    ) -> tuple[EnterpriseDecisionRecommendation, ...]:
        """Generate ranked recommendations for an outcome."""

        if not 0 <= score <= 100:
            raise ValueError("Decision score must be between 0 and 100.")
        if not 0 <= confidence <= 100:
            raise ValueError(
                "Decision confidence must be between 0 and 100."
            )

        candidates: list[
            tuple[
                EnterpriseRecommendationType,
                str,
                str,
                float,
                bool,
            ]
        ] = []

        if outcome is EnterpriseDecisionOutcome.PROCEED:
            candidates.append(
                (
                    EnterpriseRecommendationType.EXECUTE,
                    "Execute approved enterprise action",
                    (
                        "Evidence and confidence meet the configured "
                        "proceeding thresholds."
                    ),
                    score,
                    policy.require_human_approval_for_external_actions,
                )
            )
            candidates.append(
                (
                    EnterpriseRecommendationType.MONITOR,
                    "Monitor execution and outcome",
                    (
                        "Track events, risks and performance after "
                        "execution."
                    ),
                    max(0.0, score - 10.0),
                    False,
                )
            )

        elif outcome is EnterpriseDecisionOutcome.MANUAL_REVIEW:
            candidates.append(
                (
                    EnterpriseRecommendationType.APPROVE,
                    "Request human approval",
                    (
                        "Decision requires authorised human review "
                        "before execution."
                    ),
                    confidence,
                    True,
                )
            )
            candidates.append(
                (
                    EnterpriseRecommendationType.REQUEST_INFORMATION,
                    "Collect additional evidence",
                    (
                        "Increase source coverage and resolve material "
                        "uncertainty."
                    ),
                    max(0.0, 100.0 - confidence),
                    False,
                )
            )

        elif outcome is EnterpriseDecisionOutcome.ESCALATE:
            candidates.append(
                (
                    EnterpriseRecommendationType.ESCALATE,
                    "Escalate to enterprise control owner",
                    (
                        "Critical or blocking evidence requires senior "
                        "decision authority."
                    ),
                    100.0,
                    True,
                )
            )
            candidates.append(
                (
                    EnterpriseRecommendationType.PAUSE,
                    "Pause dependent execution",
                    (
                        "Prevent downstream side effects until the "
                        "escalation is resolved."
                    ),
                    95.0,
                    True,
                )
            )

        elif outcome is EnterpriseDecisionOutcome.REJECT:
            candidates.append(
                (
                    EnterpriseRecommendationType.REJECT,
                    "Reject the proposed action",
                    (
                        "The enterprise score or blocking evidence "
                        "does not satisfy policy."
                    ),
                    max(0.0, 100.0 - score),
                    True,
                )
            )
            candidates.append(
                (
                    EnterpriseRecommendationType.REPLAN,
                    "Create a corrective plan",
                    (
                        "Address blocking conditions and reassess the "
                        "business case."
                    ),
                    max(0.0, 90.0 - score),
                    False,
                )
            )

        else:
            candidates.append(
                (
                    EnterpriseRecommendationType.PAUSE,
                    "Hold the proposed action",
                    (
                        "Current evidence is insufficient for execution "
                        "or rejection."
                    ),
                    max(0.0, 100.0 - abs(50.0 - score)),
                    True,
                )
            )
            candidates.append(
                (
                    EnterpriseRecommendationType.REQUEST_INFORMATION,
                    "Request additional information",
                    (
                        "Collect evidence from missing or low-confidence "
                        "sources."
                    ),
                    max(0.0, 100.0 - confidence),
                    False,
                )
            )

        if context.requested_action:
            candidates.append(
                (
                    EnterpriseRecommendationType.MONITOR,
                    f"Review requested action: {context.requested_action}",
                    (
                        "Validate that the requested action remains "
                        "aligned with the final decision."
                    ),
                    50.0,
                    False,
                )
            )

        ordered = sorted(
            candidates,
            key=lambda item: (
                -item[3],
                item[0].value,
                item[1],
            ),
        )[: policy.maximum_recommendations]

        return tuple(
            EnterpriseDecisionRecommendation(
                recommendation_type=item[0],
                title=item[1],
                rationale=item[2],
                score=round(
                    max(0.0, min(100.0, item[3])),
                    2,
                ),
                rank=rank,
                requires_human_approval=item[4],
                metadata={
                    "case_id": context.case_id,
                    "context_id": context.context_id,
                },
            )
            for rank, item in enumerate(ordered, start=1)
        )