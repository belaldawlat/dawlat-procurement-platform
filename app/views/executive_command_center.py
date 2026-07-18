"""Executive Command Center view."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd
import streamlit as st

from services.dashboard_intelligence.command_center_service import (
    CommandCenterRequest,
    ExecutiveCommandCenterSnapshot,
    get_command_center_service,
)


PAGE_TITLE = "Executive Command Center"


def render(
    request: CommandCenterRequest | None = None,
) -> None:
    """Render the enterprise executive command center."""

    st.title(PAGE_TITLE)
    st.caption(
        "Unified executive visibility across procurement, finance, risk, "
        "pipeline performance and platform health."
    )

    snapshot = get_command_center_service().build(
        request or CommandCenterRequest()
    )

    _render_header(snapshot)
    _render_kpis(snapshot)
    _render_executive_status(snapshot)
    _render_action_queue(snapshot)
    _render_pipeline(snapshot)
    _render_risk_and_finance(snapshot)
    _render_health(snapshot)
    _render_audit_footer(snapshot)


def _render_header(
    snapshot: ExecutiveCommandCenterSnapshot,
) -> None:
    left, middle, right = st.columns([2, 1, 1])

    with left:
        st.subheader("Enterprise Decision Surface")

    with middle:
        st.metric(
            "Executive Attention",
            "Required"
            if snapshot.executive_attention_required
            else "Normal",
        )

    with right:
        st.metric(
            "Execution Gate",
            "Open"
            if snapshot.transaction_execution_allowed
            else "Restricted",
        )


def _render_kpis(
    snapshot: ExecutiveCommandCenterSnapshot,
) -> None:
    kpis = snapshot.kpis

    row_one = st.columns(4)
    row_one[0].metric(
        "Pipeline Value",
        _money(kpis.procurement_pipeline_value),
    )
    row_one[1].metric(
        "Expected Revenue",
        _money(kpis.expected_revenue),
    )
    row_one[2].metric(
        "Protected Gross Profit",
        _money(kpis.protected_gross_profit),
    )
    row_one[3].metric(
        "Protected Margin",
        f"{kpis.protected_margin_percent:.2f}%",
    )

    row_two = st.columns(4)
    row_two[0].metric(
        "Cleared Buyer Funds",
        _money(kpis.cleared_buyer_funds),
    )
    row_two[1].metric(
        "Capital at Risk",
        _money(kpis.capital_at_risk),
    )
    row_two[2].metric(
        "AI Confidence",
        f"{kpis.ai_confidence_index}/100",
    )
    row_two[3].metric(
        "Enterprise Health",
        f"{kpis.enterprise_health_score}/100",
    )


def _render_executive_status(
    snapshot: ExecutiveCommandCenterSnapshot,
) -> None:
    st.subheader("Executive Status")

    left, right = st.columns(2)

    with left:
        st.markdown("**Executive warnings**")
        warnings = list(snapshot.kpis.warnings)
        warnings.extend(snapshot.financial_exposure.warnings)
        warnings.extend(snapshot.risk_posture.warnings)

        if warnings:
            for warning in dict.fromkeys(warnings):
                st.warning(warning)
        else:
            st.success("No executive warnings are currently active.")

    with right:
        st.markdown("**Control posture**")
        posture = {
            "Risk execution allowed": snapshot.risk_posture.execution_allowed,
            "Dashboard rendering allowed": (
                snapshot.platform_health.dashboard_rendering_allowed
            ),
            "Financial exposure protected": (
                snapshot.financial_exposure.unprotected_exposure == 0
            ),
            "Pipeline free of blockers": (
                snapshot.pipeline.blocked_cases == 0
            ),
        }
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Control": key,
                        "Status": "Pass" if value else "Restricted",
                    }
                    for key, value in posture.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_action_queue(
    snapshot: ExecutiveCommandCenterSnapshot,
) -> None:
    st.subheader("Executive Action Queue")

    if not snapshot.actions:
        st.success("No executive actions are currently pending.")
        return

    dataframe = pd.DataFrame(
        [
            {
                "Priority": item.priority,
                "Category": item.category,
                "Action": item.title,
                "Owner": item.owner,
                "Case": item.case_id or "-",
                "Approval": (
                    "Required"
                    if item.approval_required
                    else "Not required"
                ),
                "Route": item.route,
                "Reason": item.reason,
            }
            for item in snapshot.actions
        ]
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )


def _render_pipeline(
    snapshot: ExecutiveCommandCenterSnapshot,
) -> None:
    st.subheader("Procurement Pipeline")

    metrics = st.columns(5)
    metrics[0].metric(
        "Total Cases",
        snapshot.pipeline.total_cases,
    )
    metrics[1].metric(
        "Healthy",
        snapshot.pipeline.healthy_cases,
    )
    metrics[2].metric(
        "Attention",
        snapshot.pipeline.attention_cases,
    )
    metrics[3].metric(
        "Blocked",
        snapshot.pipeline.blocked_cases,
    )
    metrics[4].metric(
        "Overdue",
        snapshot.pipeline.overdue_cases,
    )

    if snapshot.pipeline.stage_values:
        stage_df = pd.DataFrame(
            [
                {
                    "Stage": stage,
                    "Value": value,
                    "Cases": snapshot.pipeline.stage_counts.get(stage, 0),
                }
                for stage, value
                in snapshot.pipeline.stage_values.items()
            ]
        )
        st.bar_chart(
            stage_df.set_index("Stage")["Value"],
            use_container_width=True,
        )


def _render_risk_and_finance(
    snapshot: ExecutiveCommandCenterSnapshot,
) -> None:
    left, right = st.columns(2)

    with left:
        st.subheader("Enterprise Risk")
        st.metric(
            "Overall Risk Score",
            f"{snapshot.risk_posture.overall_risk_score}/100",
        )
        st.metric(
            "Risk Level",
            snapshot.risk_posture.risk_level.value,
        )
        st.metric(
            "Critical Risks",
            snapshot.risk_posture.critical_risk_count,
        )

        if snapshot.risk_posture.category_scores:
            risk_df = pd.DataFrame(
                [
                    {
                        "Category": category,
                        "Score": score,
                    }
                    for category, score
                    in snapshot.risk_posture.category_scores.items()
                ]
            )
            st.bar_chart(
                risk_df.set_index("Category")["Score"],
                use_container_width=True,
            )

    with right:
        st.subheader("Financial Exposure")
        finance = snapshot.financial_exposure

        st.metric(
            "Supplier Obligations",
            _money(finance.total_supplier_obligations),
        )
        st.metric(
            "Unprotected Exposure",
            _money(finance.unprotected_exposure),
        )
        st.metric(
            "FX Exposure",
            _money(finance.fx_exposure),
        )
        st.metric(
            "Exposure Level",
            finance.exposure_level.value,
        )


def _render_health(
    snapshot: ExecutiveCommandCenterSnapshot,
) -> None:
    st.subheader("Platform Health")

    health = snapshot.platform_health
    metrics = st.columns(4)
    metrics[0].metric(
        "Health Score",
        f"{health.health_score}/100",
    )
    metrics[1].metric(
        "Health Level",
        health.level.value,
    )
    metrics[2].metric(
        "Dependencies Checked",
        health.dependencies_checked,
    )
    metrics[3].metric(
        "Unavailable",
        len(health.unavailable_dependencies),
    )

    if health.critical_failures:
        for failure in health.critical_failures:
            st.error(failure)

    if health.latency_warnings:
        for warning in health.latency_warnings:
            st.warning(warning)


def _render_audit_footer(
    snapshot: ExecutiveCommandCenterSnapshot,
) -> None:
    with st.expander("Audit and snapshot metadata"):
        st.json(
            {
                "generated_at": snapshot.generated_at,
                "executive_attention_required": (
                    snapshot.executive_attention_required
                ),
                "transaction_execution_allowed": (
                    snapshot.transaction_execution_allowed
                ),
                "snapshot": _serialisable_snapshot(snapshot),
            }
        )


def _serialisable_snapshot(
    snapshot: ExecutiveCommandCenterSnapshot,
) -> dict[str, Any]:
    return asdict(snapshot)


def _money(
    value: float,
) -> str:
    return f"${value:,.2f}"


if __name__ == "__main__":
    render()