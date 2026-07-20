"""Tests for Phase 21 Package T enterprise decision intelligence."""

from __future__ import annotations

import pytest

from app.orchestration import (
    EnterpriseDecisionAuditTrail,
    EnterpriseDecisionContext,
    EnterpriseDecisionEngine,
    EnterpriseDecisionEnginePolicy,
    EnterpriseDecisionEvidence,
    EnterpriseDecisionOutcome,
    EnterpriseDecisionRegistry,
    EnterpriseDecisionSource,
    EnterpriseDecisionStore,
    EnterpriseRecommendationType,
    WorkflowIntegrityError,
)


def evidence(
    evidence_id: str,
    source: EnterpriseDecisionSource,
    score: float,
    *,
    confidence: float = 90.0,
    blocking: bool = False,
) -> EnterpriseDecisionEvidence:
    return EnterpriseDecisionEvidence(
        evidence_id=evidence_id,
        source=source,
        reference_id=f"REF-{evidence_id}",
        score=score,
        confidence=confidence,
        summary=f"Evidence {evidence_id}",
        blocking=blocking,
    )


def context(
    *items: EnterpriseDecisionEvidence,
    requested_action: str = "",
) -> EnterpriseDecisionContext:
    return EnterpriseDecisionContext(
        context_id="CTX-100",
        case_id="CASE-100",
        evidences=tuple(items),
        correlation_id="CORR-100",
        requested_action=requested_action,
    )


def test_policy_validates_threshold_order() -> None:
    with pytest.raises(ValueError):
        EnterpriseDecisionEnginePolicy(
            policy_id="invalid",
            name="Invalid",
            proceed_threshold=50,
            review_threshold=80,
        )


def test_context_requires_evidence() -> None:
    with pytest.raises(ValueError):
        EnterpriseDecisionContext(
            context_id="CTX",
            case_id="CASE",
            evidences=(),
        )


def test_high_multi_source_evidence_proceeds() -> None:
    result = EnterpriseDecisionEngine().evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                95,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                90,
            ),
        )
    )

    assert result.outcome is EnterpriseDecisionOutcome.PROCEED
    assert result.score >= 90
    assert result.confidence >= 75


def test_single_source_requires_manual_review() -> None:
    result = EnterpriseDecisionEngine().evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                95,
            )
        ),
        persist=False,
    )

    assert result.outcome is EnterpriseDecisionOutcome.MANUAL_REVIEW
    assert result.requires_human_approval is True


def test_blocking_evidence_rejects() -> None:
    result = EnterpriseDecisionEngine().evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.RISK,
                90,
                blocking=True,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.PLANNING,
                95,
            ),
        ),
        persist=False,
    )

    assert result.outcome is EnterpriseDecisionOutcome.REJECT
    assert result.requires_human_approval is True


def test_low_score_rejects() -> None:
    result = EnterpriseDecisionEngine().evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.RISK,
                20,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.COMPLIANCE
                if hasattr(EnterpriseDecisionSource, "COMPLIANCE")
                else EnterpriseDecisionSource.PROCUREMENT,
                30,
            ),
        ),
        persist=False,
    )

    assert result.outcome is EnterpriseDecisionOutcome.REJECT


def test_mid_score_holds_or_reviews() -> None:
    policy = EnterpriseDecisionEnginePolicy(
        policy_id="mid",
        name="Mid",
        proceed_threshold=85,
        review_threshold=65,
        reject_threshold=30,
        minimum_confidence=50,
        require_multi_source_evidence=False,
    )
    result = EnterpriseDecisionEngine(
        policy=policy
    ).evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                50,
            )
        ),
        persist=False,
    )

    assert result.outcome is EnterpriseDecisionOutcome.HOLD


def test_requested_external_action_requires_approval() -> None:
    result = EnterpriseDecisionEngine().evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                95,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                95,
            ),
            requested_action="pay_supplier",
        ),
        persist=False,
    )

    assert result.outcome is EnterpriseDecisionOutcome.PROCEED
    assert result.requires_human_approval is True


def test_recommendations_are_ranked() -> None:
    result = EnterpriseDecisionEngine().evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                95,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                90,
            ),
        ),
        persist=False,
    )

    assert result.recommendations
    assert [
        item.rank
        for item in result.recommendations
    ] == list(range(1, len(result.recommendations) + 1))


def test_proceed_recommendation_contains_execute() -> None:
    result = EnterpriseDecisionEngine().evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                95,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                90,
            ),
        ),
        persist=False,
    )

    assert any(
        item.recommendation_type
        is EnterpriseRecommendationType.EXECUTE
        for item in result.recommendations
    )


def test_explanation_is_generated() -> None:
    result = EnterpriseDecisionEngine().evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                90,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                85,
            ),
        ),
        persist=False,
    )

    assert "score" in result.explanation
    assert result.metadata["primary_reason"]


def test_decision_is_persisted_by_default() -> None:
    store = EnterpriseDecisionStore()
    engine = EnterpriseDecisionEngine(
        decision_store=store
    )

    result = engine.evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                90,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                90,
            ),
        )
    )

    assert engine.get_decision(result.decision_id) == result


def test_case_decision_history_is_available() -> None:
    store = EnterpriseDecisionStore()
    engine = EnterpriseDecisionEngine(
        decision_store=store
    )

    first = engine.evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                90,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                90,
            ),
        )
    )

    second_context = EnterpriseDecisionContext(
        context_id="CTX-200",
        case_id="CASE-100",
        evidences=(
            evidence(
                "E3",
                EnterpriseDecisionSource.PLANNING,
                80,
            ),
            evidence(
                "E4",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                80,
            ),
        ),
    )
    second = engine.evaluate(second_context)

    assert engine.list_case_decisions("CASE-100") == (
        first,
        second,
    )


def test_store_rejects_duplicate_create() -> None:
    store = EnterpriseDecisionStore()
    engine = EnterpriseDecisionEngine(
        decision_store=store
    )

    result = engine.evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                90,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                90,
            ),
        )
    )

    with pytest.raises(WorkflowIntegrityError):
        store.create(result)


def test_registry_rejects_duplicate_evaluator() -> None:
    registry = EnterpriseDecisionRegistry()
    registry.register("default", lambda value: value)

    with pytest.raises(WorkflowIntegrityError):
        registry.register("default", lambda value: value)


def test_audit_record_is_created_and_valid() -> None:
    audit = EnterpriseDecisionAuditTrail()
    engine = EnterpriseDecisionEngine(
        audit_trail=audit
    )

    result = engine.evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                90,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                90,
            ),
        ),
        persist=False,
        actor_id="user-1",
    )

    records = audit.list_records(
        decision_id=result.decision_id
    )

    assert len(records) == 1
    assert records[0].actor_id == "user-1"
    assert audit.verify_integrity() is True


def test_result_serialises() -> None:
    result = EnterpriseDecisionEngine().evaluate(
        context(
            evidence(
                "E1",
                EnterpriseDecisionSource.PLANNING,
                90,
            ),
            evidence(
                "E2",
                EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                90,
            ),
        ),
        persist=False,
    )

    payload = result.as_dict()

    assert payload["case_id"] == "CASE-100"
    assert payload["recommendations"]
    assert payload["audit_reference"]


def test_disabled_policy_rejects_evaluation() -> None:
    engine = EnterpriseDecisionEngine(
        policy=EnterpriseDecisionEnginePolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        engine.evaluate(
            context(
                evidence(
                    "E1",
                    EnterpriseDecisionSource.PLANNING,
                    90,
                ),
                evidence(
                    "E2",
                    EnterpriseDecisionSource.KNOWLEDGE_GRAPH,
                    90,
                ),
            )
        )