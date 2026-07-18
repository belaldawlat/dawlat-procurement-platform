"""Streamlit control centre for GPNI."""
from __future__ import annotations
import streamlit as st
from services.network_intelligence.gpni_health_service import (
    get_gpni_health_service,
)

def render() -> None:
    st.title("Global Procurement Network Intelligence")
    st.caption(
        "Connect verified demand with verified supply while protecting "
        "margin, compliance, payments, contracts and relationships."
    )
    health = get_gpni_health_service().check()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Subsystem", "Healthy" if health.healthy else "Attention Required")
    col2.metric("Database", "Ready" if health.database_ready else "Unavailable")
    col3.metric("Engines", "Ready" if health.engines_ready else "Unavailable")
    col4.metric(
        "Governance",
        "Ready" if health.workflow_ready and health.audit_ready else "Incomplete",
    )
    if health.failures:
        st.error("GPNI health checks found issues.")
        for failure in health.failures:
            st.write(f"- {failure}")
    else:
        st.success("All critical GPNI integration components are available.")
    st.subheader("Protected lifecycle")
    st.info(
        "Verified demand → Buyer qualification → Verified supply → "
        "Supplier qualification → Matching → Commercial review → "
        "Buyer approval → Cleared funds → Contract readiness → "
        "Authorised execution → Monitoring → Learning"
    )
    st.subheader("Mandatory controls")
    st.write(
        "- No supplier commitment before buyer approval and cleared funds.\n"
        "- No payment release before verified milestones and documents.\n"
        "- No contract activation without authorised signatures.\n"
        "- No bypass of risk, trust, compliance or margin protections.\n"
        "- Every decision and workflow transition is auditable."
    )

def show() -> None:
    render()