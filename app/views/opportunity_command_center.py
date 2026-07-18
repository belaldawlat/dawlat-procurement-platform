"""Opportunity Command Center view."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

import pandas as pd
import streamlit as st

from services.dashboard_intelligence.opportunity_command_service import (
    OpportunityCommandInput,
    OpportunityCommandSnapshot,
    OpportunityReadiness,
    get_opportunity_command_service,
)


PAGE_TITLE = "Opportunity Command Center"


@dataclass(frozen=True)
class OpportunityCommandRecord:
    opportunity_id: str
    title: str
    buyer_name: str
    product_name: str
    market: str
    stage: str
    owner: str
    expected_revenue: float
    expected_profit: float
    probability_percent: float
    buyer_readiness_score: int
    payment_readiness_score: int
    days_in_stage: int
    stage_sla_days: int
    approval_required: bool
    approval_status: str
    lost_reason: str | None = None
    next_action: str = ""


@dataclass(frozen=True)
class OpportunityCommandOperationsSnapshot:
    total_opportunities: int
    total_pipeline_revenue: float
    weighted_revenue_forecast: float
    total_expected_profit: float
    protected_margin_percent: float
    overdue_stage_cases: int
    pending_approvals: int
    low_buyer_readiness: int
    low_payment_readiness: int
    win_rate_percent: float
    lost_opportunities: int
    stage_counts: dict[str, int]
    records: tuple[OpportunityCommandRecord, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


def build_operations_snapshot(
    records: Iterable[OpportunityCommandRecord],
) -> OpportunityCommandOperationsSnapshot:
    items = tuple(records)

    won = sum(
        1
        for item in items
        if item.stage.strip().lower() in {"won", "converted", "contracted"}
    )
    lost = sum(
        1
        for item in items
        if item.stage.strip().lower() in {"lost", "declined", "cancelled"}
    )
    closed = won + lost

    revenue = sum(item.expected_revenue for item in items)
    profit = sum(item.expected_profit for item in items)

    return OpportunityCommandOperationsSnapshot(
        total_opportunities=len(items),
        total_pipeline_revenue=round(revenue, 2),
        weighted_revenue_forecast=round(
            sum(
                item.expected_revenue
                * max(0.0, min(100.0, item.probability_percent))
                / 100.0
                for item in items
            ),
            2,
        ),
        total_expected_profit=round(profit, 2),
        protected_margin_percent=round(
            profit / revenue * 100.0
            if revenue > 0
            else 0.0,
            2,
        ),
        overdue_stage_cases=sum(
            1
            for item in items
            if item.days_in_stage > item.stage_sla_days
        ),
        pending_approvals=sum(
            1
            for item in items
            if item.approval_required
            and item.approval_status.strip().lower() == "pending"
        ),
        low_buyer_readiness=sum(
            1
            for item in items
            if item.buyer_readiness_score < 60
        ),
        low_payment_readiness=sum(
            1
            for item in items
            if item.payment_readiness_score < 60
        ),
        win_rate_percent=round(
            won / closed * 100.0
            if closed > 0
            else 0.0,
            2,
        ),
        lost_opportunities=lost,
        stage_counts=dict(Counter(item.stage for item in items)),
        records=tuple(
            sorted(
                items,
                key=lambda item: (
                    item.days_in_stage <= item.stage_sla_days,
                    item.buyer_readiness_score >= 60,
                    item.payment_readiness_score >= 60,
                    -item.expected_profit,
                ),
            )
        ),
    )


def render(
    opportunity_inputs: tuple[OpportunityCommandInput, ...] = (),
    command_records: tuple[OpportunityCommandRecord, ...] = (),
) -> None:
    """Render commercial pipeline, profitability and readiness operations."""

    st.title(PAGE_TITLE)
    st.caption(
        "Commercial control tower covering opportunity ranking, revenue, "
        "margin, buyer readiness, payment readiness and approvals."
    )

    command = get_opportunity_command_service().build(
        opportunity_inputs
    )
    operations = build_operations_snapshot(command_records)

    _render_metrics(command, operations)
    _render_pipeline(operations)
    _render_ranked_opportunities(command)
    _render_bottlenecks(operations)
    _render_approval_queue(operations)
    _render_lost_opportunities(operations)
    _render_recommendations(command, operations)
    _render_governance(command, operations)


def _render_metrics(
    command: OpportunityCommandSnapshot,
    operations: OpportunityCommandOperationsSnapshot,
) -> None:
    first = st.columns(5)
    first[0].metric(
        "Pipeline Revenue",
        _money(operations.total_pipeline_revenue),
    )
    first[1].metric(
        "Weighted Forecast",
        _money(operations.weighted_revenue_forecast),
    )
    first[2].metric(
        "Expected Profit",
        _money(operations.total_expected_profit),
    )
    first[3].metric(
        "Protected Margin",
        f"{operations.protected_margin_percent:.2f}%",
    )
    first[4].metric(
        "Win Rate",
        f"{operations.win_rate_percent:.2f}%",
    )

    second = st.columns(5)
    second[0].metric("Ready", command.ready_opportunities)
    second[1].metric(
        "Conditional",
        command.conditional_opportunities,
    )
    second[2].metric("Blocked", command.blocked_opportunities)
    second[3].metric(
        "Pending Approvals",
        operations.pending_approvals,
    )
    second[4].metric(
        "Overdue in Stage",
        operations.overdue_stage_cases,
    )


def _render_pipeline(
    operations: OpportunityCommandOperationsSnapshot,
) -> None:
    st.subheader("Opportunity Pipeline")

    if not operations.stage_counts:
        st.info("No opportunity command records were supplied.")
        return

    pipeline_df = pd.DataFrame(
        [
            {"Stage": stage, "Opportunities": count}
            for stage, count in operations.stage_counts.items()
        ]
    ).sort_values("Opportunities", ascending=False)

    st.bar_chart(
        pipeline_df.set_index("Stage"),
        use_container_width=True,
    )


def _render_ranked_opportunities(
    command: OpportunityCommandSnapshot,
) -> None:
    st.subheader("Ranked Opportunity Portfolio")

    if not command.records:
        st.info("No opportunity-command records were supplied.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Opportunity": item.title,
                    "Readiness": item.readiness.value,
                    "Priority Score": item.priority_score,
                    "Protected Profit": item.protected_profit,
                    "Protected Margin %": (
                        item.protected_margin_percent
                    ),
                    "Blockers": "; ".join(item.blockers),
                    "Warnings": "; ".join(item.warnings),
                    "Recommended Action": item.recommended_action,
                }
                for item in command.records
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_bottlenecks(
    operations: OpportunityCommandOperationsSnapshot,
) -> None:
    st.subheader("Opportunity Bottleneck Queue")

    rows: list[dict[str, object]] = []

    for item in operations.records:
        reasons: list[str] = []

        if item.days_in_stage > item.stage_sla_days:
            reasons.append("Stage SLA exceeded.")
        if item.buyer_readiness_score < 60:
            reasons.append("Buyer readiness below target.")
        if item.payment_readiness_score < 60:
            reasons.append("Payment readiness below target.")

        if reasons:
            rows.append(
                {
                    "Priority": _opportunity_priority(item),
                    "Opportunity": item.title,
                    "Buyer": item.buyer_name,
                    "Stage": item.stage,
                    "Owner": item.owner,
                    "Revenue": item.expected_revenue,
                    "Profit": item.expected_profit,
                    "Buyer Readiness": item.buyer_readiness_score,
                    "Payment Readiness": item.payment_readiness_score,
                    "Reason": "; ".join(reasons),
                    "Next Action": item.next_action,
                }
            )

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No commercial bottlenecks are currently active.")


def _render_approval_queue(
    operations: OpportunityCommandOperationsSnapshot,
) -> None:
    st.subheader("Opportunity Approval Queue")

    pending = [
        item
        for item in operations.records
        if item.approval_required
        and item.approval_status.strip().lower() == "pending"
    ]

    if not pending:
        st.success("No commercial approvals are pending.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Opportunity": item.title,
                    "Buyer": item.buyer_name,
                    "Product": item.product_name,
                    "Market": item.market,
                    "Revenue": item.expected_revenue,
                    "Expected Profit": item.expected_profit,
                    "Probability %": item.probability_percent,
                    "Owner": item.owner,
                    "Next Action": item.next_action,
                }
                for item in pending
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_lost_opportunities(
    operations: OpportunityCommandOperationsSnapshot,
) -> None:
    st.subheader("Lost Opportunity Intelligence")

    lost = [
        item
        for item in operations.records
        if item.stage.strip().lower() in {
            "lost",
            "declined",
            "cancelled",
        }
    ]

    if not lost:
        st.success("No lost opportunities are recorded in this snapshot.")
        return

    reason_counts = Counter(
        item.lost_reason or "Reason not recorded"
        for item in lost
    )

    reason_df = pd.DataFrame(
        [
            {"Reason": reason, "Count": count}
            for reason, count in reason_counts.items()
        ]
    ).sort_values("Count", ascending=False)

    st.bar_chart(
        reason_df.set_index("Reason"),
        use_container_width=True,
    )


def _render_recommendations(
    command: OpportunityCommandSnapshot,
    operations: OpportunityCommandOperationsSnapshot,
) -> None:
    st.subheader("AI Opportunity Recommendations")

    recommendations: list[str] = []

    if command.blocked_opportunities:
        recommendations.append(
            "Resolve compliance, supplier qualification and critical risk "
            "blockers before commercial execution."
        )
    if operations.low_buyer_readiness:
        recommendations.append(
            "Prioritise final buyer specifications, purchase commitment "
            "and commercial acceptance before supplier engagement."
        )
    if operations.low_payment_readiness:
        recommendations.append(
            "Secure cleared buyer funds or approved payment structure "
            "before supplier payment milestones are activated."
        )
    if operations.protected_margin_percent < 15:
        recommendations.append(
            "Reprice, renegotiate or redesign logistics to restore the "
            "protected-margin threshold."
        )
    if operations.overdue_stage_cases:
        recommendations.append(
            "Escalate opportunities exceeding stage SLA and close stale "
            "pipeline records with evidence."
        )

    if recommendations:
        for recommendation in recommendations:
            st.info(recommendation)
    else:
        st.success("No commercial recommendations are currently required.")


def _render_governance(
    command: OpportunityCommandSnapshot,
    operations: OpportunityCommandOperationsSnapshot,
) -> None:
    with st.expander("Opportunity command governance and snapshot metadata"):
        st.json(
            {
                "command_generated_at": command.generated_at,
                "operations_generated_at": operations.generated_at,
                "total_opportunities": operations.total_opportunities,
                "ready_opportunities": command.ready_opportunities,
                "blocked_opportunities": command.blocked_opportunities,
                "pending_approvals": operations.pending_approvals,
            }
        )

    st.caption(
        "This Opportunity Command Center is read-only. Customer commitments, pricing, "
        "contracts, supplier awards and payment execution remain subject "
        "to authorised approval and audit workflows."
    )


def _opportunity_priority(
    item: OpportunityCommandRecord,
) -> str:
    if (
        item.buyer_readiness_score < 40
        or item.payment_readiness_score < 40
    ):
        return "Critical"
    if item.days_in_stage > item.stage_sla_days:
        return "High"
    return "Moderate"


def _money(
    value: float,
) -> str:
    return f"${value:,.2f}"


if __name__ == "__main__":
    render()