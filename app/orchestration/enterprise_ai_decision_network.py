"""Enterprise AI decision network."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from app.orchestration.enterprise_ai_decision_graph import (
    EnterpriseAIDecisionGraph,
)
from app.orchestration.enterprise_ai_decision_models import (
    AIDecisionOutcome,
    AIDecisionRequest,
)
from app.orchestration.enterprise_ai_decision_policy import (
    EnterpriseAIDecisionPolicy,
)
from app.orchestration.enterprise_ai_decision_result import (
    EnterpriseAIDecisionResult,
)
from app.orchestration.enterprise_ai_decision_store import (
    EnterpriseAIDecisionStore,
)


class EnterpriseAIDecisionNetwork:
    """Coordinate scoring, explainability, approval and replay."""

    def __init__(
        self,
        *,
        policy: EnterpriseAIDecisionPolicy | None = None,
        graph: EnterpriseAIDecisionGraph | None = None,
        store: EnterpriseAIDecisionStore | None = None,
    ) -> None:
        self._policy = policy or EnterpriseAIDecisionPolicy(
            policy_id="default-enterprise-ai-decision",
            name="Default Enterprise AI Decision Policy",
        )
        self._graph = graph or EnterpriseAIDecisionGraph()
        self._store = store or EnterpriseAIDecisionStore()

    @property
    def policy(self) -> EnterpriseAIDecisionPolicy:
        return self._policy

    @property
    def store(self) -> EnterpriseAIDecisionStore:
        return self._store

    def decide(
        self,
        request: AIDecisionRequest,
    ) -> EnterpriseAIDecisionResult:
        if not self._policy.enabled:
            raise ValueError(
                "Enterprise AI decision policy is disabled."
            )

        score, confidence, explanations = self._graph.evaluate(
            request,
            self._policy,
        )

        blocking_count = sum(
            1 for item in explanations if item.blocking
        )

        if blocking_count > self._policy.maximum_blocking_signals:
            outcome = AIDecisionOutcome.REJECT
        elif score >= self._policy.proceed_threshold:
            outcome = AIDecisionOutcome.PROCEED
        elif score >= self._policy.manual_review_threshold:
            outcome = AIDecisionOutcome.MANUAL_REVIEW
        elif score <= self._policy.reject_threshold:
            outcome = AIDecisionOutcome.REJECT
        else:
            outcome = AIDecisionOutcome.HOLD

        requires_human_approval = (
            outcome is AIDecisionOutcome.MANUAL_REVIEW
            or (
                self._policy.require_human_approval_below_confidence
                and confidence < self._policy.minimum_confidence
            )
        )

        if (
            requires_human_approval
            and outcome is AIDecisionOutcome.PROCEED
        ):
            outcome = AIDecisionOutcome.MANUAL_REVIEW

        result = EnterpriseAIDecisionResult(
            request_id=request.request_id,
            case_id=request.case_id,
            outcome=outcome,
            score=score,
            confidence=confidence,
            explanations=explanations,
            requires_human_approval=requires_human_approval,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "signal_count": len(request.signals),
                "blocking_count": blocking_count,
                "correlation_id": request.correlation_id,
            },
        )

        self._store.append(result)
        return result

    def replay(
        self,
        request: AIDecisionRequest,
        original_request_id: str,
    ) -> EnterpriseAIDecisionResult:
        if not self._policy.allow_replay:
            raise ValueError("Enterprise AI decision replay is disabled.")

        original = self._store.get(original_request_id)
        replay_request = replace(
            request,
            request_id=uuid4().hex,
        )
        replayed = self.decide(replay_request)

        replay_result = replace(
            replayed,
            replay_of=original.request_id,
        )

        self._store._results[replay_result.request_id] = replay_result
        return replay_result


_default_enterprise_ai_decision_network = (
    EnterpriseAIDecisionNetwork()
)


def get_enterprise_ai_decision_network(
) -> EnterpriseAIDecisionNetwork:
    return _default_enterprise_ai_decision_network