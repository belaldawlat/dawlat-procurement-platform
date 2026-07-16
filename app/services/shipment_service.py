"""Shipment application service for Dawlat Procurement Platform.

This module preserves the public functions used by the current Streamlit UI
while routing shipment persistence through the enterprise repository and
schema. It keeps legacy and enterprise columns synchronized during the
controlled Phase 9 migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from database.connection import get_connection
from database.shipment_schema import (
    TIMELINE_STAGE_ORDER,
    create_default_document_checklist,
    create_default_shipment_timeline,
    create_shipment_tables,
)
from models.shipment import Shipment, ShipmentMilestone
from repositories.shipment_repository import ShipmentRepository


_MILESTONE_TO_STAGE = {
    "Order Placed": "Ordered",
    "Ordered": "Ordered",
    "Packing Completed": "Packed",
    "Cargo Ready": "Packed",
    "Packed": "Packed",
    "Container Loaded": "Loaded",
    "Loaded": "Loaded",
    "Export Customs Cleared": "Export Customs",
    "Export Customs": "Export Customs",
    "Departed Origin": "Vessel Departed",
    "Vessel Departed": "Vessel Departed",
    "In Transit": "In Transit",
    "Arrived Destination": "Arrival",
    "Arrival": "Arrival",
    "Import Documents Submitted": "Import Customs",
    "Customs Cleared": "Import Customs",
    "Delivered to Warehouse": "Warehouse Received",
    "Warehouse Received": "Warehouse Received",
    "Delivered": "Delivered",
    "Shipment Completed": "Delivered",
}


_STATUS_TO_STAGE = {
    "Planning": None,
    "Draft": None,
    "Booking Requested": "Ordered",
    "Booked": "Ordered",
    "Ordered": "Ordered",
    "Awaiting Pickup": "Packed",
    "Packed": "Packed",
    "Picked Up": "Loaded",
    "Loaded": "Loaded",
    "Export Customs": "Export Customs",
    "Vessel Departed": "Vessel Departed",
    "In Transit": "In Transit",
    "Arrived at Port": "Arrival",
    "Arrival": "Arrival",
    "Customs Clearance": "Import Customs",
    "Import Customs": "Import Customs",
    "Released": "Warehouse Received",
    "Out for Delivery": "Warehouse Received",
    "Warehouse Received": "Warehouse Received",
    "Delivered": "Delivered",
    "Completed": "Delivered",
    "Delayed": None,
    "Cancelled": None,
}


def ensure_shipment_tables() -> None:
    """Create or migrate all shipment-domain tables safely."""

    create_shipment_tables()


def row_to_shipment(row: Any) -> Shipment:
    """Convert a SQLite row or mapping into the existing Shipment model."""

    return Shipment(
        id=row["id"],
        shipment_number=row["shipment_number"],
        shipment_type=row["shipment_type"],
        status=row["status"],
        rfq_id=row["rfq_id"],
        supplier_quote_id=row["supplier_quote_id"],
        logistics_quote_id=row["logistics_quote_id"],
        warehouse_quote_id=row["warehouse_quote_id"],
        supplier_name=row["supplier_name"],
        logistics_provider=row["logistics_provider"],
        warehouse_name=row["warehouse_name"],
        product_name=row["product_name"],
        cargo_description=row["cargo_description"],
        quantity=float(row["quantity"] or 0),
        unit=row["unit"],
        gross_weight_kg=float(row["gross_weight_kg"] or 0),
        volume_cbm=float(row["volume_cbm"] or 0),
        origin_country=row["origin_country"],
        origin_location=row["origin_location"],
        destination_country=row["destination_country"],
        destination_location=row["destination_location"],
        transport_mode=row["transport_mode"],
        service_type=row["service_type"],
        incoterm=row["incoterm"],
        container_type=row["container_type"],
        booking_number=row["booking_number"],
        bill_of_lading_number=row["bill_of_lading_number"],
        airway_bill_number=row["airway_bill_number"],
        container_number=row["container_number"],
        seal_number=row["seal_number"],
        tracking_number=row["tracking_number"],
        carrier_name=row["carrier_name"],
        vessel_name=row["vessel_name"],
        voyage_number=row["voyage_number"],
        flight_number=row["flight_number"],
        planned_pickup_date=row["planned_pickup_date"],
        actual_pickup_date=row["actual_pickup_date"],
        etd=row["etd"],
        actual_departure_date=row["actual_departure_date"],
        eta=row["eta"],
        actual_arrival_date=row["actual_arrival_date"],
        customs_clearance_date=row["customs_clearance_date"],
        warehouse_delivery_date=row["warehouse_delivery_date"],
        customs_status=row["customs_status"],
        biosecurity_status=row["biosecurity_status"],
        inspection_status=row["inspection_status"],
        document_status=row["document_status"],
        commercial_invoice_received=bool(row["commercial_invoice_received"]),
        packing_list_received=bool(row["packing_list_received"]),
        bill_of_lading_received=bool(row["bill_of_lading_received"]),
        certificate_of_origin_received=bool(row["certificate_of_origin_received"]),
        phytosanitary_received=bool(row["phytosanitary_received"]),
        fumigation_received=bool(row["fumigation_received"]),
        insurance_certificate_received=bool(row["insurance_certificate_received"]),
        import_permit_received=bool(row["import_permit_received"]),
        other_documents=row["other_documents"],
        currency=row["currency"],
        goods_value=float(row["goods_value"] or 0),
        freight_cost=float(row["freight_cost"] or 0),
        insurance_cost=float(row["insurance_cost"] or 0),
        customs_cost=float(row["customs_cost"] or 0),
        biosecurity_cost=float(row["biosecurity_cost"] or 0),
        port_cost=float(row["port_cost"] or 0),
        local_delivery_cost=float(row["local_delivery_cost"] or 0),
        storage_cost=float(row["storage_cost"] or 0),
        other_costs=float(row["other_costs"] or 0),
        delay_reason=row["delay_reason"],
        risk_level=row["risk_level"],
        priority=row["priority"],
        inventory_received=bool(row["inventory_received"]),
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def row_to_milestone(row: Any) -> ShipmentMilestone:
    return ShipmentMilestone(
        id=row["id"],
        shipment_id=row["shipment_id"],
        milestone_type=row["milestone_type"],
        milestone_date=row["milestone_date"],
        status=row["status"],
        location=row["location"],
        description=row["description"],
        responsible_party=row["responsible_party"],
        reference_number=row["reference_number"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


def generate_shipment_number() -> str:
    ensure_shipment_tables()
    year = datetime.now().year
    prefix = f"SHP-{year}-"
    sequence = ShipmentRepository.count_by_reference_prefix(prefix) + 1

    while ShipmentRepository.reference_exists(f"{prefix}{sequence:04d}"):
        sequence += 1

    return f"{prefix}{sequence:04d}"


def create_shipment(shipment: Shipment) -> int:
    """Create one shipment and initialize all enterprise child records."""

    ensure_shipment_tables()
    data = _shipment_to_payload(shipment)
    shipment_id = ShipmentRepository.create_shipment(data)

    create_default_shipment_timeline(shipment_id)
    create_default_document_checklist(shipment_id)

    ShipmentRepository.add_status_history(
        shipment_id=shipment_id,
        previous_status=None,
        new_status=shipment.status,
        change_reason="Shipment created.",
    )

    ShipmentRepository.add_tracking_event(
        {
            "shipment_id": shipment_id,
            "event_code": "SHIPMENT_CREATED",
            "event_name": "Shipment Created",
            "event_description": "Shipment record created.",
            "location_name": shipment.origin_location,
            "city": None,
            "country": shipment.origin_country,
            "port_code": None,
            "latitude": None,
            "longitude": None,
            "event_time": datetime.now().isoformat(timespec="seconds"),
            "source_type": "System",
            "source_reference": shipment.shipment_number,
            "external_tracking_id": None,
            "vessel_name": shipment.vessel_name,
            "voyage_number": shipment.voyage_number,
            "is_exception": 0,
            "exception_reason": None,
            "recorded_by": None,
        }
    )

    _insert_legacy_milestone(
        shipment_id=shipment_id,
        milestone_type="Shipment Created",
        milestone_date=datetime.now().date().isoformat(),
        status="Completed",
        description="Shipment record created.",
    )
    _synchronise_timeline_from_status(shipment_id, shipment.status)
    return shipment_id


def get_shipments(
    search: str = "",
    status: str = "All",
    transport_mode: str = "All",
    risk_level: str = "All",
) -> list[Shipment]:
    ensure_shipment_tables()

    query = """
        SELECT *
        FROM shipments
        WHERE COALESCE(is_deleted, 0) = 0
          AND COALESCE(is_active, 1) = 1
    """
    parameters: list[Any] = []

    if search.strip():
        value = f"%{search.strip()}%"
        query += """
            AND (
                shipment_number LIKE ?
                OR shipment_reference LIKE ?
                OR supplier_name LIKE ?
                OR customer_name LIKE ?
                OR logistics_provider LIKE ?
                OR product_name LIKE ?
                OR booking_number LIKE ?
                OR bill_of_lading_number LIKE ?
                OR airway_bill_number LIKE ?
                OR container_number LIKE ?
                OR tracking_number LIKE ?
                OR origin_location LIKE ?
                OR origin_port LIKE ?
                OR destination_location LIKE ?
                OR destination_port LIKE ?
            )
        """
        parameters.extend([value] * 15)

    if status != "All":
        query += " AND status = ?"
        parameters.append(status)

    if transport_mode != "All":
        query += " AND transport_mode = ?"
        parameters.append(transport_mode)

    if risk_level != "All":
        query += " AND risk_level = ?"
        parameters.append(risk_level)

    query += """
        ORDER BY
            CASE WHEN status IN ('Delivered', 'Completed', 'Cancelled')
                 THEN 1 ELSE 0 END,
            CASE WHEN status = 'Delayed' THEN 0 ELSE 1 END,
            eta ASC,
            id DESC
    """

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [row_to_shipment(row) for row in rows]


def get_shipment_by_id(shipment_id: int) -> Optional[Shipment]:
    ensure_shipment_tables()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM shipments
            WHERE id = ? AND COALESCE(is_deleted, 0) = 0
            """,
            (shipment_id,),
        ).fetchone()
    return row_to_shipment(row) if row else None


def update_shipment_status(
    shipment_id: int,
    *,
    status: str,
    customs_status: str,
    biosecurity_status: str,
    inspection_status: str,
    document_status: str,
    risk_level: str,
    priority: str,
    delay_reason: str,
    inventory_received: bool,
    notes: str,
) -> None:
    """Update legacy and enterprise workflow fields atomically."""

    ensure_shipment_tables()
    current = ShipmentRepository.get_by_id(shipment_id)
    if current is None:
        raise ValueError(f"Shipment with ID {shipment_id} was not found.")

    delay_text = delay_reason.strip() if delay_reason else None
    delay_days = int(current.get("delay_days") or 0)
    if status == "Delayed" and delay_days == 0:
        delay_days = 1
    elif status != "Delayed" and not delay_text:
        delay_days = 0

    updated = ShipmentRepository.update_shipment(
        shipment_id,
        {
            "shipment_status": status,
            "customs_clearance_status": customs_status,
            "delay_reason": delay_text,
            "delay_days": delay_days,
            "notes": notes.strip() if notes else None,
        },
        expected_version=current.get("version"),
    )
    if not updated:
        raise RuntimeError("Shipment was updated elsewhere. Reload and try again.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE shipments
            SET status = ?,
                customs_status = ?,
                biosecurity_status = ?,
                inspection_status = ?,
                document_status = ?,
                risk_level = ?,
                priority = ?,
                delay_reason = ?,
                inventory_received = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                customs_status,
                biosecurity_status,
                inspection_status,
                document_status,
                risk_level,
                priority,
                delay_text,
                int(inventory_received),
                notes.strip() if notes else None,
                shipment_id,
            ),
        )
        connection.commit()

    ShipmentRepository.add_status_history(
        shipment_id=shipment_id,
        previous_status=current.get("shipment_status") or current.get("status"),
        new_status=status,
        change_reason=delay_text or "Shipment control status updated.",
    )
    ShipmentRepository.add_tracking_event(
        {
            "shipment_id": shipment_id,
            "event_code": f"STATUS_{status.upper().replace(' ', '_')}",
            "event_name": status,
            "event_description": delay_text or f"Shipment status changed to {status}.",
            "location_name": current.get("current_location") or current.get("origin_port"),
            "city": None,
            "country": None,
            "port_code": None,
            "latitude": None,
            "longitude": None,
            "event_time": datetime.now().isoformat(timespec="seconds"),
            "source_type": "System",
            "source_reference": current.get("shipment_reference"),
            "external_tracking_id": None,
            "vessel_name": current.get("vessel_name"),
            "voyage_number": current.get("voyage_number"),
            "is_exception": int(status == "Delayed"),
            "exception_reason": delay_text if status == "Delayed" else None,
            "recorded_by": None,
        }
    )
    _synchronise_timeline_from_status(shipment_id, status, delay_text)


def create_shipment_milestone(milestone: ShipmentMilestone) -> int:
    ensure_shipment_tables()
    milestone_id = _insert_legacy_milestone(
        shipment_id=milestone.shipment_id,
        milestone_type=milestone.milestone_type,
        milestone_date=milestone.milestone_date,
        status=milestone.status,
        location=milestone.location,
        description=milestone.description,
        responsible_party=milestone.responsible_party,
        reference_number=milestone.reference_number,
        notes=milestone.notes,
    )

    stage = _MILESTONE_TO_STAGE.get(milestone.milestone_type)
    if stage:
        ShipmentRepository.update_timeline_stage(
            shipment_id=milestone.shipment_id,
            stage_name=stage,
            stage_status=_normalise_stage_status(milestone.status),
            actual_date=milestone.milestone_date,
            location=milestone.location,
            responsible_party=milestone.responsible_party,
            notes=milestone.notes or milestone.description,
        )

    ShipmentRepository.add_tracking_event(
        {
            "shipment_id": milestone.shipment_id,
            "event_code": milestone.milestone_type.upper().replace(" ", "_"),
            "event_name": milestone.milestone_type,
            "event_description": milestone.description,
            "location_name": milestone.location,
            "city": None,
            "country": None,
            "port_code": None,
            "latitude": None,
            "longitude": None,
            "event_time": f"{milestone.milestone_date} 00:00:00",
            "source_type": "Manual",
            "source_reference": milestone.reference_number,
            "external_tracking_id": None,
            "vessel_name": None,
            "voyage_number": None,
            "is_exception": int(milestone.status == "Delayed"),
            "exception_reason": milestone.notes if milestone.status == "Delayed" else None,
            "recorded_by": None,
        }
    )
    return milestone_id


def get_shipment_milestones(shipment_id: int) -> list[ShipmentMilestone]:
    ensure_shipment_tables()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM shipment_milestones
            WHERE shipment_id = ?
            ORDER BY milestone_date ASC, id ASC
            """,
            (shipment_id,),
        ).fetchall()
    return [row_to_milestone(row) for row in rows]


def delete_shipment(shipment_id: int) -> None:
    """Soft-delete a shipment so audit, timeline and documents are retained."""

    ensure_shipment_tables()
    if not ShipmentRepository.soft_delete(shipment_id):
        raise ValueError(f"Shipment with ID {shipment_id} was not found.")


def get_shipment_dashboard() -> dict[str, Any]:
    ensure_shipment_tables()
    return ShipmentRepository.get_dashboard_metrics()


def get_enterprise_shipment(shipment_id: int) -> dict[str, Any] | None:
    ensure_shipment_tables()
    return ShipmentRepository.get_by_id(shipment_id)


def get_shipment_timeline(shipment_id: int) -> list[dict[str, Any]]:
    ensure_shipment_tables()
    return ShipmentRepository.get_timeline(shipment_id)


def get_shipment_documents(shipment_id: int) -> list[dict[str, Any]]:
    ensure_shipment_tables()
    return ShipmentRepository.list_documents(shipment_id)


def get_shipment_tracking_events(shipment_id: int) -> list[dict[str, Any]]:
    ensure_shipment_tables()
    return ShipmentRepository.list_tracking_events(shipment_id)


def get_shipment_status_history(shipment_id: int) -> list[dict[str, Any]]:
    ensure_shipment_tables()
    return ShipmentRepository.get_status_history(shipment_id)


def get_shipment_analytics() -> dict[str, Any]:
    ensure_shipment_tables()
    return {
        "summary": ShipmentRepository.get_analytics_summary(),
        "country_performance": ShipmentRepository.get_country_performance(),
        "shipping_line_performance": ShipmentRepository.get_shipping_line_performance(),
        "cost_analysis": ShipmentRepository.get_cost_analysis(),
    }


def update_shipment_timeline_stage(
    shipment_id: int,
    stage_name: str,
    stage_status: str,
    planned_date: str | None = None,
    actual_date: str | None = None,
    location: str | None = None,
    responsible_party: str | None = None,
    notes: str | None = None,
) -> bool:
    ensure_shipment_tables()
    return ShipmentRepository.update_timeline_stage(
        shipment_id=shipment_id,
        stage_name=stage_name,
        stage_status=stage_status,
        planned_date=planned_date,
        actual_date=actual_date,
        location=location,
        responsible_party=responsible_party,
        notes=notes,
    )


def update_shipment_document(document_id: int, data: dict[str, Any]) -> bool:
    ensure_shipment_tables()
    return ShipmentRepository.update_document(document_id, data)


def add_shipment_tracking_event(shipment_id: int, data: dict[str, Any]) -> int:
    ensure_shipment_tables()
    payload = dict(data)
    payload["shipment_id"] = shipment_id
    payload.setdefault("event_time", datetime.now().isoformat(timespec="seconds"))
    payload.setdefault("source_type", "Manual")
    payload.setdefault("is_exception", 0)
    return ShipmentRepository.add_tracking_event(payload)


def _shipment_to_payload(shipment: Shipment) -> dict[str, Any]:
    return {
        "shipment_reference": shipment.shipment_number,
        "shipment_number": shipment.shipment_number,
        "shipment_name": f"{shipment.product_name} Shipment",
        "shipment_type": shipment.shipment_type,
        "shipment_status": shipment.status,
        "status": shipment.status,
        "rfq_id": shipment.rfq_id,
        "supplier_quotation_id": shipment.supplier_quote_id,
        "supplier_quote_id": shipment.supplier_quote_id,
        "freight_quote_id": shipment.logistics_quote_id,
        "logistics_quote_id": shipment.logistics_quote_id,
        "warehouse_id": shipment.warehouse_quote_id,
        "warehouse_quote_id": shipment.warehouse_quote_id,
        "supplier_name": shipment.supplier_name,
        "customer_name": None,
        "logistics_provider": shipment.logistics_provider,
        "warehouse_name": shipment.warehouse_name,
        "product_name": shipment.product_name,
        "cargo_description": shipment.cargo_description,
        "cargo_quantity": shipment.quantity,
        "quantity": shipment.quantity,
        "cargo_unit": shipment.unit,
        "unit": shipment.unit,
        "gross_weight_kg": shipment.gross_weight_kg,
        "net_weight_kg": 0,
        "volume_cbm": shipment.volume_cbm,
        "origin_country": shipment.origin_country,
        "origin_location": shipment.origin_location,
        "origin_port": shipment.origin_location,
        "destination_country": shipment.destination_country,
        "destination_location": shipment.destination_location,
        "destination_port": shipment.destination_location,
        "transport_mode": shipment.transport_mode,
        "service_type": shipment.service_type,
        "incoterm": shipment.incoterm,
        "container_type": shipment.container_type,
        "booking_number": shipment.booking_number,
        "bill_of_lading_number": shipment.bill_of_lading_number,
        "airway_bill_number": shipment.airway_bill_number,
        "container_number": shipment.container_number,
        "seal_number": shipment.seal_number,
        "tracking_number": shipment.tracking_number,
        "shipping_line": shipment.carrier_name,
        "carrier_name": shipment.carrier_name,
        "vessel_name": shipment.vessel_name,
        "voyage_number": shipment.voyage_number,
        "flight_number": shipment.flight_number,
        "planned_pickup_date": shipment.planned_pickup_date,
        "actual_pickup_date": shipment.actual_pickup_date,
        "etd": shipment.etd,
        "atd": shipment.actual_departure_date,
        "actual_departure_date": shipment.actual_departure_date,
        "eta": shipment.eta,
        "ata": shipment.actual_arrival_date,
        "actual_arrival_date": shipment.actual_arrival_date,
        "customs_clearance_date": shipment.customs_clearance_date,
        "warehouse_delivery_date": shipment.warehouse_delivery_date,
        "customs_status": shipment.customs_status,
        "customs_clearance_status": shipment.customs_status,
        "biosecurity_status": shipment.biosecurity_status,
        "inspection_status": shipment.inspection_status,
        "document_status": shipment.document_status,
        "commercial_invoice_received": shipment.commercial_invoice_received,
        "packing_list_received": shipment.packing_list_received,
        "bill_of_lading_received": shipment.bill_of_lading_received,
        "certificate_of_origin_received": shipment.certificate_of_origin_received,
        "phytosanitary_received": shipment.phytosanitary_received,
        "fumigation_received": shipment.fumigation_received,
        "insurance_certificate_received": shipment.insurance_certificate_received,
        "import_permit_received": shipment.import_permit_received,
        "other_documents": shipment.other_documents,
        "currency": shipment.currency,
        "goods_value": shipment.goods_value,
        "freight_cost": shipment.freight_cost,
        "insurance_cost": shipment.insurance_cost,
        "customs_cost": shipment.customs_cost,
        "biosecurity_cost": shipment.biosecurity_cost,
        "port_cost": shipment.port_cost,
        "port_charges": shipment.port_cost,
        "local_delivery_cost": shipment.local_delivery_cost,
        "local_transport_cost": shipment.local_delivery_cost,
        "storage_cost": shipment.storage_cost,
        "warehouse_cost": shipment.storage_cost,
        "other_costs": shipment.other_costs,
        "delay_reason": shipment.delay_reason,
        "delay_days": 1 if shipment.status == "Delayed" else 0,
        "risk_level": shipment.risk_level,
        "priority": shipment.priority,
        "inventory_received": shipment.inventory_received,
        "notes": shipment.notes,
        "current_location": shipment.origin_location,
        "estimated_transit_days": _date_difference(shipment.etd, shipment.eta),
    }


def _insert_legacy_milestone(
    shipment_id: int,
    milestone_type: str,
    milestone_date: str,
    status: str,
    location: str | None = None,
    description: str | None = None,
    responsible_party: str | None = None,
    reference_number: str | None = None,
    notes: str | None = None,
) -> int:
    timestamp = datetime.now().isoformat(timespec="seconds")
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO shipment_milestones (
                shipment_id, milestone_type, milestone_date, status,
                location, description, responsible_party,
                reference_number, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shipment_id,
                milestone_type,
                milestone_date,
                status,
                location,
                description,
                responsible_party,
                reference_number,
                notes,
                timestamp,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def _synchronise_timeline_from_status(
    shipment_id: int,
    status: str,
    notes: str | None = None,
) -> None:
    stage_name = _STATUS_TO_STAGE.get(status)
    if not stage_name:
        return

    timeline = ShipmentRepository.get_timeline(shipment_id)
    target_order = TIMELINE_STAGE_ORDER[stage_name]
    today = datetime.now().date().isoformat()

    for stage in timeline:
        if stage["stage_order"] < target_order:
            stage_status = "Completed"
            actual_date = stage.get("actual_date") or today
        elif stage["stage_order"] == target_order:
            stage_status = "Completed" if stage_name == "Delivered" else "In Progress"
            actual_date = today if stage_status == "Completed" else stage.get("actual_date")
        else:
            continue

        ShipmentRepository.update_timeline_stage(
            shipment_id=shipment_id,
            stage_name=stage["stage_name"],
            stage_status=stage_status,
            planned_date=stage.get("planned_date"),
            actual_date=actual_date,
            location=stage.get("location"),
            responsible_party=stage.get("responsible_party"),
            notes=notes if stage["stage_name"] == stage_name else stage.get("notes"),
        )


def _normalise_stage_status(status: str) -> str:
    return {
        "Planned": "Pending",
        "In Progress": "In Progress",
        "Completed": "Completed",
        "Delayed": "Delayed",
        "Cancelled": "Skipped",
    }.get(status, "Pending")


def _date_difference(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        return max(
            0,
            (
                datetime.fromisoformat(end).date()
                - datetime.fromisoformat(start).date()
            ).days,
        )
    except ValueError:
        return None