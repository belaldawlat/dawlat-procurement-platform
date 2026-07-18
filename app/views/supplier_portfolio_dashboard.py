"""Supplier Portfolio Dashboard view."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable

import pandas as pd
import streamlit as st

from services.dashboard_intelligence.supplier_portfolio_service import (
    SupplierPortfolioInput,
    SupplierPortfolioSnapshot,
    SupplierPortfolioTier,
    get_supplier_portfolio_service,
)


PAGE_TITLE = "Supplier Portfolio Dashboard"


@dataclass(frozen=True)
class SupplierPortfolioControlRecord:
    supplier_id: str
    supplier_name: str
    country: str
    category: str
    on_time_in_full_percent: float
    quality_incident_count: int
    open_corrective_actions: int
    production_capacity_utilisation_percent: float
    certificate_expiry_dates: tuple[str, ...]
    compliance_status: str
    latest_audit_score: int
    response_sla_hours: float
    average_response_hours: float
    active_orders: int
    open_disputes: int
    backup_supplier_count: int
    owner: str


@dataclass(frozen=True)
class SupplierPortfolioControlSnapshot:
    total_suppliers: int
    otif_below_target: int
    quality_attention: int
    certificate_expiry_alerts: int
    compliance_exceptions: int
    capacity_alerts: int
    open_corrective_actions: int
    open_disputes: int
    records: tuple[SupplierPortfolioControlRecord, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


def build_control_snapshot(
    records: Iterable[SupplierPortfolioControlRecord],
) -> SupplierPortfolioControlSnapshot:
    items = tuple(records)

    return SupplierPortfolioControlSnapshot(
        total_suppliers=len(items),
        otif_below_target=sum(
            1
            for item in items
            if item.on_time_in_full_percent < 90
        ),
        quality_attention=sum(
            1
            for item in items
            if item.quality_incident_count > 0
            or item.open_corrective_actions > 0
        ),
        certificate_expiry_alerts=sum(
            _expiring_certificate_count(item.certificate_expiry_dates)
            for item in items
        ),
        compliance_exceptions=sum(
            1
            for item in items
            if item.compliance_status.strip().lower()
            not in {"approved", "clear", "compliant"}
        ),
        capacity_alerts=sum(
            1
            for item in items
            if item.production_capacity_utilisation_percent >= 90
        ),
        open_corrective_actions=sum(
            item.open_corrective_actions for item in items
        ),
        open_disputes=sum(item.open_disputes for item in items),
        records=tuple(
            sorted(
                items,
                key=lambda item: (
                    item.compliance_status.strip().lower()
                    in {"approved", "clear", "compliant"},
                    item.on_time_in_full_percent >= 90,
                    item.quality_incident_count == 0,
                    -item.active_orders,
                ),
            )
        ),
    )


def render(
    portfolio_inputs: tuple[SupplierPortfolioInput, ...] = (),
    control_records: tuple[SupplierPortfolioControlRecord, ...] = (),
) -> None:
    """Render supplier performance, compliance and resilience control."""

    st.title(PAGE_TITLE)
    st.caption(
        "Supplier control tower covering performance, compliance, capacity, "
        "concentration, certificates, disputes and backup coverage."
    )

    portfolio = get_supplier_portfolio_service().build(portfolio_inputs)
    operations = build_control_snapshot(control_records)

    _render_metrics(portfolio, control)
    _render_portfolio(portfolio)
    _render_supplier_exceptions(portfolio, control)
    _render_concentration(portfolio)
    _render_supplier_table(control)
    _render_recommendations(portfolio, control)
    _render_governance(portfolio, control)


def _render_metrics(
    portfolio: SupplierPortfolioSnapshot,
    operations: SupplierPortfolioControlSnapshot,
) -> None:
    first = st.columns(5)
    first[0].metric("Active Suppliers", portfolio.active_suppliers)
    first[1].metric("Strategic", portfolio.strategic_suppliers)
    first[2].metric("Restricted", portfolio.restricted_suppliers)
    first[3].metric("Blocked", portfolio.blocked_suppliers)
    first[4].metric(
        "Annual Spend",
        _money(portfolio.total_annual_spend),
    )

    second = st.columns(5)
    second[0].metric(
        "OTIF Below Target",
        control.otif_below_target,
    )
    second[1].metric(
        "Quality Attention",
        control.quality_attention,
    )
    second[2].metric(
        "Certificate Alerts",
        control.certificate_expiry_alerts,
    )
    second[3].metric(
        "Compliance Exceptions",
        control.compliance_exceptions,
    )
    second[4].metric(
        "Capacity Alerts",
        control.capacity_alerts,
    )


def _render_portfolio(
    portfolio: SupplierPortfolioSnapshot,
) -> None:
    st.subheader("Supplier Portfolio Classification")

    if not portfolio.records:
        st.info("No supplier portfolio records were supplied.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Supplier": item.supplier_name,
                    "Country": item.country,
                    "Category": item.category,
                    "Tier": item.tier.value,
                    "Score": item.composite_score,
                    "Annual Spend": item.annual_spend,
                    "Concentration %": item.concentration_percent,
                    "Backup Coverage": item.backup_coverage,
                    "Recommended Action": item.recommended_action,
                    "Warnings": "; ".join(item.warnings),
                }
                for item in portfolio.records
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_supplier_exceptions(
    portfolio: SupplierPortfolioSnapshot,
    operations: SupplierPortfolioControlSnapshot,
) -> None:
    st.subheader("Supplier Action Queue")

    portfolio_index = {
        item.supplier_id: item
        for item in portfolio.records
    }

    actions: list[dict[str, object]] = []

    for item in control.records:
        portfolio_item = portfolio_index.get(item.supplier_id)
        reasons: list[str] = []

        if item.on_time_in_full_percent < 90:
            reasons.append("OTIF below target.")
        if item.quality_incident_count > 0:
            reasons.append("Open quality incidents.")
        if item.open_corrective_actions > 0:
            reasons.append("Corrective actions remain open.")
        if item.production_capacity_utilisation_percent >= 90:
            reasons.append("Capacity utilisation is critical.")
        if _expiring_certificate_count(item.certificate_expiry_dates):
            reasons.append("Certificates require renewal.")
        if item.open_disputes > 0:
            reasons.append("Commercial disputes are open.")
        if item.average_response_hours > item.response_sla_hours:
            reasons.append("Supplier response SLA exceeded.")
        if item.backup_supplier_count == 0:
            reasons.append("No backup supplier recorded.")

        if reasons:
            actions.append(
                {
                    "Priority": _supplier_priority(
                        item,
                        portfolio_item.tier
                        if portfolio_item is not None
                        else None,
                    ),
                    "Supplier": item.supplier_name,
                    "Country": item.country,
                    "Category": item.category,
                    "Owner": item.owner,
                    "Reason": "; ".join(dict.fromkeys(reasons)),
                    "Action": (
                        portfolio_item.recommended_action
                        if portfolio_item is not None
                        else "Investigate and remediate supplier exception."
                    ),
                }
            )

    if actions:
        st.dataframe(
            pd.DataFrame(actions),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No supplier actions are currently pending.")


def _render_concentration(
    portfolio: SupplierPortfolioSnapshot,
) -> None:
    st.subheader("Country and Category Concentration")

    left, right = st.columns(2)

    with left:
        if portfolio.country_concentration:
            country_df = pd.DataFrame(
                [
                    {"Country": key, "Concentration": value}
                    for key, value
                    in portfolio.country_concentration.items()
                ]
            )
            st.bar_chart(
                country_df.set_index("Country"),
                use_container_width=True,
            )

    with right:
        if portfolio.category_concentration:
            category_df = pd.DataFrame(
                [
                    {"Category": key, "Concentration": value}
                    for key, value
                    in portfolio.category_concentration.items()
                ]
            )
            st.bar_chart(
                category_df.set_index("Category"),
                use_container_width=True,
            )

    if portfolio.single_source_categories:
        st.warning(
            "Single-source categories: "
            + ", ".join(portfolio.single_source_categories)
        )


def _render_supplier_table(
    operations: SupplierPortfolioControlSnapshot,
) -> None:
    st.subheader("Supplier Portfolio Registry")

    if not control.records:
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Supplier": item.supplier_name,
                    "Country": item.country,
                    "Category": item.category,
                    "OTIF %": item.on_time_in_full_percent,
                    "Quality Incidents": item.quality_incident_count,
                    "Corrective Actions": item.open_corrective_actions,
                    "Capacity %": (
                        item.production_capacity_utilisation_percent
                    ),
                    "Compliance": item.compliance_status,
                    "Audit Score": item.latest_audit_score,
                    "Response SLA Hours": item.response_sla_hours,
                    "Average Response Hours": item.average_response_hours,
                    "Active Orders": item.active_orders,
                    "Open Disputes": item.open_disputes,
                    "Backup Suppliers": item.backup_supplier_count,
                    "Owner": item.owner,
                }
                for item in control.records
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_recommendations(
    portfolio: SupplierPortfolioSnapshot,
    operations: SupplierPortfolioControlSnapshot,
) -> None:
    st.subheader("AI Supplier Recommendations")

    recommendations: list[str] = []

    if portfolio.single_source_categories:
        recommendations.append(
            "Qualify backup suppliers for all single-source categories."
        )
    if control.certificate_expiry_alerts:
        recommendations.append(
            "Launch certificate-renewal workflows before expiry blocks "
            "new purchase orders or shipments."
        )
    if control.capacity_alerts:
        recommendations.append(
            "Validate production allocation and contingency capacity for "
            "suppliers operating above 90 percent utilisation."
        )
    if control.quality_attention:
        recommendations.append(
            "Prioritise root-cause analysis and corrective-action closure "
            "for suppliers with active quality incidents."
        )

    if recommendations:
        for recommendation in recommendations:
            st.info(recommendation)
    else:
        st.success("No supplier recommendations are currently required.")


def _render_governance(
    portfolio: SupplierPortfolioSnapshot,
    operations: SupplierPortfolioControlSnapshot,
) -> None:
    with st.expander("Supplier portfolio governance and snapshot metadata"):
        st.json(
            {
                "portfolio_generated_at": portfolio.generated_at,
                "operations_generated_at": control.generated_at,
                "blocked_suppliers": portfolio.blocked_suppliers,
                "compliance_exceptions": control.compliance_exceptions,
                "open_corrective_actions": (
                    control.open_corrective_actions
                ),
            }
        )

    st.caption(
        "This Supplier Portfolio Dashboard is read-only. Supplier qualification, "
        "restriction, blocking and reactivation remain governed by "
        "authorised compliance and procurement workflows."
    )


def _expiring_certificate_count(
    values: tuple[str, ...],
    within_days: int = 60,
) -> int:
    today = date.today()
    count = 0

    for value in values:
        try:
            expiry = datetime.fromisoformat(str(value)[:10]).date()
        except ValueError:
            continue

        if (expiry - today).days <= within_days:
            count += 1

    return count


def _supplier_priority(
    item: SupplierPortfolioControlRecord,
    tier: SupplierPortfolioTier | None,
) -> str:
    if tier == SupplierPortfolioTier.BLOCKED:
        return "Critical"
    if (
        item.compliance_status.strip().lower()
        not in {"approved", "clear", "compliant"}
        or item.production_capacity_utilisation_percent >= 95
    ):
        return "Critical"
    if item.on_time_in_full_percent < 80:
        return "High"
    return "Moderate"


def _money(
    value: float,
) -> str:
    return f"${value:,.2f}"


if __name__ == "__main__":
    render()