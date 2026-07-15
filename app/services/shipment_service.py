from datetime import datetime
from typing import Optional

from database.connection import get_connection
from models.shipment import Shipment, ShipmentMilestone


def ensure_shipment_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                shipment_number TEXT NOT NULL UNIQUE,
                shipment_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Planning',

                rfq_id INTEGER,
                supplier_quote_id INTEGER,
                logistics_quote_id INTEGER,
                warehouse_quote_id INTEGER,

                supplier_name TEXT NOT NULL,
                logistics_provider TEXT,
                warehouse_name TEXT,

                product_name TEXT NOT NULL,
                cargo_description TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                gross_weight_kg REAL NOT NULL DEFAULT 0,
                volume_cbm REAL NOT NULL DEFAULT 0,

                origin_country TEXT NOT NULL,
                origin_location TEXT NOT NULL,
                destination_country TEXT NOT NULL,
                destination_location TEXT NOT NULL,

                transport_mode TEXT NOT NULL,
                service_type TEXT NOT NULL,
                incoterm TEXT NOT NULL,
                container_type TEXT,

                booking_number TEXT,
                bill_of_lading_number TEXT,
                airway_bill_number TEXT,
                container_number TEXT,
                seal_number TEXT,
                tracking_number TEXT,

                carrier_name TEXT,
                vessel_name TEXT,
                voyage_number TEXT,
                flight_number TEXT,

                planned_pickup_date TEXT,
                actual_pickup_date TEXT,
                etd TEXT,
                actual_departure_date TEXT,
                eta TEXT,
                actual_arrival_date TEXT,
                customs_clearance_date TEXT,
                warehouse_delivery_date TEXT,

                customs_status TEXT NOT NULL DEFAULT 'Not Started',
                biosecurity_status TEXT NOT NULL DEFAULT 'Not Required',
                inspection_status TEXT NOT NULL DEFAULT 'Not Required',
                document_status TEXT NOT NULL DEFAULT 'Incomplete',

                commercial_invoice_received INTEGER NOT NULL DEFAULT 0,
                packing_list_received INTEGER NOT NULL DEFAULT 0,
                bill_of_lading_received INTEGER NOT NULL DEFAULT 0,
                certificate_of_origin_received INTEGER NOT NULL DEFAULT 0,
                phytosanitary_received INTEGER NOT NULL DEFAULT 0,
                fumigation_received INTEGER NOT NULL DEFAULT 0,
                insurance_certificate_received INTEGER NOT NULL DEFAULT 0,
                import_permit_received INTEGER NOT NULL DEFAULT 0,
                other_documents TEXT,

                currency TEXT NOT NULL DEFAULT 'AUD',
                goods_value REAL NOT NULL DEFAULT 0,
                freight_cost REAL NOT NULL DEFAULT 0,
                insurance_cost REAL NOT NULL DEFAULT 0,
                customs_cost REAL NOT NULL DEFAULT 0,
                biosecurity_cost REAL NOT NULL DEFAULT 0,
                port_cost REAL NOT NULL DEFAULT 0,
                local_delivery_cost REAL NOT NULL DEFAULT 0,
                storage_cost REAL NOT NULL DEFAULT 0,
                other_costs REAL NOT NULL DEFAULT 0,

                delay_reason TEXT,
                risk_level TEXT NOT NULL DEFAULT 'Medium',
                priority TEXT NOT NULL DEFAULT 'Normal',

                inventory_received INTEGER NOT NULL DEFAULT 0,
                notes TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (rfq_id)
                    REFERENCES rfqs (id),

                FOREIGN KEY (supplier_quote_id)
                    REFERENCES supplier_quotes (id),

                FOREIGN KEY (logistics_quote_id)
                    REFERENCES logistics_quotes (id),

                FOREIGN KEY (warehouse_quote_id)
                    REFERENCES warehouse_quotes (id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS shipment_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                shipment_id INTEGER NOT NULL,
                milestone_type TEXT NOT NULL,
                milestone_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Completed',

                location TEXT,
                description TEXT,
                responsible_party TEXT,
                reference_number TEXT,
                notes TEXT,

                created_at TEXT NOT NULL,

                FOREIGN KEY (shipment_id)
                    REFERENCES shipments (id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_shipments_number
            ON shipments (shipment_number)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_shipments_status
            ON shipments (status)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_shipment_milestones_shipment
            ON shipment_milestones (shipment_id)
            """
        )

        connection.commit()


def row_to_shipment(row) -> Shipment:
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
        quantity=float(row["quantity"]),
        unit=row["unit"],
        gross_weight_kg=float(row["gross_weight_kg"]),
        volume_cbm=float(row["volume_cbm"]),
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
        commercial_invoice_received=bool(
            row["commercial_invoice_received"]
        ),
        packing_list_received=bool(
            row["packing_list_received"]
        ),
        bill_of_lading_received=bool(
            row["bill_of_lading_received"]
        ),
        certificate_of_origin_received=bool(
            row["certificate_of_origin_received"]
        ),
        phytosanitary_received=bool(
            row["phytosanitary_received"]
        ),
        fumigation_received=bool(
            row["fumigation_received"]
        ),
        insurance_certificate_received=bool(
            row["insurance_certificate_received"]
        ),
        import_permit_received=bool(
            row["import_permit_received"]
        ),
        other_documents=row["other_documents"],
        currency=row["currency"],
        goods_value=float(row["goods_value"]),
        freight_cost=float(row["freight_cost"]),
        insurance_cost=float(row["insurance_cost"]),
        customs_cost=float(row["customs_cost"]),
        biosecurity_cost=float(row["biosecurity_cost"]),
        port_cost=float(row["port_cost"]),
        local_delivery_cost=float(row["local_delivery_cost"]),
        storage_cost=float(row["storage_cost"]),
        other_costs=float(row["other_costs"]),
        delay_reason=row["delay_reason"],
        risk_level=row["risk_level"],
        priority=row["priority"],
        inventory_received=bool(row["inventory_received"]),
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def row_to_milestone(row) -> ShipmentMilestone:
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

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM shipments
            WHERE shipment_number LIKE ?
            """,
            (f"SHP-{year}-%",),
        ).fetchone()

    next_number = int(row["total"]) + 1

    return f"SHP-{year}-{next_number:04d}"


def create_shipment(shipment: Shipment) -> int:
    ensure_shipment_tables()

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO shipments (
                shipment_number,
                shipment_type,
                status,

                rfq_id,
                supplier_quote_id,
                logistics_quote_id,
                warehouse_quote_id,

                supplier_name,
                logistics_provider,
                warehouse_name,

                product_name,
                cargo_description,
                quantity,
                unit,
                gross_weight_kg,
                volume_cbm,

                origin_country,
                origin_location,
                destination_country,
                destination_location,

                transport_mode,
                service_type,
                incoterm,
                container_type,

                booking_number,
                bill_of_lading_number,
                airway_bill_number,
                container_number,
                seal_number,
                tracking_number,

                carrier_name,
                vessel_name,
                voyage_number,
                flight_number,

                planned_pickup_date,
                actual_pickup_date,
                etd,
                actual_departure_date,
                eta,
                actual_arrival_date,
                customs_clearance_date,
                warehouse_delivery_date,

                customs_status,
                biosecurity_status,
                inspection_status,
                document_status,

                commercial_invoice_received,
                packing_list_received,
                bill_of_lading_received,
                certificate_of_origin_received,
                phytosanitary_received,
                fumigation_received,
                insurance_certificate_received,
                import_permit_received,
                other_documents,

                currency,
                goods_value,
                freight_cost,
                insurance_cost,
                customs_cost,
                biosecurity_cost,
                port_cost,
                local_delivery_cost,
                storage_cost,
                other_costs,

                delay_reason,
                risk_level,
                priority,

                inventory_received,
                notes,

                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?
            )
            """,
            (
                shipment.shipment_number,
                shipment.shipment_type,
                shipment.status,

                shipment.rfq_id,
                shipment.supplier_quote_id,
                shipment.logistics_quote_id,
                shipment.warehouse_quote_id,

                shipment.supplier_name,
                shipment.logistics_provider,
                shipment.warehouse_name,

                shipment.product_name,
                shipment.cargo_description,
                shipment.quantity,
                shipment.unit,
                shipment.gross_weight_kg,
                shipment.volume_cbm,

                shipment.origin_country,
                shipment.origin_location,
                shipment.destination_country,
                shipment.destination_location,

                shipment.transport_mode,
                shipment.service_type,
                shipment.incoterm,
                shipment.container_type,

                shipment.booking_number,
                shipment.bill_of_lading_number,
                shipment.airway_bill_number,
                shipment.container_number,
                shipment.seal_number,
                shipment.tracking_number,

                shipment.carrier_name,
                shipment.vessel_name,
                shipment.voyage_number,
                shipment.flight_number,

                shipment.planned_pickup_date,
                shipment.actual_pickup_date,
                shipment.etd,
                shipment.actual_departure_date,
                shipment.eta,
                shipment.actual_arrival_date,
                shipment.customs_clearance_date,
                shipment.warehouse_delivery_date,

                shipment.customs_status,
                shipment.biosecurity_status,
                shipment.inspection_status,
                shipment.document_status,

                int(shipment.commercial_invoice_received),
                int(shipment.packing_list_received),
                int(shipment.bill_of_lading_received),
                int(shipment.certificate_of_origin_received),
                int(shipment.phytosanitary_received),
                int(shipment.fumigation_received),
                int(shipment.insurance_certificate_received),
                int(shipment.import_permit_received),
                shipment.other_documents,

                shipment.currency,
                shipment.goods_value,
                shipment.freight_cost,
                shipment.insurance_cost,
                shipment.customs_cost,
                shipment.biosecurity_cost,
                shipment.port_cost,
                shipment.local_delivery_cost,
                shipment.storage_cost,
                shipment.other_costs,

                shipment.delay_reason,
                shipment.risk_level,
                shipment.priority,

                int(shipment.inventory_received),
                shipment.notes,

                timestamp,
                timestamp,
            ),
        )

        shipment_id = int(cursor.lastrowid)

        connection.execute(
            """
            INSERT INTO shipment_milestones (
                shipment_id,
                milestone_type,
                milestone_date,
                status,
                description,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                shipment_id,
                "Shipment Created",
                datetime.now().date().isoformat(),
                "Completed",
                "Shipment record created.",
                timestamp,
            ),
        )

        connection.commit()

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
        WHERE 1 = 1
    """

    parameters: list = []

    if search.strip():
        value = f"%{search.strip()}%"

        query += """
            AND (
                shipment_number LIKE ?
                OR supplier_name LIKE ?
                OR logistics_provider LIKE ?
                OR product_name LIKE ?
                OR booking_number LIKE ?
                OR bill_of_lading_number LIKE ?
                OR airway_bill_number LIKE ?
                OR container_number LIKE ?
                OR tracking_number LIKE ?
                OR origin_location LIKE ?
                OR destination_location LIKE ?
            )
        """

        parameters.extend([value] * 11)

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
            CASE
                WHEN status IN (
                    'Delivered',
                    'Completed',
                    'Cancelled'
                )
                THEN 1
                ELSE 0
            END,
            eta ASC,
            id DESC
    """

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [
        row_to_shipment(row)
        for row in rows
    ]


def get_shipment_by_id(
    shipment_id: int,
) -> Optional[Shipment]:
    ensure_shipment_tables()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM shipments
            WHERE id = ?
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
    ensure_shipment_tables()

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

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
                updated_at = ?
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
                delay_reason.strip()
                if delay_reason
                else None,
                int(inventory_received),
                notes.strip() if notes else None,
                timestamp,
                shipment_id,
            ),
        )

        connection.commit()


def create_shipment_milestone(
    milestone: ShipmentMilestone,
) -> int:
    ensure_shipment_tables()

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO shipment_milestones (
                shipment_id,
                milestone_type,
                milestone_date,
                status,
                location,
                description,
                responsible_party,
                reference_number,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                milestone.shipment_id,
                milestone.milestone_type,
                milestone.milestone_date,
                milestone.status,
                milestone.location,
                milestone.description,
                milestone.responsible_party,
                milestone.reference_number,
                milestone.notes,
                timestamp,
            ),
        )

        connection.commit()

    return int(cursor.lastrowid)


def get_shipment_milestones(
    shipment_id: int,
) -> list[ShipmentMilestone]:
    ensure_shipment_tables()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM shipment_milestones
            WHERE shipment_id = ?
            ORDER BY milestone_date ASC, id ASC
            """,
            (shipment_id,),
        ).fetchall()

    return [
        row_to_milestone(row)
        for row in rows
    ]


def delete_shipment(shipment_id: int) -> None:
    ensure_shipment_tables()

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM shipment_milestones
            WHERE shipment_id = ?
            """,
            (shipment_id,),
        )

        connection.execute(
            """
            DELETE FROM shipments
            WHERE id = ?
            """,
            (shipment_id,),
        )

        connection.commit()