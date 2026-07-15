"""
Shipment database schema for the Dawlat Procurement Platform.

This module owns all shipment-domain database tables, indexes, constraints,
timeline events, document records, tracking events, and status history.

Architecture:
    UI Layer
        ↓
    Shipment Services
        ↓
    Shipment Repositories
        ↓
    This database schema
"""

from __future__ import annotations

from database.connection import get_connection


SHIPMENT_STATUSES: tuple[str, ...] = (
    "Draft",
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
    "Insurance Certificate",
    "Import Permit",
    "Customs Documents",
    "Other",
)


def create_shipment_tables() -> None:
    """
    Create the complete Phase 9 shipment database structure.

    The function is idempotent and can safely run whenever the application
    starts. Existing tables and data will not be removed.
    """

    with get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        _create_shipments_table(connection)
        _create_shipment_timeline_table(connection)
        _create_shipment_documents_table(connection)
        _create_shipment_tracking_table(connection)
        _create_shipment_status_history_table(connection)
        _create_shipment_indexes(connection)

        connection.commit()


def _create_shipments_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            shipment_reference TEXT NOT NULL UNIQUE,
            shipment_name TEXT NOT NULL,

            rfq_id INTEGER,
            supplier_quotation_id INTEGER,
            freight_quote_id INTEGER,
            warehouse_id INTEGER,
            supplier_id INTEGER,
            customer_id INTEGER,
            product_id INTEGER,

            supplier_name TEXT,
            customer_name TEXT,
            product_name TEXT,

            container_type TEXT NOT NULL DEFAULT '20GP'
                CHECK (
                    container_type IN (
                        '20GP',
                        '40GP',
                        '40HC',
                        'LCL'
                    )
                ),

            shipping_line TEXT,
            vessel_name TEXT,
            voyage_number TEXT,

            booking_number TEXT,
            container_number TEXT,
            seal_number TEXT,
            bill_of_lading_number TEXT,

            origin_country TEXT,
            origin_city TEXT,
            origin_port TEXT NOT NULL,

            destination_country TEXT,
            destination_city TEXT,
            destination_port TEXT NOT NULL,

            etd TEXT,
            eta TEXT,
            atd TEXT,
            ata TEXT,

            incoterm TEXT,
            insurance_required INTEGER NOT NULL DEFAULT 0
                CHECK (insurance_required IN (0, 1)),
            insurance_provider TEXT,
            insurance_policy_number TEXT,
            insurance_value REAL NOT NULL DEFAULT 0
                CHECK (insurance_value >= 0),

            cargo_quantity REAL NOT NULL DEFAULT 0
                CHECK (cargo_quantity >= 0),
            cargo_unit TEXT,
            gross_weight_kg REAL NOT NULL DEFAULT 0
                CHECK (gross_weight_kg >= 0),
            net_weight_kg REAL NOT NULL DEFAULT 0
                CHECK (net_weight_kg >= 0),
            volume_cbm REAL NOT NULL DEFAULT 0
                CHECK (volume_cbm >= 0),

            goods_value REAL NOT NULL DEFAULT 0
                CHECK (goods_value >= 0),
            freight_cost REAL NOT NULL DEFAULT 0
                CHECK (freight_cost >= 0),
            insurance_cost REAL NOT NULL DEFAULT 0
                CHECK (insurance_cost >= 0),
            customs_cost REAL NOT NULL DEFAULT 0
                CHECK (customs_cost >= 0),
            port_charges REAL NOT NULL DEFAULT 0
                CHECK (port_charges >= 0),
            warehouse_cost REAL NOT NULL DEFAULT 0
                CHECK (warehouse_cost >= 0),
            local_transport_cost REAL NOT NULL DEFAULT 0
                CHECK (local_transport_cost >= 0),
            other_costs REAL NOT NULL DEFAULT 0
                CHECK (other_costs >= 0),

            shipment_cost REAL NOT NULL DEFAULT 0
                CHECK (shipment_cost >= 0),
            total_shipment_value REAL NOT NULL DEFAULT 0
                CHECK (total_shipment_value >= 0),

            currency TEXT NOT NULL DEFAULT 'AUD',

            shipment_status TEXT NOT NULL DEFAULT 'Draft'
                CHECK (
                    shipment_status IN (
                        'Draft',
                        'Ordered',
                        'Packed',
                        'Loaded',
                        'Export Customs',
                        'Vessel Departed',
                        'In Transit',
                        'Arrival',
                        'Import Customs',
                        'Customs Clearance',
                        'Warehouse Received',
                        'Delivered',
                        'Delayed',
                        'Cancelled'
                    )
                ),

            current_location TEXT,
            tracking_url TEXT,
            tracking_number TEXT,

            delay_days INTEGER NOT NULL DEFAULT 0
                CHECK (delay_days >= 0),
            delay_reason TEXT,

            customs_clearance_status TEXT,
            customs_entry_number TEXT,
            customs_broker_name TEXT,

            actual_transit_days INTEGER
                CHECK (
                    actual_transit_days IS NULL
                    OR actual_transit_days >= 0
                ),

            estimated_transit_days INTEGER
                CHECK (
                    estimated_transit_days IS NULL
                    OR estimated_transit_days >= 0
                ),

            delivery_address TEXT,
            notes TEXT,

            is_active INTEGER NOT NULL DEFAULT 1
                CHECK (is_active IN (0, 1)),
            is_deleted INTEGER NOT NULL DEFAULT 0
                CHECK (is_deleted IN (0, 1)),

            version INTEGER NOT NULL DEFAULT 1,

            created_by INTEGER,
            updated_by INTEGER,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT
        )
        """
    )


def _create_shipment_timeline_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shipment_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            shipment_id INTEGER NOT NULL,

            stage_name TEXT NOT NULL
                CHECK (
                    stage_name IN (
                        'Ordered',
                        'Packed',
                        'Loaded',
                        'Export Customs',
                        'Vessel Departed',
                        'In Transit',
                        'Arrival',
                        'Import Customs',
                        'Warehouse Received',
                        'Delivered'
                    )
                ),

            stage_order INTEGER NOT NULL
                CHECK (stage_order BETWEEN 1 AND 10),

            stage_status TEXT NOT NULL DEFAULT 'Pending'
                CHECK (
                    stage_status IN (
                        'Pending',
                        'In Progress',
                        'Completed',
                        'Delayed',
                        'Skipped'
                    )
                ),

            planned_date TEXT,
            actual_date TEXT,

            location TEXT,
            responsible_party TEXT,
            notes TEXT,

            completed_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (shipment_id)
                REFERENCES shipments(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE,

            UNIQUE (shipment_id, stage_name)
        )
        """
    )


def _create_shipment_documents_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shipment_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            shipment_id INTEGER NOT NULL,

            document_type TEXT NOT NULL
                CHECK (
                    document_type IN (
                        'Commercial Invoice',
                        'Packing List',
                        'Bill of Lading',
                        'Certificate of Origin',
                        'Phytosanitary Certificate',
                        'Insurance Certificate',
                        'Import Permit',
                        'Customs Documents',
                        'Other'
                    )
                ),

            document_name TEXT NOT NULL,
            document_number TEXT,

            file_name TEXT,
            file_path TEXT,
            file_extension TEXT,
            file_size_bytes INTEGER
                CHECK (
                    file_size_bytes IS NULL
                    OR file_size_bytes >= 0
                ),

            issuing_authority TEXT,
            issued_date TEXT,
            expiry_date TEXT,

            verification_status TEXT NOT NULL DEFAULT 'Pending'
                CHECK (
                    verification_status IN (
                        'Pending',
                        'Verified',
                        'Rejected',
                        'Expired',
                        'Not Required'
                    )
                ),

            is_required INTEGER NOT NULL DEFAULT 1
                CHECK (is_required IN (0, 1)),
            is_received INTEGER NOT NULL DEFAULT 0
                CHECK (is_received IN (0, 1)),

            notes TEXT,

            uploaded_by INTEGER,
            verified_by INTEGER,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (shipment_id)
                REFERENCES shipments(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        )
        """
    )


def _create_shipment_tracking_table(connection) -> None:
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

            source_type TEXT NOT NULL DEFAULT 'Manual'
                CHECK (
                    source_type IN (
                        'Manual',
                        'Shipping Line',
                        'Carrier API',
                        'Port',
                        'Customs',
                        'Warehouse',
                        'System'
                    )
                ),

            source_reference TEXT,
            external_tracking_id TEXT,

            vessel_name TEXT,
            voyage_number TEXT,

            is_exception INTEGER NOT NULL DEFAULT 0
                CHECK (is_exception IN (0, 1)),
            exception_reason TEXT,

            recorded_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (shipment_id)
                REFERENCES shipments(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        )
        """
    )


def _create_shipment_status_history_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shipment_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            shipment_id INTEGER NOT NULL,

            previous_status TEXT,
            new_status TEXT NOT NULL,

            change_reason TEXT,
            changed_by INTEGER,
            changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (shipment_id)
                REFERENCES shipments(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        )
        """
    )


def _create_shipment_indexes(connection) -> None:
    indexes = (
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_status
        ON shipments(shipment_status)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_reference
        ON shipments(shipment_reference)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_booking
        ON shipments(booking_number)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_container
        ON shipments(container_number)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_bl
        ON shipments(bill_of_lading_number)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_supplier
        ON shipments(supplier_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_customer
        ON shipments(customer_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_product
        ON shipments(product_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_rfq
        ON shipments(rfq_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_supplier_quotation
        ON shipments(supplier_quotation_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_freight_quote
        ON shipments(freight_quote_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_warehouse
        ON shipments(warehouse_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_route
        ON shipments(origin_port, destination_port)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_dates
        ON shipments(etd, eta, atd, ata)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipments_active_deleted
        ON shipments(is_active, is_deleted)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipment_timeline_shipment
        ON shipment_timeline(shipment_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipment_timeline_status
        ON shipment_timeline(stage_status)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipment_documents_shipment
        ON shipment_documents(shipment_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipment_documents_type
        ON shipment_documents(document_type)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_shipment_documents_verification
        ON shipment_documents(verification_status)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_tracking_events_shipment
        ON shipment_tracking_events(shipment_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_tracking_events_time
        ON shipment_tracking_events(event_time)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_tracking_events_exception
        ON shipment_tracking_events(is_exception)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_status_history_shipment
        ON shipment_status_history(shipment_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_status_history_changed_at
        ON shipment_status_history(changed_at)
        """,
    )

    for index_sql in indexes:
        connection.execute(index_sql)


def create_default_shipment_timeline(
    shipment_id: int,
) -> None:
    """
    Create the standard ten-stage enterprise shipment timeline.

    Existing stages are preserved through INSERT OR IGNORE.
    """

    if shipment_id <= 0:
        raise ValueError("shipment_id must be a positive integer.")

    stages = (
        (1, "Ordered"),
        (2, "Packed"),
        (3, "Loaded"),
        (4, "Export Customs"),
        (5, "Vessel Departed"),
        (6, "In Transit"),
        (7, "Arrival"),
        (8, "Import Customs"),
        (9, "Warehouse Received"),
        (10, "Delivered"),
    )

    with get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        shipment_exists = connection.execute(
            """
            SELECT 1
            FROM shipments
            WHERE id = ?
              AND is_deleted = 0
            """,
            (shipment_id,),
        ).fetchone()

        if shipment_exists is None:
            raise ValueError(
                f"Shipment with ID {shipment_id} does not exist."
            )

        connection.executemany(
            """
            INSERT OR IGNORE INTO shipment_timeline (
                shipment_id,
                stage_name,
                stage_order,
                stage_status
            )
            VALUES (?, ?, ?, 'Pending')
            """,
            [
                (shipment_id, stage_name, stage_order)
                for stage_order, stage_name in stages
            ],
        )

        connection.commit()


def create_default_document_checklist(
    shipment_id: int,
) -> None:
    """
    Create the standard shipment document checklist.

    The checklist is created only for document types that do not already
    exist for the selected shipment.
    """

    if shipment_id <= 0:
        raise ValueError("shipment_id must be a positive integer.")

    required_documents = (
        "Commercial Invoice",
        "Packing List",
        "Bill of Lading",
        "Certificate of Origin",
        "Phytosanitary Certificate",
        "Insurance Certificate",
        "Import Permit",
        "Customs Documents",
    )

    with get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        shipment_exists = connection.execute(
            """
            SELECT 1
            FROM shipments
            WHERE id = ?
              AND is_deleted = 0
            """,
            (shipment_id,),
        ).fetchone()

        if shipment_exists is None:
            raise ValueError(
                f"Shipment with ID {shipment_id} does not exist."
            )

        for document_type in required_documents:
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
                SELECT ?, ?, ?, 'Pending', 1, 0
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
                    shipment_id,
                    document_type,
                ),
            )

        connection.commit()