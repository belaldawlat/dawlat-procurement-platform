"""Financial Command Center view."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.dashboard_intelligence.financial_exposure_service import (
    FinancialExposureItem,
    FinancialExposureSnapshot,
    get_financial_exposure_service,
)


PAGE_TITLE = "Financial Command Center"


def render(
    items: tuple[FinancialExposureItem, ...] = (),
) -> None:
    """Render executive financial exposure and protection controls."""

    st.title(PAGE_TITLE)
    st.caption(
        "Executive visibility over buyer funds, supplier obligations, "
        "margin protection, FX exposure and working-capital risk."
    )

    snapshot = get_financial_exposure_service().calculate(items)

    _render_metrics(snapshot)
    _render_financial_posture(snapshot)
    _render_case_exposure(items)
    _render_warnings(snapshot)
    _render_governance(snapshot)


def _render_metrics(
    snapshot: FinancialExposureSnapshot,
) -> None:
    first = st.columns(4)
    first[0].metric(
        "Cleared Buyer Funds",
        _money(snapshot.total_cleared_buyer_funds),
    )
    first[1].metric(
        "Supplier Obligations",
        _money(snapshot.total_supplier_obligations),
    )
    first[2].metric(
        "Protected Profit",
        _money(snapshot.protected_profit),
    )
    first[3].metric(
        "Unprotected Exposure",
        _money(snapshot.unprotected_exposure),
    )

    second = st.columns(4)
    second[0].metric(
        "FX Exposure",
        _money(snapshot.fx_exposure),
    )
    second[1].metric(
        "Margin Leakage",
        _money(snapshot.margin_leakage),
    )
    second[2].metric(
        "Overdue Receivables",
        _money(snapshot.overdue_receivables),
    )
    second[3].metric(
        "Exposure Utilisation",
        f"{snapshot.exposure_utilisation_percent:.2f}%",
    )


def _render_financial_posture(
    snapshot: FinancialExposureSnapshot,
) -> None:
    st.subheader("Financial Protection Posture")

    left, right = st.columns(2)

    with left:
        st.metric(
            "Exposure Level",
            snapshot.exposure_level.value,
        )
        st.metric(
            "Committed Cash",
            _money(snapshot.committed_cash),
        )

    with right:
        st.metric(
            "Expected Revenue",
            _money(snapshot.expected_revenue),
        )
        st.metric(
            "Expected Landed Cost",
            _money(snapshot.expected_landed_cost),
        )

    chart = pd.DataFrame(
        {
            "Amount": {
                "Buyer Funds": snapshot.total_cleared_buyer_funds,
                "Supplier Obligations": snapshot.total_supplier_obligations,
                "Expected Revenue": snapshot.expected_revenue,
                "Expected Landed Cost": snapshot.expected_landed_cost,
                "Protected Profit": snapshot.protected_profit,
            }
        }
    )

    st.bar_chart(
        chart,
        use_container_width=True,
    )


def _render_case_exposure(
    items: tuple[FinancialExposureItem, ...],
) -> None:
    st.subheader("Case-Level Financial Exposure")

    if not items:
        st.info("No financial exposure records were supplied.")
        return

    dataframe = pd.DataFrame(
        [
            {
                "Case": item.case_id,
                "Buyer Funds": item.cleared_buyer_funds,
                "Supplier Obligation": item.supplier_obligation,
                "Protected Profit": item.protected_profit,
                "Revenue": item.expected_revenue,
                "Landed Cost": item.expected_landed_cost,
                "FX Exposure": item.fx_exposure,
                "Overdue Receivable": item.overdue_receivable_amount,
                "Exposure Limit": item.authorised_exposure_limit,
                "Payment Gate": (
                    "Open"
                    if item.cleared_buyer_funds >= item.supplier_obligation
                    else "Blocked"
                ),
            }
            for item in items
        ]
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )


def _render_warnings(
    snapshot: FinancialExposureSnapshot,
) -> None:
    st.subheader("Financial Warnings")

    if snapshot.warnings:
        for warning in snapshot.warnings:
            st.warning(warning)
    else:
        st.success("No financial warnings are currently active.")

    if snapshot.blocked_case_ids:
        st.error(
            "Payment execution is blocked for: "
            + ", ".join(snapshot.blocked_case_ids)
        )


def _render_governance(
    snapshot: FinancialExposureSnapshot,
) -> None:
    st.subheader("Financial Governance")

    gate_open = (
        snapshot.unprotected_exposure == 0
        and not snapshot.blocked_case_ids
    )

    st.metric(
        "Supplier Payment Gate",
        "Open" if gate_open else "Restricted",
    )

    st.caption(
        "This dashboard is read-only. Supplier payments must continue "
        "through the approval gateway and payment protection controls."
    )


def _money(
    value: float,
) -> str:
    return f"${value:,.2f}"


if __name__ == "__main__":
    render()