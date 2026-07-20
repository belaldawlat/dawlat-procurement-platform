"""Unified Package T enterprise decision intelligence engine."""

from __future__ import annotations

from uuid import uuid4

from app.orchestration.enterprise_decision_audit import (
    EnterpriseDecisionAuditTrail,
)
from app.orchestration.enterprise_decision_confidence import (
    EnterpriseDecisionConfidence,
)
from app.orchestration.enterprise_decision_explainer import (
    EnterpriseDecisionExplainer,
)
from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionContext,
    EnterpriseDecisionOutcome,
)
from app.orchestration.enterprise_decision_policy import (
    EnterpriseDecisionEnginePolicy,
)
from app.orchestration.enterprise_decision_recommendation import (
    EnterpriseDecisionRecommendationEngine,
)
from app.orchestration.enterprise_decision_result import (
    EnterpriseDecisionEngineResult,
)
from app.orchestration.enterprise_decision_store import (
    EnterpriseDecisionStore,
)


class EnterpriseDecisionEngine:
    """Coordinate scoring, confidence, explanation, audit and recommendations."""

    def __init__(
        self,
        *,
        policy: EnterpriseDecisionEnginePolicy | None = None,
        confidence_engine: EnterpriseDecisionConfidence | None = None,
        explainer: EnterpriseDecisionExplainer | None = None,
        recommendation_engine: (
            EnterpriseDecisionRecommendationEngine | None
        ) = None,
        audit_trail: EnterpriseDecisionAuditTrail | None = None,
        decision_store: EnterpriseDecisionStore | None = None,
    ) -> None:
        self._policy = policy or EnterpriseDecisionEnginePolicy(
            policy_id="default-enterprise-decision-engine",
            name="Default Enterprise Decision Engine Policy",
        )
        self._confidence_engine = (
            confidence_engine or EnterpriseDecisionConfidence()
        )
        self._explainer = explainer or EnterpriseDecisionExplainer()
        self._recommendation_engine = (
            recommendation_engine
            or EnterpriseDecisionRecommendationEngine()
        )
        self._audit_trail = (
            audit_trail or EnterpriseDecisionAuditTrail()
        )
        self._decision_store = (
            decision_store or EnterpriseDecisionStore()
        )

    @property
    def policy(self) -> EnterpriseDecisionEnginePolicy:
        """Return the active decision policy."""

        return self._policy

    @property
    def audit_trail(self) -> EnterpriseDecisionAuditTrail:
        """Return the decision audit trail."""

        return self._audit_trail

    @property
    def decision_store(self) -> EnterpriseDecisionStore:
        """Return the decision result store."""

        return self._decision_store

    def evaluate(
        self,
        context: EnterpriseDecisionContext,
        *,
        persist: bool = True,
        actor_id: str = "enterprise-decision-engine",
    ) -> EnterpriseDecisionEngineResult:
        """Evaluate cross-module evidence and return one unified decision."""

        if not isinstance(context, EnterpriseDecisionContext):
            raise TypeError(
                "Enterprise decision engine requires an "
                "EnterpriseDecisionContext."
            )

        if not self._policy.enabled:
            raise ValueError(
                "Enterprise decision engine policy is disabled."
            )

        cleaned_actor_id = str(actor_id or "").strip()

        if not cleaned_actor_id:
            raise ValueError("Decision actor ID is required.")

        score = self._calculate_score(context)
        confidence_result = self._confidence_engine.calculate(
            context,
            self._policy,
        )
        outcome = self._resolve_outcome(
            context=context,
            score=score,
            confidence=confidence_result.confidence,
            distinct_source_count=(
                confidence_result.distinct_source_count
            ),
        )

        explanation = self._explainer.explain(
            context=context,
            outcome=outcome,
            score=score,
            confidence=confidence_result,
            policy=self._policy,
        )
        recommendations = self._recommendation_engine.generate(
            context=context,
            outcome=outcome,
            score=score,
            confidence=confidence_result.confidence,
            policy=self._policy,
        )

        requires_human_approval = self._requires_human_approval(
            context=context,
            outcome=outcome,
            confidence=confidence_result.confidence,
            recommendations=recommendations,
        )

        decision_id = uuid4().hex
        audit_reference = ""

        if self._policy.audit_required:
            audit_record = self._audit_trail.append(
                decision_id=decision_id,
                case_id=context.case_id,
                action="enterprise_decision_evaluated",
                actor_id=cleaned_actor_id,
                payload={
                    "context_id": context.context_id,
                    "outcome": outcome.value,
                    "score": score,
                    "confidence": confidence_result.confidence,
                    "requires_human_approval": (
                        requires_human_approval
                    ),
                    "recommendation_count": len(recommendations),
                    "source_references": list(
                        explanation.source_references
                    ),
                },
            )
            audit_reference = audit_record.audit_id

        result = EnterpriseDecisionEngineResult(
            decision_id=decision_id,
            context_id=context.context_id,
            case_id=context.case_id,
            outcome=outcome,
            score=score,
            confidence=confidence_result.confidence,
            recommendations=recommendations,
            explanation=explanation.summary,
            requires_human_approval=requires_human_approval,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            audit_reference=audit_reference,
            metadata={
                "correlation_id": context.correlation_id,
                "requested_action": context.requested_action,
                "evidence_count": confidence_result.evidence_count,
                "distinct_source_count": (
                    confidence_result.distinct_source_count
                ),
                "blocking_evidence_count": (
                    confidence_result.blocking_evidence_count
                ),
                "average_evidence_confidence": (
                    confidence_result.average_evidence_confidence
                ),
                "score_dispersion": (
                    confidence_result.score_dispersion
                ),
                "source_coverage_factor": (
                    confidence_result.source_coverage_factor
                ),
                "primary_reason": explanation.primary_reason,
                "supporting_reasons": list(
                    explanation.supporting_reasons
                ),
                "warnings": list(explanation.warnings),
                "source_references": list(
                    explanation.source_references
                ),
            },
        )

        if persist:
            self._decision_store.create(result)

        return result

    def decide(
        self,
        context: EnterpriseDecisionContext,
        *,
        persist: bool = True,
        actor_id: str = "enterprise-decision-engine",
    ) -> EnterpriseDecisionEngineResult:
        """Compatibility alias for evaluate."""

        return self.evaluate(
            context,
            persist=persist,
            actor_id=actor_id,
        )

    def get_decision(
        self,
        decision_id: str,
    ) -> EnterpriseDecisionEngineResult:
        """Return one persisted decision."""

        return self._decision_store.get(decision_id)

    def list_case_decisions(
        self,
        case_id: str,
    ) -> tuple[EnterpriseDecisionEngineResult, ...]:
        """Return persisted decision history for one case."""

        return self._decision_store.list_by_case(case_id)

    @staticmethod
    def _calculate_score(
        context: EnterpriseDecisionContext,
    ) -> float:
        total_weight = sum(
            max(evidence.confidence, 1.0)
            for evidence in context.evidences
        )

        if total_weight <= 0:
            raise ValueError(
                "Decision evidence confidence must total more than zero."
            )

        score = sum(
            evidence.score * max(evidence.confidence, 1.0)
            for evidence in context.evidences
        ) / total_weight

        return round(max(0.0, min(100.0, score)), 2)

    def _resolve_outcome(
        self,
        *,
        context: EnterpriseDecisionContext,
        score: float,
        confidence: float,
        distinct_source_count: int,
    ) -> EnterpriseDecisionOutcome:
        blocking_present = any(
            evidence.blocking
            for evidence in context.evidences
        )

        if (
            blocking_present
            and self._policy.reject_on_blocking_evidence
        ):
            return EnterpriseDecisionOutcome.REJECT

        if score <= self._policy.reject_threshold:
            return EnterpriseDecisionOutcome.REJECT

        source_requirement_met = (
            not self._policy.require_multi_source_evidence
            or distinct_source_count
            >= self._policy.minimum_distinct_sources
        )
        confidence_requirement_met = (
            confidence >= self._policy.minimum_confidence
        )

        if (
            score >= self._policy.proceed_threshold
            and source_requirement_met
            and confidence_requirement_met
        ):
            return EnterpriseDecisionOutcome.PROCEED

        if (
            score >= self._policy.review_threshold
            or not source_requirement_met
            or not confidence_requirement_met
        ):
            return EnterpriseDecisionOutcome.MANUAL_REVIEW

        return EnterpriseDecisionOutcome.HOLD

    def _requires_human_approval(
        self,
        *,
        context: EnterpriseDecisionContext,
        outcome: EnterpriseDecisionOutcome,
        confidence: float,
        recommendations: tuple[object, ...],
    ) -> bool:
        if outcome in {
            EnterpriseDecisionOutcome.MANUAL_REVIEW,
            EnterpriseDecisionOutcome.ESCALATE,
            EnterpriseDecisionOutcome.REJECT,
        }:
            return True

        if confidence < self._policy.minimum_confidence:
            return True

        if (
            context.requested_action
            and self._policy.require_human_approval_for_external_actions
        ):
            return True

        return any(
            bool(
                getattr(
                    recommendation,
                    "requires_human_approval",
                    False,
                )
            )
            for recommendation in recommendations
        )


_default_enterprise_decision_engine = EnterpriseDecisionEngine()


def get_enterprise_decision_engine() -> EnterpriseDecisionEngine:
    """Return the process-local default Package T decision engine."""

    return _default_enterprise_decision_engine