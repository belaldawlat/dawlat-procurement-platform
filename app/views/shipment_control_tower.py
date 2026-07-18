"""Shipment Control Tower view."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

import pandas as pd
import streamlit as st

from services.dashboard_intelligence.shipment_command_service import (
    ShipmentCommandInput,
    ShipmentCommandSnapshot,
    ShipmentCommandStatus,
    get_shipment_command_service,
)


PAGE_TITLE = "Shipment Control Tower"


@dataclass(frozen=True)
class ShipmentControlRecord:
    shipment_id: str
    reference: str
    container_number: str | None
    shipping_line: str | None
    vessel: str | None
    origin_port: str
    destination_port: str
    warehouse_name: str | None
    customs_status: str
    tracking_status: str
    port_congestion_level: str
    warehouse_status: str
    documents_complete: bool
    freight_cost: float
    expected_landed_cost: float
    actual_landed_cost: float | None
    owner: str
    exception_reason: str | None = None
    predicted_delay_days: int = 0


@dataclass(frozen=True)
class ShipmentControlSnapshot:
    total_shipments: int
    customs_attention: int
    port_congestion_alerts: int
    document_exceptions: int
    warehouse_exceptions: int
    predicted_delay_shipments: int
    total_freight_cost: float
    total_cost_variance: float
    route_counts: dict[str, int]
    records: tuple[ShipmentControlRecord, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


def build_control_snapshot(
    records: Iterable[ShipmentControlRecord],
) -> ShipmentControlSnapshot:
    items = tuple(records)

    routes = Counter(
        f"{item.origin_port} → {item.destination_port}"
        for item in items
    )

    cost_variance = sum(
        (
            item.actual_landed_cost
            if item.actual_landed_cost is not None
            else item.expected_landed_cost
        )
        - item.expected_landed_cost
        for item in items
    )

    return ShipmentControlSnapshot(
        total_shipments=len(items),
        customs_attention=sum(
            1
            for item in items
            if item.customs_status.strip().lower()
            not in {"cleared", "complete", "not required"}
        ),
        port_congestion_alerts=sum(
            1
            for item in items
            if item.port_congestion_level.strip().lower()
            in {"high", "severe", "critical"}
        ),
        document_exceptions=sum(
            1 for item in items if not item.documents_complete
        ),
        warehouse_exceptions=sum(
            1
            for item in items
            if item.warehouse_status.strip().lower()
            in {"blocked", "full", "delayed", "unavailable"}
        ),
        predicted_delay_shipments=sum(
            1
            for item in items
            if item.predicted_delay_days > 0
        ),
        total_freight_cost=round(
            sum(item.freight_cost for item in items),
            2,
        ),
        total_cost_variance=round(cost_variance, 2),
        route_counts=dict(routes),
        records=tuple(
            sorted(
                items,
                key=lambda item: (
                    item.predicted_delay_days <= 0,
                    item.customs_status.strip().lower()
                    in {"cleared", "complete", "not required"},
                    item.port_congestion_level.strip().lower()
                    not in {"high", "severe", "critical"},
                ),
            )
        ),
    )


def render(
    shipment_inputs: tuple[ShipmentCommandInput, ...] = (),
    control_records: tuple[ShipmentControlRecord, ...] = (),
) -> None:
    """Render global shipment, customs and landed-cost control control."""

    st.title(PAGE_TITLE)
    st.caption(
        "Shipment control tower covering ETA performance, customs, "
        "documents, ports, freight cost, warehouses and delivery exceptions."
    )

    command = get_shipment_command_service().build(shipment_inputs)
    operations = build_control_snapshot(control_records)

    _render_metrics(command, control)
    _render_live_shipment_board(command)
    _render_exception_queue(command, control)
    _render_cost_control(command, control)
    _render_route_distribution(control)
    _render_logistics_table(control)
    _render_recommendations(command, control)
    _render_governance(command, control)


def _render_metrics(
    command: ShipmentCommandSnapshot,
    operations: ShipmentControlSnapshot,
) -> None:
    first = st.columns(5)
    first[0].metric("Active Shipments", command.active_shipments)
    first[1].metric("Delayed", command.delayed_shipments)
    first[2].metric("Blocked", command.blocked_shipments)
    first[3].metric(
        "On-Time Rate",
        f"{command.on_time_rate_percent:.2f}%",
    )
    first[4].metric(
        "Shipment Value",
        _money(command.total_shipment_value),
    )

    second = st.columns(5)
    second[0].metric(
        "Customs Attention",
        control.customs_attention,
    )
    second[1].metric(
        "Port Alerts",
        control.port_congestion_alerts,
    )
    second[2].metric(
        "Document Exceptions",
        control.document_exceptions,
    )
    second[3].metric(
        "Predicted Delays",
        control.predicted_delay_shipments,
    )
    second[4].metric(
        "Cost Variance",
        _money(command.total_cost_variance),
    )


def _render_live_shipment_board(
    command: ShipmentCommandSnapshot,
) -> None:
    st.subheader("Live Shipment Board")

    if not command.records:
        st.info("No shipment command records were supplied.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Reference": item.reference,
                    "Status": item.command_status.value,
                    "Days to ETA": item.days_to_eta,
                    "Delay Days": item.delay_days,
                    "Cost Variance": item.landed_cost_variance,
                    "Variance %": item.landed_cost_variance_percent,
                    "Owner": item.owner,
                    "Next Action": item.next_action,
                    "Warnings": "; ".join(item.warnings),
                }
                for item in command.records
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_exception_queue(
    command: ShipmentCommandSnapshot,
    operations: ShipmentControlSnapshot,
) -> None:
    st.subheader("Logistics Exception Queue")

    command_index = {
        item.shipment_id: item
        for item in command.records
    }

    exceptions: list[dict[str, object]] = []

    for item in control.records:
        command_item = command_index.get(item.shipment_id)
        reasons: list[str] = []

        if not item.documents_complete:
            reasons.append("Documents incomplete.")
        if item.customs_status.strip().lower() not in {
            "cleared",
            "complete",
            "not required",
        }:
            reasons.append("Customs clearance requires attention.")
        if item.port_congestion_level.strip().lower() in {
            "high",
            "severe",
            "critical",
        }:
            reasons.append("Port congestion risk.")
        if item.predicted_delay_days > 0:
            reasons.append(
                f"Predicted delay: {item.predicted_delay_days} days."
            )
        if item.exception_reason:
            reasons.append(item.exception_reason)

        if reasons:
            exceptions.append(
                {
                    "Priority": _logistics_priority(
                        item,
                        command_item.command_status
                        if command_item is not None
                        else None,
                    ),
                    "Reference": item.reference,
                    "Container": item.container_number or "-",
                    "Route": (
                        f"{item.origin_port} → {item.destination_port}"
                    ),
                    "Customs": item.customs_status,
                    "Port Risk": item.port_congestion_level,
                    "Warehouse": item.warehouse_status,
                    "Owner": item.owner,
                    "Reason": "; ".join(dict.fromkeys(reasons)),
                }
            )

    if exceptions:
        st.dataframe(
            pd.DataFrame(exceptions),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No logistics exceptions are currently active.")


def _render_cost_control(
    command: ShipmentCommandSnapshot,
    operations: ShipmentControlSnapshot,
) -> None:
    st.subheader("Freight and Landed-Cost Control")

    metrics = st.columns(4)
    metrics[0].metric(
        "Freight Cost",
        _money(control.total_freight_cost),
    )
    metrics[1].metric(
        "Expected Landed Cost",
        _money(command.total_expected_landed_cost),
    )
    metrics[2].metric(
        "Actual Landed Cost",
        _money(command.total_actual_landed_cost),
    )
    metrics[3].metric(
        "Variance",
        _money(command.total_cost_variance),
    )

    chart = pd.DataFrame(
        {
            "Amount": {
                "Freight Cost": control.total_freight_cost,
                "Expected Landed Cost": (
                    command.total_expected_landed_cost
                ),
                "Actual Landed Cost": (
                    command.total_actual_landed_cost
                ),
            }
        }
    )

    st.bar_chart(chart, use_container_width=True)


def _render_route_distribution(
    snapshot: ShipmentControlSnapshot,
) -> None:
    st.subheader("Route Distribution")

    if snapshot.route_counts:
        route_df = pd.DataFrame(
            [
                {"Route": route, "Shipments": count}
                for route, count in snapshot.route_counts.items()
            ]
        ).sort_values("Shipments", ascending=False)

        st.bar_chart(
            route_df.set_index("Route"),
            use_container_width=True,
        )


def _render_logistics_table(
    snapshot: ShipmentControlSnapshot,
) -> None:
    st.subheader("Shipment Control Registry")

    if not snapshot.records:
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Reference": item.reference,
                    "Container": item.container_number or "-",
                    "Shipping Line": item.shipping_line or "-",
                    "Vessel": item.vessel or "-",
                    "Origin": item.origin_port,
                    "Destination": item.destination_port,
                    "Customs": item.customs_status,
                    "Tracking": item.tracking_status,
                    "Port Congestion": item.port_congestion_level,
                    "Warehouse": item.warehouse_status,
                    "Documents": item.documents_complete,
                    "Freight Cost": item.freight_cost,
                    "Expected Landed Cost": item.expected_landed_cost,
                    "Actual Landed Cost": item.actual_landed_cost,
                    "Predicted Delay": item.predicted_delay_days,
                    "Owner": item.owner,
                }
                for item in snapshot.records
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_recommendations(
    command: ShipmentCommandSnapshot,
    operations: ShipmentControlSnapshot,
) -> None:
    st.subheader("AI Shipment Recommendations")

    recommendations: list[str] = []

    if command.delayed_shipments:
        recommendations.append(
            "Refresh recovery ETAs and escalate delayed shipments to "
            "carriers, brokers and receiving warehouses."
        )
    if control.customs_attention:
        recommendations.append(
            "Prioritise customs-document validation and broker follow-up "
            "for shipments awaiting clearance."
        )
    if control.port_congestion_alerts:
        recommendations.append(
            "Assess alternate ports, sailing schedules or transshipment "
            "routes for high-congestion lanes."
        )
    if command.total_cost_variance > 0:
        recommendations.append(
            "Investigate freight, port, handling and storage variance "
            "before final landed-cost closure."
        )

    if recommendations:
        for recommendation in recommendations:
            st.info(recommendation)
    else:
        st.success("No logistics recommendations are currently required.")


def _render_governance(
    command: ShipmentCommandSnapshot,
    operations: ShipmentControlSnapshot,
) -> None:
    with st.expander("Shipment control governance and snapshot metadata"):
        st.json(
            {
                "command_generated_at": command.generated_at,
                "operations_generated_at": control.generated_at,
                "active_shipments": command.active_shipments,
                "blocked_shipments": command.blocked_shipments,
                "predicted_delays": control.predicted_delay_shipments,
            }
        )

    st.caption(
        "This Shipment Control Tower is read-only. Carrier bookings, customs "
        "instructions, release orders and delivery changes remain governed "
        "through authorised workflows."
    )


def _logistics_priority(
    item: ShipmentControlRecord,
    command_status: ShipmentCommandStatus | None,
) -> str:
    if command_status == ShipmentCommandStatus.BLOCKED:
        return "Critical"
    if (
        item.port_congestion_level.strip().lower()
        in {"severe", "critical"}
        or item.predicted_delay_days >= 5
    ):
        return "Critical"
    if item.predicted_delay_days > 0:
        return "High"
    return "Moderate"


def _money(
    value: float,
) -> str:
    return f"${value:,.2f}"


if __name__ == "__main__":
    render()