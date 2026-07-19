"""Tests for Phase 21 Package O enterprise AI decision network."""

from __future__ import annotations

import pytest

from app.orchestration import (
    AIDecisionDomain,
    AIDecisionOutcome,
    AIDecisionRequest,
    AIDecisionSignal,
    EnterpriseAIDecisionNetwork,
    EnterpriseAIDecisionPolicy,
    EnterpriseAIDecisionRegistry,
    EnterpriseAIDecisionStore,
    WorkflowIntegrityError,
)


def signal(
    signal_id: str,
    value: float,
    *,
    weight: float = 1.0,
    positive: bool = True,
    domain: AIDecisionDomain = AIDecisionDomain.PROCUREMENT,
) -> AIDecisionSignal:
    return AIDecisionSignal(
        signal_id=signal_id,
        domain=domain,
        name=signal_id.replace("-", " ").title(),
        value=value,
        weight=weight,
        positive=positive,
    )


def request(*signals: AIDecisionSignal) -> AIDecisionRequest:
    return AIDecisionRequest(
        case_id="CASE-100",
        signals=tuple(signals),
        correlation_id="CORR-100",
    )


def test_policy_validates_threshold_order() -> None:
    with pytest.raises(ValueError):
        EnterpriseAIDecisionPolicy(
            policy_id="invalid",
            name="Invalid",
            proceed_threshold=50,
            manual_review_threshold=80,
        )


def test_signal_validates_weight() -> None:
    with pytest.raises(ValueError):
        signal("risk", 50, weight=1.5)


def test_request_requires_signals() -> None:
    with pytest.raises(ValueError):
        AIDecisionRequest(
            case_id="CASE-100",
            signals=(),
        )


def test_high_scores_proceed() -> None:
    result = EnterpriseAIDecisionNetwork().decide(
        request(
            signal("quality", 95, weight=0.5),
            signal("compliance", 90, weight=0.5),
        )
    )

    assert result.outcome is AIDecisionOutcome.PROCEED
    assert result.score >= 80


def test_low_signal_rejects() -> None:
    result = EnterpriseAIDecisionNetwork().decide(
        request(
            signal("compliance", 20),
        )
    )

    assert result.outcome is AIDecisionOutcome.REJECT
    assert result.blocking_explanations


def test_mid_score_requires_review() -> None:
    result = EnterpriseAIDecisionNetwork().decide(
        request(
            signal("quality", 70),
        )
    )

    assert result.outcome is AIDecisionOutcome.MANUAL_REVIEW
    assert result.requires_human_approval is True


def test_negative_signal_is_inverted() -> None:
    result = EnterpriseAIDecisionNetwork().decide(
        request(
            signal(
                "supplier-risk",
                10,
                positive=False,
                domain=AIDecisionDomain.RISK,
            )
        )
    )

    assert result.score == 90
    assert result.outcome is AIDecisionOutcome.PROCEED


def test_weighted_scoring_is_deterministic() -> None:
    result = EnterpriseAIDecisionNetwork().decide(
        request(
            signal("quality", 100, weight=0.75),
            signal("cost", 40, weight=0.25),
        )
    )

    assert result.score == 85


def test_low_confidence_forces_review() -> None:
    network = EnterpriseAIDecisionNetwork(
        policy=EnterpriseAIDecisionPolicy(
            policy_id="strict-confidence",
            name="Strict Confidence",
            minimum_confidence=95,
        )
    )

    result = network.decide(
        request(
            signal("quality", 100, weight=0.5),
            signal("cost", 60, weight=0.5),
        )
    )

    assert result.outcome is AIDecisionOutcome.MANUAL_REVIEW


def test_result_is_persisted() -> None:
    store = EnterpriseAIDecisionStore()
    network = EnterpriseAIDecisionNetwork(store=store)

    result = network.decide(
        request(signal("quality", 90))
    )

    assert store.get(result.request_id) == result


def test_store_rejects_duplicate_result() -> None:
    store = EnterpriseAIDecisionStore()
    network = EnterpriseAIDecisionNetwork(store=store)
    result = network.decide(
        request(signal("quality", 90))
    )

    with pytest.raises(WorkflowIntegrityError):
        store.append(result)


def test_replay_creates_new_result() -> None:
    network = EnterpriseAIDecisionNetwork()
    original_request = request(signal("quality", 90))
    original = network.decide(original_request)

    replayed = network.replay(
        request(signal("quality", 95)),
        original.request_id,
    )

    assert replayed.request_id != original.request_id
    assert replayed.replay_of == original.request_id


def test_replay_can_be_disabled() -> None:
    network = EnterpriseAIDecisionNetwork(
        policy=EnterpriseAIDecisionPolicy(
            policy_id="no-replay",
            name="No Replay",
            allow_replay=False,
        )
    )
    original = network.decide(
        request(signal("quality", 90))
    )

    with pytest.raises(ValueError):
        network.replay(
            request(signal("quality", 90)),
            original.request_id,
        )


def test_registry_rejects_duplicate_strategy() -> None:
    registry = EnterpriseAIDecisionRegistry()
    registry.register("strategy", lambda value: value)

    with pytest.raises(WorkflowIntegrityError):
        registry.register("strategy", lambda value: value)


def test_result_serialises() -> None:
    result = EnterpriseAIDecisionNetwork().decide(
        request(signal("quality", 90))
    )

    payload = result.as_dict()

    assert payload["case_id"] == "CASE-100"
    assert payload["outcome"] == "proceed"
    assert payload["explanations"]


def test_disabled_policy_rejects_decision() -> None:
    network = EnterpriseAIDecisionNetwork(
        policy=EnterpriseAIDecisionPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        network.decide(
            request(signal("quality", 90))
        )