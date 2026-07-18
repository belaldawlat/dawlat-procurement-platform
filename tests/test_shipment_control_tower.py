"""Shipment Control Tower tests."""

from __future__ import annotations

from views.shipment_control_tower import ShipmentControlRecord, _money, build_control_snapshot


def _record(**overrides: object) -> ShipmentControlRecord:
    values: dict[str, object] = {
        "shipment_id": "SHIP-1", "reference": "SHP-001",
        "container_number": "CONT-001", "shipping_line": "Carrier", "vessel": "Vessel",
        "origin_port": "Karachi", "destination_port": "Melbourne",
        "warehouse_name": "Melbourne 3PL", "customs_status": "Cleared",
        "tracking_status": "Current", "port_congestion_level": "Low",
        "warehouse_status": "Available", "documents_complete": True,
        "freight_cost": 8_000.0, "expected_landed_cost": 50_000.0,
        "actual_landed_cost": 50_000.0, "owner": "Logistics",
        "exception_reason": None, "predicted_delay_days": 0,
    }
    values.update(overrides)
    return ShipmentControlRecord(**values)


def test_shipment_snapshot_detects_customs_cost_and_delay_exceptions() -> None:
    exception = _record(
        shipment_id="SHIP-X", customs_status="Pending",
        port_congestion_level="Severe", warehouse_status="Delayed",
        documents_complete=False, actual_landed_cost=56_000, predicted_delay_days=6,
    )
    snapshot = build_control_snapshot((exception, _record(shipment_id="SHIP-SAFE")))
    assert snapshot.total_shipments == 2
    assert snapshot.customs_attention == 1
    assert snapshot.port_congestion_alerts == 1
    assert snapshot.document_exceptions == 1
    assert snapshot.warehouse_exceptions == 1
    assert snapshot.predicted_delay_shipments == 1
    assert snapshot.total_cost_variance == 6_000
    assert snapshot.records[0].shipment_id == "SHIP-X"


def test_shipment_route_aggregation_and_empty_state() -> None:
    snapshot = build_control_snapshot((_record(shipment_id="A"), _record(shipment_id="B")))
    assert snapshot.route_counts["Karachi → Melbourne"] == 2
    assert _money(8000) == "$8,000.00"
    empty = build_control_snapshot(())
    assert empty.total_shipments == 0
    assert empty.total_cost_variance == 0