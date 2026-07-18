"""Procurement Control Tower view."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

import pandas as pd
import streamlit as st

from services.dashboard_intelligence.pipeline_intelligence_service import (
    PipelineCase,
    PipelineSnapshot,
    get_pipeline_intelligence_service,
)


PAGE_TITLE = "Procurement Control Tower"


@dataclass(frozen=True)
class ProcurementControlRecord:
    case_id: str
    reference: str
    buyer_name: str
    supplier_name: str | None
    product_name: str
    stage: str
    owner: str
    value: float
    age_days: int
    sla_days: int
    buyer_commitment_confirmed: bool
    supplier_response_received: bool
    documents_complete: bool
    approval_required: bool
    approval_status: str
    next_action: str
    risk_score: int
    ai_confidence: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProcurementControlSnapshot:
    total_cases: int
    total_pipeline_value: float
    overdue_cases: int
    blocked_cases: int
    pending_approvals: int
    missing_documents: int
    awaiting_supplier_response: int
    buyer_commitment_gaps: int
    average_age_days: float
    stage_counts: dict[str, int]
    owner_workload: dict[str, int]
    records: tuple[ProcurementControlRecord, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


def build_control_snapshot(
    records: Iterable[ProcurementControlRecord],
) -> ProcurementControlSnapshot:
    items = tuple(records)

    stage_counts = dict(Counter(item.stage for item in items))
    owner_workload = dict(Counter(item.owner for item in items))

    return ProcurementControlSnapshot(
        total_cases=len(items),
        total_pipeline_value=round(sum(item.value for item in items), 2),
        overdue_cases=sum(
            1 for item in items if item.age_days > item.sla_days
        ),
        blocked_cases=sum(
            1 for item in items if item.blockers
        ),
        pending_approvals=sum(
            1
            for item in items
            if item.approval_required
            and item.approval_status.strip().lower() == "pending"
        ),
        missing_documents=sum(
            1 for item in items if not item.documents_complete
        ),
        awaiting_supplier_response=sum(
            1
            for item in items
            if not item.supplier_response_received
        ),
        buyer_commitment_gaps=sum(
            1
            for item in items
            if not item.buyer_commitment_confirmed
        ),
        average_age_days=round(
            sum(item.age_days for item in items) / len(items),
            2,
        )
        if items
        else 0.0,
        stage_counts=stage_counts,
        owner_workload=owner_workload,
        records=tuple(
            sorted(
                items,
                key=lambda item: (
                    not bool(item.blockers),
                    item.age_days <= item.sla_days,
                    -item.risk_score,
                    -item.value,
                ),
            )
        ),
    )


def render(
    pipeline_cases: tuple[PipelineCase, ...] = (),
    control_records: tuple[ProcurementControlRecord, ...] = (),
) -> None:
    """Render procurement execution, bottleneck and approval intelligence."""

    st.title(PAGE_TITLE)
    st.caption(
        "Procurement control over RFQs, quotations, approvals, buyer "
        "commitment, supplier response, documentation and procurement SLAs."
    )

    pipeline = get_pipeline_intelligence_service().snapshot(pipeline_cases)
    operations = build_control_snapshot(control_records)

    _render_metrics(pipeline, control)
    _render_stage_pipeline(control)
    _render_exception_queue(control)
    _render_approval_queue(control)
    _render_workload(control)
    _render_operational_table(control)
    _render_ai_recommendations(control)
    _render_governance(control)


def _render_metrics(
    pipeline: PipelineSnapshot,
    operations: ProcurementControlSnapshot,
) -> None:
    first = st.columns(5)
    first[0].metric("Total Cases", control.total_cases)
    first[1].metric(
        "Pipeline Value",
        _money(control.total_pipeline_value),
    )
    first[2].metric("Blocked", control.blocked_cases)
    first[3].metric("Overdue", control.overdue_cases)
    first[4].metric(
        "Pending Approvals",
        control.pending_approvals,
    )

    second = st.columns(5)
    second[0].metric(
        "Missing Documents",
        control.missing_documents,
    )
    second[1].metric(
        "Awaiting Supplier",
        control.awaiting_supplier_response,
    )
    second[2].metric(
        "Buyer Commitment Gaps",
        control.buyer_commitment_gaps,
    )
    second[3].metric(
        "Average Age",
        f"{control.average_age_days:.1f} days",
    )
    second[4].metric(
        "Pipeline Health",
        f"{pipeline.healthy_cases}/{pipeline.total_cases}",
    )


def _render_stage_pipeline(
    snapshot: ProcurementControlSnapshot,
) -> None:
    st.subheader("Procurement Stage Distribution")

    if not snapshot.stage_counts:
        st.info("No procurement control records were supplied.")
        return

    dataframe = pd.DataFrame(
        [
            {"Stage": stage, "Cases": count}
            for stage, count in snapshot.stage_counts.items()
        ]
    ).sort_values("Cases", ascending=False)

    st.bar_chart(
        dataframe.set_index("Stage"),
        use_container_width=True,
    )


def _render_exception_queue(
    snapshot: ProcurementControlSnapshot,
) -> None:
    st.subheader("Procurement Exception Queue")

    exceptions: list[dict[str, object]] = []

    for item in snapshot.records:
        reasons = list(item.blockers)
        if item.age_days > item.sla_days:
            reasons.append("SLA exceeded.")
        if not item.documents_complete:
            reasons.append("Documents incomplete.")
        if not item.supplier_response_received:
            reasons.append("Supplier response pending.")
        if not item.buyer_commitment_confirmed:
            reasons.append("Buyer commitment not confirmed.")

        if reasons:
            exceptions.append(
                {
                    "Priority": _priority(item),
                    "Reference": item.reference,
                    "Stage": item.stage,
                    "Owner": item.owner,
                    "Age": item.age_days,
                    "SLA": item.sla_days,
                    "Value": item.value,
                    "Reason": "; ".join(dict.fromkeys(reasons)),
                    "Next Action": item.next_action,
                }
            )

    if exceptions:
        st.dataframe(
            pd.DataFrame(exceptions),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No procurement exceptions are currently active.")


def _render_approval_queue(
    snapshot: ProcurementControlSnapshot,
) -> None:
    st.subheader("Approval Queue")

    pending = [
        item
        for item in snapshot.records
        if item.approval_required
        and item.approval_status.strip().lower() == "pending"
    ]

    if not pending:
        st.success("No procurement approvals are pending.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Reference": item.reference,
                    "Buyer": item.buyer_name,
                    "Supplier": item.supplier_name or "-",
                    "Product": item.product_name,
                    "Value": item.value,
                    "Risk Score": item.risk_score,
                    "AI Confidence": item.ai_confidence,
                    "Owner": item.owner,
                    "Next Action": item.next_action,
                }
                for item in pending
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_workload(
    snapshot: ProcurementControlSnapshot,
) -> None:
    st.subheader("Owner Workload")

    if snapshot.owner_workload:
        workload = pd.DataFrame(
            [
                {"Owner": owner, "Open Cases": count}
                for owner, count in snapshot.owner_workload.items()
            ]
        ).sort_values("Open Cases", ascending=False)

        st.bar_chart(
            workload.set_index("Owner"),
            use_container_width=True,
        )


def _render_operational_table(
    snapshot: ProcurementControlSnapshot,
) -> None:
    st.subheader("Procurement Control Board")

    if not snapshot.records:
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Reference": item.reference,
                    "Buyer": item.buyer_name,
                    "Supplier": item.supplier_name or "-",
                    "Product": item.product_name,
                    "Stage": item.stage,
                    "Owner": item.owner,
                    "Value": item.value,
                    "Age Days": item.age_days,
                    "SLA Days": item.sla_days,
                    "Buyer Commitment": item.buyer_commitment_confirmed,
                    "Supplier Response": item.supplier_response_received,
                    "Documents": item.documents_complete,
                    "Approval": item.approval_status,
                    "Risk": item.risk_score,
                    "AI Confidence": item.ai_confidence,
                    "Next Action": item.next_action,
                }
                for item in snapshot.records
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_ai_recommendations(
    snapshot: ProcurementControlSnapshot,
) -> None:
    st.subheader("AI Procurement Recommendations")

    recommendations: list[str] = []

    if snapshot.buyer_commitment_gaps:
        recommendations.append(
            "Prioritise buyer commitment confirmation before supplier "
            "payment or purchase-order release."
        )
    if snapshot.awaiting_supplier_response:
        recommendations.append(
            "Escalate aged supplier quotation requests and activate "
            "backup suppliers where SLA thresholds are breached."
        )
    if snapshot.missing_documents:
        recommendations.append(
            "Complete mandatory commercial and compliance documentation "
            "before routing cases for approval."
        )
    if snapshot.overdue_cases:
        recommendations.append(
            "Rebalance owner workload and execute recovery plans for "
            "overdue procurement cases."
        )

    if recommendations:
        for recommendation in recommendations:
            st.info(recommendation)
    else:
        st.success("No operational AI recommendations are currently required.")


def _render_governance(
    snapshot: ProcurementControlSnapshot,
) -> None:
    with st.expander("Procurement control governance and snapshot metadata"):
        st.json(
            {
                "generated_at": snapshot.generated_at,
                "total_cases": snapshot.total_cases,
                "blocked_cases": snapshot.blocked_cases,
                "overdue_cases": snapshot.overdue_cases,
                "pending_approvals": snapshot.pending_approvals,
            }
        )

    st.caption(
        "This Procurement Control Tower is read-only. RFQ release, purchase orders, "
        "supplier payments and contract commitments remain governed by "
        "role-based approval and audit controls."
    )


def _priority(
    item: ProcurementControlRecord,
) -> str:
    if item.blockers or item.risk_score >= 80:
        return "Critical"
    if item.age_days > item.sla_days:
        return "High"
    return "Moderate"


def _money(
    value: float,
) -> str:
    return f"${value:,.2f}"


if __name__ == "__main__":
    render()