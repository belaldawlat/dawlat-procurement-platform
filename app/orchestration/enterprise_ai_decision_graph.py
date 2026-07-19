"""Deterministic decision graph for enterprise AI signals."""

from __future__ import annotations

from app.orchestration.enterprise_ai_decision_models import (
    AIDecisionDomain,
    AIDecisionExplanation,
    AIDecisionRequest,
    AIDecisionSeverity,
)
from app.orchestration.enterprise_ai_decision_policy import (
    EnterpriseAIDecisionPolicy,
)


class EnterpriseAIDecisionGraph:
    """Aggregate weighted signals and generate explanations."""

    def evaluate(
        self,
        request: AIDecisionRequest,
        policy: EnterpriseAIDecisionPolicy,
    ) -> tuple[float, float, tuple[AIDecisionExplanation, ...]]:
        total_weight = sum(signal.weight for signal in request.signals)

        if total_weight <= 0:
            raise ValueError(
                "AI decision signal weights must total more than zero."
            )

        weighted_score = sum(
            signal.adjusted_score()
            for signal in request.signals
        )
        score = round(weighted_score / total_weight, 2)

        dispersion = sum(
            abs(
                (
                    signal.value
                    if signal.positive
                    else 100.0 - signal.value
                )
                - score
            )
            * signal.weight
            for signal in request.signals
        ) / total_weight

        confidence = round(
            max(0.0, min(100.0, 100.0 - dispersion)),
            2,
        )

        explanations: list[AIDecisionExplanation] = []

        for signal in request.signals:
            effective_value = (
                signal.value
                if signal.positive
                else 100.0 - signal.value
            )

            if effective_value < policy.reject_threshold:
                explanations.append(
                    AIDecisionExplanation(
                        code=f"CRITICAL_{signal.signal_id.upper()}",
                        message=(
                            signal.explanation
                            or f"{signal.name} is critically below threshold."
                        ),
                        severity=AIDecisionSeverity.CRITICAL,
                        domain=signal.domain,
                        blocking=True,
                        metadata={"effective_value": effective_value},
                    )
                )
            elif effective_value < policy.manual_review_threshold:
                explanations.append(
                    AIDecisionExplanation(
                        code=f"REVIEW_{signal.signal_id.upper()}",
                        message=(
                            signal.explanation
                            or f"{signal.name} requires manual review."
                        ),
                        severity=AIDecisionSeverity.HIGH,
                        domain=signal.domain,
                        blocking=False,
                        metadata={"effective_value": effective_value},
                    )
                )
            elif effective_value >= policy.proceed_threshold:
                explanations.append(
                    AIDecisionExplanation(
                        code=f"POSITIVE_{signal.signal_id.upper()}",
                        message=(
                            signal.explanation
                            or f"{signal.name} supports proceeding."
                        ),
                        severity=AIDecisionSeverity.LOW,
                        domain=signal.domain,
                        blocking=False,
                        metadata={"effective_value": effective_value},
                    )
                )

        if not explanations:
            explanations.append(
                AIDecisionExplanation(
                    code="BALANCED_DECISION",
                    message=(
                        "Signals are balanced without material exceptions."
                    ),
                    severity=AIDecisionSeverity.MEDIUM,
                    domain=AIDecisionDomain.PROCUREMENT,
                    blocking=False,
                )
            )

        return (
            score,
            confidence,
            tuple(
                sorted(
                    explanations,
                    key=lambda item: (
                        not item.blocking,
                        item.severity.value,
                        item.code,
                    ),
                )
            ),
        )