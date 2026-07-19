"""Tests for Phase 21 Package Q enterprise decision brain."""

from __future__ import annotations

import pytest

from app.orchestration import (
    EnterpriseDecisionBrain,
    EnterpriseDecisionDomain,
    EnterpriseDecisionFactor,
    EnterpriseDecisionOutcome,
    EnterpriseDecisionPolicy,
    EnterpriseDecisionRegistry,
    EnterpriseDecisionRequest,
    WorkflowIntegrityError,
)


def factor(
    factor_id: str,
    score: float,
    *,
    weight: float = 1.0,
    positive: bool = True,
    blocking: bool = False,
    domain: EnterpriseDecisionDomain = (
        EnterpriseDecisionDomain.PROCUREMENT
    ),
) -> EnterpriseDecisionFactor:
    return EnterpriseDecisionFactor(
        factor_id=factor_id,
        name=factor_id.replace("-", " ").title(),
        domain=domain,
        score=score,
        weight=weight,
        positive=positive,
        blocking=blocking,
    )


def request(
    *factors: EnterpriseDecisionFactor,
) -> EnterpriseDecisionRequest:
    return EnterpriseDecisionRequest(
        case_id="CASE-100",
        factors=tuple(factors),
        correlation_id="CORR-100",
    )


def test_policy_validates_threshold_order() -> None:
    with pytest.raises(ValueError):
        EnterpriseDecisionPolicy(
            policy_id="invalid",
            name="Invalid",
            proceed_threshold=50,
            hold_threshold=80,
        )


def test_factor_validates_weight() -> None:
    with pytest.raises(ValueError):
        factor("quality", 90, weight=1.2)


def test_request_requires_factors() -> None:
    with pytest.raises(ValueError):
        EnterpriseDecisionRequest(
            case_id="CASE-100",
            factors=(),
        )


def test_high_scores_proceed() -> None:
    result = EnterpriseDecisionBrain().decide(
        request(
            factor("quality", 95, weight=0.5),
            factor("compliance", 90, weight=0.5),
        )
    )

    assert result.outcome is EnterpriseDecisionOutcome.PROCEED
    assert result.score >= 80


def test_blocking_factor_rejects() -> None:
    result = EnterpriseDecisionBrain().decide(
        request(
            factor(
                "payment",
                90,
                blocking=True,
                domain=EnterpriseDecisionDomain.FINANCIAL,
            )
        )
    )

    assert result.outcome is EnterpriseDecisionOutcome.REJECT
    assert result.blocking_findings


def test_critical_factor_escalates_when_allowed() -> None:
    policy = EnterpriseDecisionPolicy(
        policy_id="escalate",
        name="Escalate",
        maximum_blocking_factors=1,
        escalate_on_critical_finding=True,
    )
    result = EnterpriseDecisionBrain(
        policy=policy
    ).decide(
        request(
            factor("risk", 20)
        )
    )

    assert result.outcome is EnterpriseDecisionOutcome.ESCALATE
    assert result.requires_human_approval is True


def test_mid_score_requires_manual_review() -> None:
    result = EnterpriseDecisionBrain().decide(
        request(
            factor("quality", 70)
        )
    )

    assert result.outcome is EnterpriseDecisionOutcome.MANUAL_REVIEW


def test_low_noncritical_score_holds() -> None:
    policy = EnterpriseDecisionPolicy(
        policy_id="hold",
        name="Hold",
        reject_threshold=20,
        hold_threshold=55,
        proceed_threshold=80,
        escalate_on_critical_finding=False,
        maximum_blocking_factors=10,
    )
    result = EnterpriseDecisionBrain(
        policy=policy
    ).decide(
        request(
            factor("quality", 40)
        )
    )

    assert result.outcome is EnterpriseDecisionOutcome.HOLD


def test_negative_factor_is_inverted() -> None:
    result = EnterpriseDecisionBrain().decide(
        request(
            factor(
                "supplier-risk",
                10,
                positive=False,
                domain=EnterpriseDecisionDomain.RISK,
            )
        )
    )

    assert result.score == 90
    assert result.outcome is EnterpriseDecisionOutcome.PROCEED


def test_weighted_scoring_is_deterministic() -> None:
    result = EnterpriseDecisionBrain().decide(
        request(
            factor("quality", 100, weight=0.75),
            factor("cost", 40, weight=0.25),
        )
    )

    assert result.score == 85


def test_low_confidence_forces_manual_review() -> None:
    brain = EnterpriseDecisionBrain(
        policy=EnterpriseDecisionPolicy(
            policy_id="strict-confidence",
            name="Strict Confidence",
            minimum_confidence=95,
        )
    )

    result = brain.decide(
        request(
            factor("quality", 100, weight=0.5),
            factor("cost", 60, weight=0.5),
        )
    )

    assert result.outcome is EnterpriseDecisionOutcome.MANUAL_REVIEW


def test_findings_are_explainable() -> None:
    result = EnterpriseDecisionBrain().decide(
        request(
            factor("quality", 90)
        )
    )

    assert result.findings
    assert result.findings[0].message


def test_registry_rejects_duplicate_strategy() -> None:
    registry = EnterpriseDecisionRegistry()
    registry.register("strategy", lambda value: value)

    with pytest.raises(WorkflowIntegrityError):
        registry.register("strategy", lambda value: value)


def test_result_serialises() -> None:
    result = EnterpriseDecisionBrain().decide(
        request(
            factor("quality", 90)
        )
    )

    payload = result.as_dict()

    assert payload["case_id"] == "CASE-100"
    assert payload["outcome"] == "proceed"
    assert payload["findings"]


def test_disabled_policy_rejects_decision() -> None:
    brain = EnterpriseDecisionBrain(
        policy=EnterpriseDecisionPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        brain.decide(
            request(
                factor("quality", 90)
            )
        )