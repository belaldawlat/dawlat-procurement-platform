"""Enterprise Risk Command Center view."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.dashboard_intelligence.risk_command_service import (
    RiskCommandItem,
    RiskCommandSnapshot,
    get_risk_command_service,
)


PAGE_TITLE = "Risk Command Center"


def render(
    risks: tuple[RiskCommandItem, ...] = (),
) -> None:
    """Render unified enterprise risk posture and mitigation queue."""

    st.title(PAGE_TITLE)
    st.caption(
        "Correlated supplier, buyer, country, logistics, compliance, "
        "payment and compound risk intelligence."
    )

    snapshot = get_risk_command_service().evaluate(risks)

    _render_metrics(snapshot)
    _render_category_risk(snapshot)
    _render_blocking_risks(snapshot)
    _render_top_risks(snapshot)
    _render_mitigation_queue(snapshot)
    _render_governance(snapshot)


def _render_metrics(
    snapshot: RiskCommandSnapshot,
) -> None:
    metrics = st.columns(4)
    metrics[0].metric(
        "Global Risk Index",
        f"{snapshot.overall_risk_score}/100",
    )
    metrics[1].metric(
        "Risk Level",
        snapshot.risk_level.value,
    )
    metrics[2].metric(
        "Critical Risks",
        snapshot.critical_risk_count,
    )
    metrics[3].metric(
        "Execution Gate",
        "Open"
        if snapshot.execution_allowed
        else "Restricted",
    )


def _render_category_risk(
    snapshot: RiskCommandSnapshot,
) -> None:
    st.subheader("Risk by Category")

    if not snapshot.category_scores:
        st.info("No enterprise risk records were supplied.")
        return

    dataframe = pd.DataFrame(
        [
            {
                "Category": category,
                "Risk Score": score,
            }
            for category, score
            in snapshot.category_scores.items()
        ]
    ).sort_values(
        "Risk Score",
        ascending=False,
    )

    st.bar_chart(
        dataframe.set_index("Category"),
        use_container_width=True,
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )


def _render_blocking_risks(
    snapshot: RiskCommandSnapshot,
) -> None:
    st.subheader("Blocking Risk Controls")

    if snapshot.blocking_case_ids:
        st.error(
            "Commercial execution is blocked for cases: "
            + ", ".join(snapshot.blocking_case_ids)
        )
    else:
        st.success("No cases are currently blocked by risk controls.")


def _render_top_risks(
    snapshot: RiskCommandSnapshot,
) -> None:
    st.subheader("Top Enterprise Risks")

    if not snapshot.top_risks:
        st.info("No ranked risks are currently available.")
        return

    dataframe = pd.DataFrame(
        [
            {
                "Case": item.case_id,
                "Category": item.category,
                "Risk": item.title,
                "Probability": item.probability,
                "Impact": item.impact_score,
                "Confidence": item.confidence_score,
                "Blocking": item.blocking,
                "Evidence Count": len(item.evidence),
            }
            for item in snapshot.top_risks
        ]
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )


def _render_mitigation_queue(
    snapshot: RiskCommandSnapshot,
) -> None:
    st.subheader("Executive Mitigation Queue")

    actions: list[dict[str, object]] = []

    for item in snapshot.top_risks:
        priority = (
            "Critical"
            if item.blocking or item.impact_score >= 80
            else "High"
            if item.impact_score >= 60
            else "Moderate"
        )

        actions.append(
            {
                "Priority": priority,
                "Case": item.case_id,
                "Category": item.category,
                "Mitigation": (
                    "Stop execution and escalate review."
                    if item.blocking
                    else "Collect evidence and reduce exposure."
                ),
                "Owner": _owner_for_category(item.category),
            }
        )

    if actions:
        st.dataframe(
            pd.DataFrame(actions),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No mitigation actions are currently pending.")


def _render_governance(
    snapshot: RiskCommandSnapshot,
) -> None:
    st.subheader("Risk Governance")

    for warning in snapshot.warnings:
        st.warning(warning)

    st.caption(
        "This dashboard does not approve or execute transactions. "
        "All material actions remain governed by the approval gateway, "
        "workflow router and audit pipeline."
    )


def _owner_for_category(
    category: str,
) -> str:
    normalised = category.strip().lower()

    if normalised in {"compliance", "sanctions", "regulatory"}:
        return "Risk & Compliance"
    if normalised in {"payment", "finance", "buyer"}:
        return "Finance"
    if normalised in {"shipment", "logistics", "customs"}:
        return "Logistics Operations"
    if normalised in {"supplier", "quality"}:
        return "Procurement"

    return "Enterprise Risk"


if __name__ == "__main__":
    render()