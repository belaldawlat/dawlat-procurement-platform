"""Streamlit control centre for the Autonomous Procurement Brain."""

from __future__ import annotations

import streamlit as st


def render() -> None:
    st.title("Autonomous Procurement Brain")
    st.caption(
        "Predict, rank, plan, monitor and recommend while preserving "
        "human approval, commercial safeguards and auditability."
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Market Intelligence", "Ready")
    col2.metric("Opportunity Prediction", "Ready")
    col3.metric("Approval Governor", "Ready")
    col4.metric("Execution Mode", "Human Controlled")

    st.subheader("Core operating model")
    st.info(
        "Prediction → Planning → Approval → Authorised Execution → "
        "Monitoring → Outcome Learning"
    )

    st.subheader("Permitted autonomous behaviour")
    st.write(
        "- Detect and analyse market signals.\n"
        "- Forecast landed costs and disruption risks.\n"
        "- Rank opportunities, logistics routes and priorities.\n"
        "- Prepare non-binding action plans and drafts.\n"
        "- Raise alerts and request human approval."
    )

    st.subheader("Prohibited autonomous behaviour")
    st.error(
        "The brain cannot independently commit suppliers, issue purchase "
        "orders, release payments, book shipments, activate contracts, "
        "or disclose protected commercial relationships."
    )

    st.subheader("Enterprise safeguards")
    st.write(
        "- Buyer and supplier verification\n"
        "- Risk, trust and compliance controls\n"
        "- Protected minimum margin\n"
        "- Buyer final approval\n"
        "- Cleared buyer funds\n"
        "- Verified documents and milestones\n"
        "- Authorised signatures and audit history"
    )


def show() -> None:
    render()