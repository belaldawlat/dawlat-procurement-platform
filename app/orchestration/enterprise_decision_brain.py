"""Enterprise decision brain coordinating reasoning and confidence."""

from __future__ import annotations

from app.orchestration.enterprise_confidence_engine import (
    EnterpriseConfidenceEngine,
)
from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionOutcome,
    EnterpriseDecisionRequest,
    EnterpriseDecisionSeverity,
)
from app.orchestration.enterprise_decision_policy import (
    EnterpriseDecisionPolicy,
)
from app.orchestration.enterprise_decision_result import (
    EnterpriseDecisionResult,
)
from app.orchestration.enterprise_reasoning_engine import (
    EnterpriseReasoningEngine,
)


class EnterpriseDecisionBrain:
    """Create explainable enterprise decisions from weighted factors."""

    def __init__(
        self,
        *,
        policy: EnterpriseDecisionPolicy | None = None,
        reasoning_engine: EnterpriseReasoningEngine | None = None,
        confidence_engine: EnterpriseConfidenceEngine | None = None,
    ) -> None:
        self._policy = policy or EnterpriseDecisionPolicy(
            policy_id="default-enterprise-decision",
            name="Default Enterprise Decision Policy",
        )
        self._reasoning_engine = (
            reasoning_engine or EnterpriseReasoningEngine()
        )
        self._confidence_engine = (
            confidence_engine or EnterpriseConfidenceEngine()
        )

    @property
    def policy(self) -> EnterpriseDecisionPolicy:
        return self._policy

    def decide(
        self,
        request: EnterpriseDecisionRequest,
    ) -> EnterpriseDecisionResult:
        if not self._policy.enabled:
            raise ValueError(
                "Enterprise decision policy is disabled."
            )

        total_weight = sum(
            factor.weight
            for factor in request.factors
        )

        if total_weight <= 0:
            raise ValueError(
                "Decision factor weights must total more than zero."
            )

        score = round(
            sum(
                factor.weighted_score
                for factor in request.factors
            )
            / total_weight,
            2,
        )

        findings = self._reasoning_engine.reason(
            request.factors,
            self._policy,
        )
        confidence = self._confidence_engine.calculate(
            request.factors,
            score,
        )

        blocking_count = sum(
            1
            for finding in findings
            if finding.blocking
        )
        critical_present = any(
            finding.severity
            is EnterpriseDecisionSeverity.CRITICAL
            for finding in findings
        )

        if (
            blocking_count
            > self._policy.maximum_blocking_factors
        ):
            outcome = EnterpriseDecisionOutcome.REJECT
        elif (
            critical_present
            and self._policy.escalate_on_critical_finding
        ):
            outcome = EnterpriseDecisionOutcome.ESCALATE
        elif score >= self._policy.proceed_threshold:
            outcome = EnterpriseDecisionOutcome.PROCEED
        elif score >= self._policy.hold_threshold:
            outcome = EnterpriseDecisionOutcome.MANUAL_REVIEW
        elif score <= self._policy.reject_threshold:
            outcome = EnterpriseDecisionOutcome.REJECT
        else:
            outcome = EnterpriseDecisionOutcome.HOLD

        requires_human_approval = (
            outcome in {
                EnterpriseDecisionOutcome.MANUAL_REVIEW,
                EnterpriseDecisionOutcome.ESCALATE,
            }
            or (
                self._policy.require_human_approval_below_confidence
                and confidence < self._policy.minimum_confidence
            )
        )

        if (
            outcome is EnterpriseDecisionOutcome.PROCEED
            and requires_human_approval
        ):
            outcome = EnterpriseDecisionOutcome.MANUAL_REVIEW

        return EnterpriseDecisionResult(
            request_id=request.request_id,
            case_id=request.case_id,
            outcome=outcome,
            score=score,
            confidence=confidence,
            findings=findings,
            requires_human_approval=requires_human_approval,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "factor_count": len(request.factors),
                "blocking_count": blocking_count,
                "correlation_id": request.correlation_id,
            },
        )


_default_enterprise_decision_brain = EnterpriseDecisionBrain()


def get_enterprise_decision_brain() -> EnterpriseDecisionBrain:
    return _default_enterprise_decision_brain