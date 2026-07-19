"""Tests for Phase 21 Package K enterprise control tower."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestration import (
    ControlAction,
    ControlHealth,
    ControlPriority,
    EnterpriseControlPolicy,
    EnterpriseControlSnapshot,
    EnterpriseControlTower,
)


def healthy_snapshot() -> EnterpriseControlSnapshot:
    return EnterpriseControlSnapshot(
        case_id="CASE-100",
        procurement_status="shipment_handoff",
        approval_satisfied=True,
        execution_allowed=True,
        compensation_required=False,
        autonomous_confidence=95,
        decision_score=95,
        supplier_risk_score=20,
        shipment_delay_days=0,
        inventory_days_remaining=60,
        buyer_payment_cleared=True,
        documents_complete=True,
        opportunity_score=60,
        margin_percentage=20,
    )


def test_policy_validates_risk_thresholds() -> None:
    with pytest.raises(ValueError):
        EnterpriseControlPolicy(
            policy_id="invalid",
            name="Invalid",
            maximum_supplier_risk_score=90,
            critical_supplier_risk_score=80,
        )


def test_healthy_snapshot_is_healthy() -> None:
    result = EnterpriseControlTower().evaluate(
        healthy_snapshot()
    )

    assert result.health is ControlHealth.HEALTHY
    assert result.execution_blocked is False
    assert result.health_score >= 75


def test_missing_payment_is_critical_and_blocking() -> None:
    snapshot = replace(
        healthy_snapshot(),
        buyer_payment_cleared=False,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert result.health is ControlHealth.CRITICAL
    assert result.execution_blocked is True
    assert any(
        alert.action is ControlAction.SECURE_PAYMENT
        for alert in result.alerts
    )


def test_missing_documents_blocks_execution() -> None:
    snapshot = replace(
        healthy_snapshot(),
        documents_complete=False,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert result.execution_blocked is True
    assert any(
        alert.action is ControlAction.COMPLETE_DOCUMENTS
        for alert in result.alerts
    )


def test_compensation_required_is_critical() -> None:
    snapshot = replace(
        healthy_snapshot(),
        compensation_required=True,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert result.health is ControlHealth.CRITICAL
    assert any(
        alert.action is ControlAction.START_COMPENSATION
        for alert in result.alerts
    )


def test_pending_approval_blocks_execution() -> None:
    snapshot = replace(
        healthy_snapshot(),
        approval_satisfied=False,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert result.execution_blocked is True
    assert any(
        alert.action is ControlAction.REQUEST_APPROVAL
        for alert in result.alerts
    )


def test_execution_not_allowed_creates_pause_alert() -> None:
    snapshot = replace(
        healthy_snapshot(),
        execution_allowed=False,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert any(
        alert.action is ControlAction.PAUSE_EXECUTION
        for alert in result.alerts
    )


def test_low_decision_score_blocks_execution() -> None:
    snapshot = replace(
        healthy_snapshot(),
        decision_score=40,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert result.execution_blocked is True
    assert any(
        alert.code == "LOW_DECISION_SCORE"
        for alert in result.alerts
    )


def test_critical_supplier_risk_escalates() -> None:
    snapshot = replace(
        healthy_snapshot(),
        supplier_risk_score=90,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert result.health is ControlHealth.CRITICAL
    assert any(
        alert.action is ControlAction.ESCALATE
        for alert in result.alerts
    )


def test_critical_shipment_delay_is_flagged() -> None:
    snapshot = replace(
        healthy_snapshot(),
        shipment_delay_days=12,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert any(
        alert.action is ControlAction.EXPEDITE_SHIPMENT
        and alert.priority is ControlPriority.CRITICAL
        for alert in result.alerts
    )


def test_low_inventory_recommends_replenishment() -> None:
    snapshot = replace(
        healthy_snapshot(),
        inventory_days_remaining=10,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert any(
        alert.action is ControlAction.REPLENISH_INVENTORY
        for alert in result.alerts
    )


def test_high_value_opportunity_is_visible() -> None:
    snapshot = replace(
        healthy_snapshot(),
        opportunity_score=90,
        margin_percentage=25,
    )

    result = EnterpriseControlTower().evaluate(snapshot)

    assert any(
        alert.code == "HIGH_VALUE_OPPORTUNITY"
        for alert in result.alerts
    )


def test_metrics_include_core_domains() -> None:
    result = EnterpriseControlTower().evaluate(
        healthy_snapshot()
    )

    metric_ids = {
        metric.metric_id
        for metric in result.metrics
    }

    assert {
        "decision-score",
        "autonomous-confidence",
        "supplier-risk",
        "shipment-delay",
        "opportunity-score",
        "inventory-coverage",
    }.issubset(metric_ids)


def test_result_serialises_safely() -> None:
    result = EnterpriseControlTower().evaluate(
        healthy_snapshot()
    )

    payload = result.as_dict()

    assert payload["case_id"] == "CASE-100"
    assert payload["health"] == "healthy"
    assert payload["metrics"]
    assert payload["alerts"]


def test_disabled_policy_rejects_execution() -> None:
    tower = EnterpriseControlTower(
        EnterpriseControlPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        tower.evaluate(healthy_snapshot())