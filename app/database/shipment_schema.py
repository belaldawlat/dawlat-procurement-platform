"""
Enterprise shipment database schema and migrations.

This module upgrades the existing Dawlat Procurement Platform shipment
structure without deleting old shipment data or breaking current screens.

It provides:

- Backward compatibility with the existing Shipment model and service
- Enterprise shipment fields
- Shipment timeline
- Shipment documents
- Shipment tracking
- Status audit history
- Safe, repeatable database migrations
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from database.connection import get_connection


SCHEMA_COMPONENT = "shipments"
SCHEMA_VERSION = 1


SHIPMENT_STATUSES: tuple[str, ...] = (
    "Draft",
    "Planning",
    "Ordered",
    "Packed",
    "Loaded",
    "Export Customs",
    "Vessel Departed",
    "In Transit",
    "Arrival",
    "Import Customs",
    "Customs Clearance",
    "Warehouse Received",
    "Delivered",
    "Delayed",
    "Completed",
    "Cancelled",
)


CONTAINER_TYPES: tuple[str, ...] = (
    "20GP",
    "40GP",
    "40HC",
    "LCL",
)


SHIPMENT_TIMELINE_STAGES: tuple[str, ...] = (
    "Ordered",
    "Packed",
    "Loaded",
    "Export Customs",
    "Vessel Departed",
    "In Transit",
    "Arrival",
    "Import Customs",
    "Warehouse Received",
    "Delivered",
)


SHIPMENT_DOCUMENT_TYPES: tuple[str, ...] = (
    "Commercial Invoice",
    "Packing List",
    "Bill of Lading",
    "Certificate of Origin",
    "Phytosanitary Certificate",
    "Fumigation Certificate",
    "Insurance Certificate",
    "Import Permit",
    "Customs Documents",
    "Other",
)


TIMELINE_STAGE_ORDER: dict[str, int] = {
    stage: index
    for index, stage in enumerate(
        SHIPMENT_TIMELINE_STAGES,
        start=1,
    )
}


ENTERPRISE_SHIPMENT_COLUMNS: dict[str, str] = {
    # Enterprise aliases and linked entities
    "shipment_reference": "TEXT",
    "shipment_name": "TEXT",
    "supplier_quotation_id": "INTEGER",
    "freight_quote_id": "INTEGER",
    "warehouse_id": "INTEGER",
    "supplier_id": "INTEGER",
    "customer_id": "INTEGER",
    "product_id": "INTEGER",
    "customer_name": "TEXT",

    # Shipping details
    "shipping_line": "TEXT",
    "origin_city": "TEXT",
    "origin_port": "TEXT",
    "destination_city": "TEXT",
    "destination_port": "TEXT",
    "atd": "TEXT",
    "ata": "TEXT",

    # Insurance
    "insurance_required": (
        "INTEGER NOT NULL DEFAULT 0"
    ),
    "insurance_provider": "TEXT",
    "insurance_policy_number": "TEXT",
    "insurance_value": (
        "REAL NOT NULL DEFAULT 0"
    ),

    # Cargo
    "cargo_quantity": (
        "REAL NOT NULL DEFAULT 0"
    ),
    "cargo_unit": "TEXT",
    "net_weight_kg": (
        "REAL NOT NULL DEFAULT 0"
    ),

    # Enterprise cost aliases
    "port_charges": (
        "REAL NOT NULL DEFAULT 0"
    ),
    "warehouse_cost": (
        "REAL NOT NULL DEFAULT 0"
    ),
    "local_transport_cost": (
        "REAL NOT NULL DEFAULT 0"
    ),
    "shipment_cost": (
        "REAL NOT NULL DEFAULT 0"
    ),
    "total_shipment_value": (
        "REAL NOT NULL DEFAULT 0"
    ),

    # Enterprise workflow
    "shipment_status": (
        "TEXT NOT NULL DEFAULT 'Draft'"
    ),
    "current_location": "TEXT",
    "tracking_url": "TEXT",
    "delay_days": (
        "INTEGER NOT NULL DEFAULT 0"
    ),

    # Customs
    "customs_clearance_status": "TEXT",
    "customs_entry_number": "TEXT",
    "customs_broker_name": "TEXT",

    # Transit performance
    "actual_transit_days": "INTEGER",
    "estimated_transit_days": "INTEGER",

    # Delivery
    "delivery_address": "TEXT",

    # Record governance
    "is_active": (
        "INTEGER NOT NULL DEFAULT 1"
    ),
    "is_deleted": (
        "INTEGER NOT NULL DEFAULT 0"
    ),
    "version": (
        "INTEGER NOT NULL DEFAULT 1"
    ),
    "created_by": "INTEGER",
    "updated_by": "INTEGER",
    "deleted_at": "TEXT",
}


def create_shipment_tables() -> None:
    """
    Create or safely upgrade the complete shipment database structure.

    This function is idempotent. It can run every time the application
    starts without deleting shipment data.
    """

    with get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        _create_schema_migrations_table(connection)
        _create_base_shipments_table(connection)
        _upgrade_existing_shipments_table(connection)

        _create_shipment_timeline_table(connection)
        _create_shipment_documents_table(connection)
        _create_shipment_tracking_table(connection)
        _create_shipment_status_history_table(connection)

        _backfill_enterprise_shipment_fields(connection)
        _migrate_legacy_milestones(connection)
        _backfill_existing_shipment_checklists(connection)

        _create_shipment_indexes(connection)
        _record_schema_version(connection)

        connection.commit()


def _create_schema_migrations_table(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            component TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def _create_base_shipments_table(
    connection: sqlite3.Connection,
) -> None:
    """
    Create the backward-compatible shipment table for a fresh database.

    Existing installations already have this table. In that case,
    CREATE TABLE IF NOT EXISTS leaves the existing data untouched.
    """

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
            updated_at TEXT NOT NULL
        )
        """
    )


def _upgrade_existing_shipments_table(
    connection: sqlite3.Connection,
) -> None:
    """
    Add enterprise fields that do not already exist.

    SQLite supports adding nullable columns and columns with constant
    defaults safely through ALTER TABLE.
    """

    existing_columns = _get_table_columns(
        connection,
        "shipments",
    )

    for column_name, definition in (
        ENTERPRISE_SHIPMENT_COLUMNS.items()
    ):
        if column_name in existing_columns:
            continue

        connection.execute(
            f"""
            ALTER TABLE shipments
            ADD COLUMN {column_name} {definition}
            """
        )


def _create_shipment_timeline_table(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shipment_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            shipment_id INTEGER NOT NULL,
            stage_name TEXT NOT NULL,
            stage_order INTEGER NOT NULL,

            stage_status TEXT NOT NULL DEFAULT 'Pending',

            planned_date TEXT,
            actual_date TEXT,

            location TEXT,
            responsible_party TEXT,
            notes TEXT,

            completed_by INTEGER,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (shipment_id)
                REFERENCES shipments(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE,

            UNIQUE (shipment_id, stage_name)
        )
        """
    )


def _create_shipment_documents_table(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shipment_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            shipment_id INTEGER NOT NULL,

            document_type TEXT NOT NULL,
            document_name TEXT NOT NULL,
            document_number TEXT,

            file_name TEXT,
            file_path TEXT,
            file_extension TEXT,
            file_size_bytes INTEGER,

            issuing_authority TEXT,
            issued_date TEXT,
            expiry_date TEXT,

            verification_status TEXT NOT NULL
                DEFAULT 'Pending',

            is_required INTEGER NOT NULL DEFAULT 1,
            is_received INTEGER NOT NULL DEFAULT 0,

            notes TEXT,

            uploaded_by INTEGER,
            verified_by INTEGER,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (shipment_id)
                REFERENCES shipments(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        )
        """
    )


def _create_shipment_tracking_table(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shipment_tracking_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            shipment_id INTEGER NOT NULL,

            event_code TEXT,
            event_name TEXT NOT NULL,
            event_description TEXT,

            location_name TEXT,
            city TEXT,
            country TEXT,
            port_code TEXT,

            latitude REAL,
            longitude REAL,

            event_time TEXT NOT NULL,

            source_type TEXT NOT NULL
                DEFAULT 'Manual',

            source_reference TEXT,
            external_tracking_id TEXT,

            vessel_name TEXT,
            voyage_number TEXT,

            is_exception INTEGER NOT NULL DEFAULT 0,
            exception_reason TEXT,

            recorded_by INTEGER,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (shipment_id)
                REFERENCES shipments(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        )
        """
    )


def _create_shipment_status_history_table(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shipment_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            shipment_id INTEGER NOT NULL,

            previous_status TEXT,
            new_status TEXT NOT NULL,

            change_reason TEXT,
            changed_by INTEGER,

            changed_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (shipment_id)
                REFERENCES shipments(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        )
        """
    )


def _backfill_enterprise_shipment_fields(
    connection: sqlite3.Connection,
) -> None:
    """
    Synchronise the enterprise fields with legacy shipment fields.

    This provides compatibility during the controlled Phase 9 refactor.
    """

    connection.execute(
        """
        UPDATE shipments
        SET
            shipment_reference = COALESCE(
                NULLIF(shipment_reference, ''),
                shipment_number
            ),

            shipment_name = COALESCE(
                NULLIF(shipment_name, ''),
                NULLIF(product_name, '') || ' Shipment',
                shipment_number
            ),

            supplier_quotation_id = COALESCE(
                supplier_quotation_id,
                supplier_quote_id
            ),

            freight_quote_id = COALESCE(
                freight_quote_id,
                logistics_quote_id
            ),

            warehouse_id = COALESCE(
                warehouse_id,
                warehouse_quote_id
            ),

            shipping_line = COALESCE(
                NULLIF(shipping_line, ''),
                carrier_name
            ),

            origin_port = COALESCE(
                NULLIF(origin_port, ''),
                origin_location
            ),

            destination_port = COALESCE(
                NULLIF(destination_port, ''),
                destination_location
            ),

            atd = COALESCE(
                atd,
                actual_departure_date
            ),

            ata = COALESCE(
                ata,
                actual_arrival_date
            ),

            cargo_quantity = CASE
                WHEN cargo_quantity IS NULL
                     OR cargo_quantity = 0
                THEN COALESCE(quantity, 0)
                ELSE cargo_quantity
            END,

            cargo_unit = COALESCE(
                NULLIF(cargo_unit, ''),
                unit
            ),

            port_charges = CASE
                WHEN port_charges IS NULL
                     OR port_charges = 0
                THEN COALESCE(port_cost, 0)
                ELSE port_charges
            END,

            warehouse_cost = CASE
                WHEN warehouse_cost IS NULL
                     OR warehouse_cost = 0
                THEN COALESCE(storage_cost, 0)
                ELSE warehouse_cost
            END,

            local_transport_cost = CASE
                WHEN local_transport_cost IS NULL
                     OR local_transport_cost = 0
                THEN COALESCE(local_delivery_cost, 0)
                ELSE local_transport_cost
            END,

            shipment_status = CASE
                WHEN shipment_status IS NULL
                     OR shipment_status = ''
                     OR shipment_status = 'Draft'
                THEN COALESCE(NULLIF(status, ''), 'Draft')
                ELSE shipment_status
            END,

            customs_clearance_status = COALESCE(
                NULLIF(customs_clearance_status, ''),
                customs_status
            ),

            current_location = COALESCE(
                NULLIF(current_location, ''),
                origin_location
            ),

            insurance_required = CASE
                WHEN COALESCE(insurance_cost, 0) > 0
                     OR insurance_certificate_received = 1
                THEN 1
                ELSE COALESCE(insurance_required, 0)
            END,

            shipment_cost = (
                COALESCE(freight_cost, 0)
                + COALESCE(insurance_cost, 0)
                + COALESCE(customs_cost, 0)
                + COALESCE(biosecurity_cost, 0)
                + COALESCE(port_cost, 0)
                + COALESCE(local_delivery_cost, 0)
                + COALESCE(storage_cost, 0)
                + COALESCE(other_costs, 0)
            ),

            total_shipment_value = (
                COALESCE(goods_value, 0)
                + COALESCE(freight_cost, 0)
                + COALESCE(insurance_cost, 0)
                + COALESCE(customs_cost, 0)
                + COALESCE(biosecurity_cost, 0)
                + COALESCE(port_cost, 0)
                + COALESCE(local_delivery_cost, 0)
                + COALESCE(storage_cost, 0)
                + COALESCE(other_costs, 0)
            ),

            is_active = COALESCE(is_active, 1),
            is_deleted = COALESCE(is_deleted, 0),
            version = COALESCE(version, 1)
        """
    )


def _migrate_legacy_milestones(
    connection: sqlite3.Connection,
) -> None:
    """
    Copy compatible legacy milestones into the enterprise timeline.

    Unknown milestone types remain in shipment_milestones and are not lost.
    """

    if not _table_exists(
        connection,
        "shipment_milestones",
    ):
        return

    legacy_rows = connection.execute(
        """
        SELECT
            shipment_id,
            milestone_type,
            milestone_date,
            status,
            location,
            description,
            responsible_party,
            notes
        FROM shipment_milestones
        """
    ).fetchall()

    for row in legacy_rows:
        stage_name = _normalise_timeline_stage(
            row["milestone_type"]
        )

        if stage_name is None:
            continue

        connection.execute(
            """
            INSERT OR IGNORE INTO shipment_timeline (
                shipment_id,
                stage_name,
                stage_order,
                stage_status,
                actual_date,
                location,
                responsible_party,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["shipment_id"],
                stage_name,
                TIMELINE_STAGE_ORDER[stage_name],
                _normalise_stage_status(row["status"]),
                row["milestone_date"],
                row["location"],
                row["responsible_party"],
                row["notes"] or row["description"],
            ),
        )


def _backfill_existing_shipment_checklists(
    connection: sqlite3.Connection,
) -> None:
    shipment_rows = connection.execute(
        """
        SELECT *
        FROM shipments
        WHERE COALESCE(is_deleted, 0) = 0
        """
    ).fetchall()

    for shipment in shipment_rows:
        _create_default_timeline_with_connection(
            connection,
            int(shipment["id"]),
        )

        _create_default_document_checklist_with_connection(
            connection,
            int(shipment["id"]),
            shipment,
        )


def create_default_shipment_timeline(
    shipment_id: int,
) -> None:
    """Create the standard ten-stage timeline for one shipment."""

    _validate_positive_id(shipment_id, "shipment_id")

    with get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        _require_shipment(connection, shipment_id)

        _create_default_timeline_with_connection(
            connection,
            shipment_id,
        )

        connection.commit()


def _create_default_timeline_with_connection(
    connection: sqlite3.Connection,
    shipment_id: int,
) -> None:
    for stage_name, stage_order in (
        TIMELINE_STAGE_ORDER.items()
    ):
        connection.execute(
            """
            INSERT OR IGNORE INTO shipment_timeline (
                shipment_id,
                stage_name,
                stage_order,
                stage_status
            )
            VALUES (?, ?, ?, 'Pending')
            """,
            (
                shipment_id,
                stage_name,
                stage_order,
            ),
        )


def create_default_document_checklist(
    shipment_id: int,
) -> None:
    """Create the standard document checklist for one shipment."""

    _validate_positive_id(shipment_id, "shipment_id")

    with get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        shipment = _require_shipment(
            connection,
            shipment_id,
        )

        _create_default_document_checklist_with_connection(
            connection,
            shipment_id,
            shipment,
        )

        connection.commit()


def _create_default_document_checklist_with_connection(
    connection: sqlite3.Connection,
    shipment_id: int,
    shipment: sqlite3.Row | dict[str, Any],
) -> None:
    legacy_document_map = {
        "Commercial Invoice": (
            "commercial_invoice_received"
        ),
        "Packing List": (
            "packing_list_received"
        ),
        "Bill of Lading": (
            "bill_of_lading_received"
        ),
        "Certificate of Origin": (
            "certificate_of_origin_received"
        ),
        "Phytosanitary Certificate": (
            "phytosanitary_received"
        ),
        "Fumigation Certificate": (
            "fumigation_received"
        ),
        "Insurance Certificate": (
            "insurance_certificate_received"
        ),
        "Import Permit": (
            "import_permit_received"
        ),
        "Customs Documents": None,
    }

    shipment_keys = set(shipment.keys())

    for document_type, legacy_column in (
        legacy_document_map.items()
    ):
        is_received = 0

        if (
            legacy_column
            and legacy_column in shipment_keys
        ):
            is_received = int(
                bool(shipment[legacy_column])
            )

        verification_status = (
            "Verified"
            if is_received
            else "Pending"
        )

        connection.execute(
            """
            INSERT INTO shipment_documents (
                shipment_id,
                document_type,
                document_name,
                verification_status,
                is_required,
                is_received
            )
            SELECT ?, ?, ?, ?, 1, ?
            WHERE NOT EXISTS (
                SELECT 1
                FROM shipment_documents
                WHERE shipment_id = ?
                  AND document_type = ?
            )
            """,
            (
                shipment_id,
                document_type,
                document_type,
                verification_status,
                is_received,
                shipment_id,
                document_type,
            ),
        )


def _create_shipment_indexes(
    connection: sqlite3.Connection,
) -> None:
    indexes = (
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            idx_shipments_reference_unique
        ON shipments(shipment_reference)
        WHERE shipment_reference IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_status
        ON shipments(shipment_status)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_legacy_status
        ON shipments(status)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_booking
        ON shipments(booking_number)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_container
        ON shipments(container_number)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_bl
        ON shipments(bill_of_lading_number)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_supplier
        ON shipments(supplier_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_customer
        ON shipments(customer_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_product
        ON shipments(product_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_rfq
        ON shipments(rfq_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_supplier_quotation
        ON shipments(supplier_quotation_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_freight_quote
        ON shipments(freight_quote_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_warehouse
        ON shipments(warehouse_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_route
        ON shipments(origin_port, destination_port)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_dates
        ON shipments(etd, eta, atd, ata)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipments_active_deleted
        ON shipments(is_active, is_deleted)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipment_timeline_shipment
        ON shipment_timeline(shipment_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipment_timeline_status
        ON shipment_timeline(stage_status)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipment_documents_shipment
        ON shipment_documents(shipment_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipment_documents_type
        ON shipment_documents(document_type)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_shipment_documents_verification
        ON shipment_documents(verification_status)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_tracking_events_shipment
        ON shipment_tracking_events(shipment_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_tracking_events_time
        ON shipment_tracking_events(event_time)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_tracking_events_exception
        ON shipment_tracking_events(is_exception)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_status_history_shipment
        ON shipment_status_history(shipment_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_status_history_changed_at
        ON shipment_status_history(changed_at)
        """,
    )

    for index_sql in indexes:
        connection.execute(index_sql)


def _record_schema_version(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        INSERT INTO schema_migrations (
            component,
            version,
            applied_at
        )
        VALUES (?, ?, ?)
        ON CONFLICT(component)
        DO UPDATE SET
            version = excluded.version,
            applied_at = excluded.applied_at
        """,
        (
            SCHEMA_COMPONENT,
            SCHEMA_VERSION,
            datetime.now().isoformat(
                timespec="seconds"
            ),
        ),
    )


def _get_table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        str(row["name"])
        for row in rows
    }


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def _require_shipment(
    connection: sqlite3.Connection,
    shipment_id: int,
) -> sqlite3.Row:
    shipment = connection.execute(
        """
        SELECT *
        FROM shipments
        WHERE id = ?
          AND COALESCE(is_deleted, 0) = 0
        """,
        (shipment_id,),
    ).fetchone()

    if shipment is None:
        raise ValueError(
            f"Shipment with ID {shipment_id} does not exist."
        )

    return shipment


def _validate_positive_id(
    value: int,
    field_name: str,
) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(
            f"{field_name} must be a positive integer."
        )


def _normalise_timeline_stage(
    milestone_type: str | None,
) -> str | None:
    if not milestone_type:
        return None

    value = milestone_type.strip().lower()

    aliases = {
        "ordered": "Ordered",
        "order placed": "Ordered",
        "packed": "Packed",
        "packing completed": "Packed",
        "loaded": "Loaded",
        "container loaded": "Loaded",
        "export customs": "Export Customs",
        "export clearance": "Export Customs",
        "vessel departed": "Vessel Departed",
        "departed": "Vessel Departed",
        "in transit": "In Transit",
        "arrival": "Arrival",
        "arrived": "Arrival",
        "import customs": "Import Customs",
        "customs clearance": "Import Customs",
        "warehouse received": "Warehouse Received",
        "warehouse delivery": "Warehouse Received",
        "delivered": "Delivered",
    }

    return aliases.get(value)


def _normalise_stage_status(
    status: str | None,
) -> str:
    if not status:
        return "Pending"

    value = status.strip().lower()

    mapping = {
        "pending": "Pending",
        "planned": "Pending",
        "in progress": "In Progress",
        "active": "In Progress",
        "completed": "Completed",
        "complete": "Completed",
        "delayed": "Delayed",
        "skipped": "Skipped",
        "cancelled": "Skipped",
    }

    return mapping.get(value, "Pending")