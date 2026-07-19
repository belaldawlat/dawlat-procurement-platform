"""Tests for Phase 21 Package L enterprise command center."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.orchestration import (
    CommandCenterHealth,
    EnterpriseCommandCenter,
    EnterpriseCommandPolicy,
    EnterpriseCommandSnapshot,
    ExecutiveAction,
)


def healthy_snapshot() -> EnterpriseCommandSnapshot:
    return EnterpriseCommandSnapshot(
        portfolio_id="PORTFOLIO-100",
        active_procurements=10,
        blocked_procurements=0,
        pending_approvals=0,
        delayed_shipments=0,
        critical_risks=0,
        compensation_cases=0,
        low_inventory_items=0,
        high_value_opportunities=0,
        procurement_value=1_000_000,
        financial_exposure=200_000,
        average_decision_score=95,
        average_autonomous_confidence=92,
        payment_clearance_rate=100,
        document_completeness_rate=100,
        on_time_shipment_rate=95,
    )


def test_policy_validates_blocked_thresholds() -> None:
    with pytest.raises(ValueError):
        EnterpriseCommandPolicy(
            policy_id="invalid",
            name="Invalid",
            blocked_procurement_warning_count=5,
            blocked_procurement_critical_count=3,
        )


def test_healthy_portfolio_is_healthy() -> None:
    result = EnterpriseCommandCenter().evaluate(
        healthy_snapshot()
    )

    assert result.health is CommandCenterHealth.HEALTHY
    assert result.execution_paused is False


def test_critical_blockage_pauses_execution() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            blocked_procurements=5,
        )
    )

    assert result.execution_paused is True
    assert any(
        item.action is ExecutiveAction.PAUSE_EXECUTION
        for item in result.directives
    )


def test_approval_backlog_is_flagged() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            pending_approvals=5,
        )
    )

    assert any(
        item.action is ExecutiveAction.REQUEST_APPROVAL
        for item in result.directives
    )


def test_critical_risk_escalates() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            critical_risks=1,
        )
    )

    assert result.health is CommandCenterHealth.CRITICAL
    assert any(
        item.action is ExecutiveAction.ESCALATE
        for item in result.directives
    )


def test_compensation_case_pauses_execution() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            compensation_cases=1,
        )
    )

    assert result.execution_paused is True
    assert any(
        item.action is ExecutiveAction.START_COMPENSATION
        for item in result.directives
    )


def test_delayed_shipments_are_escalated() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            delayed_shipments=3,
        )
    )

    assert any(
        item.action is ExecutiveAction.EXPEDITE_SHIPMENT
        for item in result.directives
    )


def test_low_inventory_is_visible() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            low_inventory_items=2,
        )
    )

    assert any(
        item.action is ExecutiveAction.REPLENISH_INVENTORY
        for item in result.directives
    )


def test_low_payment_clearance_is_critical() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            payment_clearance_rate=80,
        )
    )

    assert result.execution_paused is True
    assert any(
        item.action is ExecutiveAction.SECURE_PAYMENT
        for item in result.directives
    )


def test_low_document_completeness_blocks() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            document_completeness_rate=85,
        )
    )

    assert result.execution_paused is True
    assert any(
        item.action is ExecutiveAction.COMPLETE_DOCUMENTS
        for item in result.directives
    )


def test_high_financial_exposure_blocks() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            financial_exposure=700_000,
        )
    )

    assert result.execution_paused is True
    assert any(
        item.code == "HIGH_FINANCIAL_EXPOSURE"
        for item in result.directives
    )


def test_high_value_opportunities_are_prioritised() -> None:
    result = EnterpriseCommandCenter().evaluate(
        replace(
            healthy_snapshot(),
            high_value_opportunities=3,
        )
    )

    assert any(
        item.action is ExecutiveAction.PRIORITISE_OPPORTUNITY
        for item in result.directives
    )


def test_kpis_include_financial_exposure() -> None:
    result = EnterpriseCommandCenter().evaluate(
        healthy_snapshot()
    )

    ids = {kpi.kpi_id for kpi in result.kpis}

    assert "financial-exposure-ratio" in ids
    assert "payment-clearance-rate" in ids


def test_result_serialises() -> None:
    result = EnterpriseCommandCenter().evaluate(
        healthy_snapshot()
    )

    payload = result.as_dict()

    assert payload["portfolio_id"] == "PORTFOLIO-100"
    assert payload["kpis"]
    assert payload["directives"]


def test_disabled_policy_rejects_execution() -> None:
    center = EnterpriseCommandCenter(
        EnterpriseCommandPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        center.evaluate(healthy_snapshot())