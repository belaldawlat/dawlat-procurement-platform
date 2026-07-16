"""
Shipment repository for the Dawlat Procurement Platform.

This repository contains shipment-domain database operations only.
Business rules belong in the service layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from database.connection import get_connection


class ShipmentRepository:
    """Database access layer for shipments and related records."""

    @staticmethod
    def create_shipment(data: dict[str, Any]) -> int:
        """
        Insert a shipment and return its database ID.

        The database is currently in a controlled compatibility period.
        This method writes both the original shipment columns and the new
        enterprise columns so existing screens and future services read the
        same record without duplicate shipment systems.
        """

        payload = _prepare_compatible_shipment_payload(data)

        columns = [
            # Original columns required by the current application
            "shipment_number",
            "shipment_type",
            "status",
            "rfq_id",
            "supplier_quote_id",
            "logistics_quote_id",
            "warehouse_quote_id",
            "supplier_name",
            "logistics_provider",
            "warehouse_name",
            "product_name",
            "cargo_description",
            "quantity",
            "unit",
            "gross_weight_kg",
            "volume_cbm",
            "origin_country",
            "origin_location",
            "destination_country",
            "destination_location",
            "transport_mode",
            "service_type",
            "incoterm",
            "container_type",
            "booking_number",
            "bill_of_lading_number",
            "airway_bill_number",
            "container_number",
            "seal_number",
            "tracking_number",
            "carrier_name",
            "vessel_name",
            "voyage_number",
            "flight_number",
            "planned_pickup_date",
            "actual_pickup_date",
            "etd",
            "actual_departure_date",
            "eta",
            "actual_arrival_date",
            "customs_clearance_date",
            "warehouse_delivery_date",
            "customs_status",
            "biosecurity_status",
            "inspection_status",
            "document_status",
            "commercial_invoice_received",
            "packing_list_received",
            "bill_of_lading_received",
            "certificate_of_origin_received",
            "phytosanitary_received",
            "fumigation_received",
            "insurance_certificate_received",
            "import_permit_received",
            "other_documents",
            "currency",
            "goods_value",
            "freight_cost",
            "insurance_cost",
            "customs_cost",
            "biosecurity_cost",
            "port_cost",
            "local_delivery_cost",
            "storage_cost",
            "other_costs",
            "delay_reason",
            "risk_level",
            "priority",
            "inventory_received",
            "notes",
            "created_at",
            "updated_at",

            # New enterprise columns
            "shipment_reference",
            "shipment_name",
            "supplier_quotation_id",
            "freight_quote_id",
            "warehouse_id",
            "supplier_id",
            "customer_id",
            "product_id",
            "customer_name",
            "shipping_line",
            "origin_city",
            "origin_port",
            "destination_city",
            "destination_port",
            "atd",
            "ata",
            "insurance_required",
            "insurance_provider",
            "insurance_policy_number",
            "insurance_value",
            "cargo_quantity",
            "cargo_unit",
            "net_weight_kg",
            "port_charges",
            "warehouse_cost",
            "local_transport_cost",
            "shipment_cost",
            "total_shipment_value",
            "shipment_status",
            "current_location",
            "tracking_url",
            "delay_days",
            "customs_clearance_status",
            "customs_entry_number",
            "customs_broker_name",
            "actual_transit_days",
            "estimated_transit_days",
            "delivery_address",
            "is_active",
            "is_deleted",
            "version",
            "created_by",
            "updated_by",
            "deleted_at",
        ]

        values = [payload.get(column) for column in columns]
        placeholders = ", ".join("?" for _ in columns)

        with get_connection() as connection:
            cursor = connection.execute(
                f"""
                INSERT INTO shipments (
                    {", ".join(columns)}
                )
                VALUES ({placeholders})
                """,
                values,
            )
            connection.commit()
            return int(cursor.lastrowid)

    @staticmethod
    def get_by_id(shipment_id: int) -> dict[str, Any] | None:
        """Return one active shipment by ID."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT *
                FROM shipments
                WHERE id = ?
                  AND is_deleted = 0
                """,
                (shipment_id,),
            ).fetchone()

    @staticmethod
    def get_by_reference(
        shipment_reference: str,
    ) -> dict[str, Any] | None:
        """Return one shipment by its unique reference."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT *
                FROM shipments
                WHERE shipment_reference = ?
                  AND is_deleted = 0
                """,
                (shipment_reference,),
            ).fetchone()

    @staticmethod
    def list_shipments(
        search: str = "",
        statuses: list[str] | None = None,
        container_types: list[str] | None = None,
        suppliers: list[str] | None = None,
        origin_ports: list[str] | None = None,
        destination_ports: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        """Return shipments using enterprise register filters."""

        conditions = ["is_deleted = 0"]
        parameters: list[Any] = []

        if not include_inactive:
            conditions.append("is_active = 1")

        if search.strip():
            search_value = f"%{search.strip()}%"
            conditions.append(
                """
                (
                    shipment_reference LIKE ?
                    OR shipment_name LIKE ?
                    OR supplier_name LIKE ?
                    OR customer_name LIKE ?
                    OR product_name LIKE ?
                    OR booking_number LIKE ?
                    OR container_number LIKE ?
                    OR bill_of_lading_number LIKE ?
                    OR shipping_line LIKE ?
                    OR vessel_name LIKE ?
                    OR origin_port LIKE ?
                    OR destination_port LIKE ?
                )
                """
            )
            parameters.extend([search_value] * 12)

        _add_in_filter(
            conditions,
            parameters,
            "shipment_status",
            statuses,
        )
        _add_in_filter(
            conditions,
            parameters,
            "container_type",
            container_types,
        )
        _add_in_filter(
            conditions,
            parameters,
            "supplier_name",
            suppliers,
        )
        _add_in_filter(
            conditions,
            parameters,
            "origin_port",
            origin_ports,
        )
        _add_in_filter(
            conditions,
            parameters,
            "destination_port",
            destination_ports,
        )

        if date_from:
            conditions.append("COALESCE(atd, etd, created_at) >= ?")
            parameters.append(date_from)

        if date_to:
            conditions.append("COALESCE(atd, etd, created_at) <= ?")
            parameters.append(date_to)

        where_clause = " AND ".join(conditions)

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                f"""
                SELECT *
                FROM shipments
                WHERE {where_clause}
                ORDER BY
                    CASE shipment_status
                        WHEN 'Delayed' THEN 1
                        WHEN 'Customs Clearance' THEN 2
                        WHEN 'Import Customs' THEN 3
                        WHEN 'In Transit' THEN 4
                        WHEN 'Vessel Departed' THEN 5
                        WHEN 'Loaded' THEN 6
                        WHEN 'Packed' THEN 7
                        WHEN 'Ordered' THEN 8
                        WHEN 'Draft' THEN 9
                        WHEN 'Delivered' THEN 10
                        WHEN 'Cancelled' THEN 11
                        ELSE 12
                    END,
                    COALESCE(eta, etd, created_at) ASC
                """,
                parameters,
            ).fetchall()

    @staticmethod
    def update_shipment(
        shipment_id: int,
        data: dict[str, Any],
        expected_version: int | None = None,
    ) -> bool:
        """
        Update a shipment.

        expected_version supports optimistic locking and prevents one user
        from silently overwriting another user's changes.
        """

        allowed_columns = {
            "shipment_name",
            "rfq_id",
            "supplier_quotation_id",
            "freight_quote_id",
            "warehouse_id",
            "supplier_id",
            "customer_id",
            "product_id",
            "supplier_name",
            "customer_name",
            "product_name",
            "container_type",
            "shipping_line",
            "vessel_name",
            "voyage_number",
            "booking_number",
            "container_number",
            "seal_number",
            "bill_of_lading_number",
            "origin_country",
            "origin_city",
            "origin_port",
            "destination_country",
            "destination_city",
            "destination_port",
            "etd",
            "eta",
            "atd",
            "ata",
            "incoterm",
            "insurance_required",
            "insurance_provider",
            "insurance_policy_number",
            "insurance_value",
            "cargo_quantity",
            "cargo_unit",
            "gross_weight_kg",
            "net_weight_kg",
            "volume_cbm",
            "goods_value",
            "freight_cost",
            "insurance_cost",
            "customs_cost",
            "port_charges",
            "warehouse_cost",
            "local_transport_cost",
            "other_costs",
            "shipment_cost",
            "total_shipment_value",
            "currency",
            "shipment_status",
            "current_location",
            "tracking_url",
            "tracking_number",
            "delay_days",
            "delay_reason",
            "customs_clearance_status",
            "customs_entry_number",
            "customs_broker_name",
            "actual_transit_days",
            "estimated_transit_days",
            "delivery_address",
            "notes",
            "is_active",
            "updated_by",
        }

        updates = {
            key: value
            for key, value in data.items()
            if key in allowed_columns
        }

        if not updates:
            return False

        assignments = [f"{column} = ?" for column in updates]
        parameters = list(updates.values())

        assignments.extend(
            [
                "updated_at = CURRENT_TIMESTAMP",
                "version = version + 1",
            ]
        )

        conditions = [
            "id = ?",
            "is_deleted = 0",
        ]
        parameters.append(shipment_id)

        if expected_version is not None:
            conditions.append("version = ?")
            parameters.append(expected_version)

        with get_connection() as connection:
            cursor = connection.execute(
                f"""
                UPDATE shipments
                SET {", ".join(assignments)}
                WHERE {" AND ".join(conditions)}
                """,
                parameters,
            )
            connection.commit()
            return cursor.rowcount == 1

    @staticmethod
    def soft_delete(
        shipment_id: int,
        deleted_by: int | None = None,
    ) -> bool:
        """Soft-delete a shipment while retaining audit data."""

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE shipments
                SET
                    is_deleted = 1,
                    is_active = 0,
                    deleted_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = ?,
                    version = version + 1
                WHERE id = ?
                  AND is_deleted = 0
                """,
                (deleted_by, shipment_id),
            )
            connection.commit()
            return cursor.rowcount == 1

    @staticmethod
    def restore_shipment(
        shipment_id: int,
        restored_by: int | None = None,
    ) -> bool:
        """Restore a previously soft-deleted shipment."""

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE shipments
                SET
                    is_deleted = 0,
                    is_active = 1,
                    deleted_at = NULL,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = ?,
                    version = version + 1
                WHERE id = ?
                  AND is_deleted = 1
                """,
                (restored_by, shipment_id),
            )
            connection.commit()
            return cursor.rowcount == 1

    @staticmethod
    def get_dashboard_metrics() -> dict[str, Any]:
        """Return shipment dashboard KPI values."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT
                    COUNT(
                        CASE
                            WHEN shipment_status NOT IN (
                                'Delivered',
                                'Cancelled'
                            )
                            THEN 1
                        END
                    ) AS active_shipments,

                    COUNT(
                        CASE
                            WHEN shipment_status IN (
                                'Vessel Departed',
                                'In Transit',
                                'Arrival'
                            )
                            THEN 1
                        END
                    ) AS in_transit,

                    COUNT(
                        CASE
                            WHEN shipment_status = 'Delivered'
                            THEN 1
                        END
                    ) AS delivered,

                    COUNT(
                        CASE
                            WHEN shipment_status = 'Delayed'
                                 OR delay_days > 0
                            THEN 1
                        END
                    ) AS delayed,

                    COUNT(
                        CASE
                            WHEN shipment_status IN (
                                'Export Customs',
                                'Import Customs',
                                'Customs Clearance'
                            )
                            THEN 1
                        END
                    ) AS customs_clearance,

                    COALESCE(
                        SUM(total_shipment_value),
                        0
                    ) AS total_shipment_value
                FROM shipments
                WHERE is_deleted = 0
                  AND is_active = 1
                """
            ).fetchone()

    @staticmethod
    def get_timeline(shipment_id: int) -> list[dict[str, Any]]:
        """Return the ordered timeline for one shipment."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT *
                FROM shipment_timeline
                WHERE shipment_id = ?
                ORDER BY stage_order ASC
                """,
                (shipment_id,),
            ).fetchall()

    @staticmethod
    def update_timeline_stage(
        shipment_id: int,
        stage_name: str,
        stage_status: str,
        planned_date: str | None = None,
        actual_date: str | None = None,
        location: str | None = None,
        responsible_party: str | None = None,
        notes: str | None = None,
        completed_by: int | None = None,
    ) -> bool:
        """Update a shipment timeline milestone."""

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE shipment_timeline
                SET
                    stage_status = ?,
                    planned_date = ?,
                    actual_date = ?,
                    location = ?,
                    responsible_party = ?,
                    notes = ?,
                    completed_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE shipment_id = ?
                  AND stage_name = ?
                """,
                (
                    stage_status,
                    planned_date,
                    actual_date,
                    location,
                    responsible_party,
                    notes,
                    completed_by,
                    shipment_id,
                    stage_name,
                ),
            )
            connection.commit()
            return cursor.rowcount == 1

    @staticmethod
    def list_documents(
        shipment_id: int,
    ) -> list[dict[str, Any]]:
        """Return all documents for one shipment."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT *
                FROM shipment_documents
                WHERE shipment_id = ?
                ORDER BY
                    is_required DESC,
                    document_type ASC,
                    created_at DESC
                """,
                (shipment_id,),
            ).fetchall()

    @staticmethod
    def add_document(data: dict[str, Any]) -> int:
        """Add a shipment document record."""

        columns = [
            "shipment_id",
            "document_type",
            "document_name",
            "document_number",
            "file_name",
            "file_path",
            "file_extension",
            "file_size_bytes",
            "issuing_authority",
            "issued_date",
            "expiry_date",
            "verification_status",
            "is_required",
            "is_received",
            "notes",
            "uploaded_by",
            "verified_by",
        ]

        values = [data.get(column) for column in columns]
        placeholders = ", ".join("?" for _ in columns)

        with get_connection() as connection:
            cursor = connection.execute(
                f"""
                INSERT INTO shipment_documents (
                    {", ".join(columns)}
                )
                VALUES ({placeholders})
                """,
                values,
            )
            connection.commit()
            return int(cursor.lastrowid)

    @staticmethod
    def update_document(
        document_id: int,
        data: dict[str, Any],
    ) -> bool:
        """Update a shipment document record."""

        allowed_columns = {
            "document_type",
            "document_name",
            "document_number",
            "file_name",
            "file_path",
            "file_extension",
            "file_size_bytes",
            "issuing_authority",
            "issued_date",
            "expiry_date",
            "verification_status",
            "is_required",
            "is_received",
            "notes",
            "uploaded_by",
            "verified_by",
        }

        updates = {
            key: value
            for key, value in data.items()
            if key in allowed_columns
        }

        if not updates:
            return False

        assignments = [f"{column} = ?" for column in updates]
        assignments.append("updated_at = CURRENT_TIMESTAMP")

        parameters = list(updates.values())
        parameters.append(document_id)

        with get_connection() as connection:
            cursor = connection.execute(
                f"""
                UPDATE shipment_documents
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                parameters,
            )
            connection.commit()
            return cursor.rowcount == 1

    @staticmethod
    def delete_document(document_id: int) -> bool:
        """Delete one shipment document record."""

        with get_connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM shipment_documents
                WHERE id = ?
                """,
                (document_id,),
            )
            connection.commit()
            return cursor.rowcount == 1

    @staticmethod
    def list_tracking_events(
        shipment_id: int,
    ) -> list[dict[str, Any]]:
        """Return tracking events newest first."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT *
                FROM shipment_tracking_events
                WHERE shipment_id = ?
                ORDER BY event_time DESC, id DESC
                """,
                (shipment_id,),
            ).fetchall()

    @staticmethod
    def add_tracking_event(data: dict[str, Any]) -> int:
        """Create a shipment tracking event."""

        columns = [
            "shipment_id",
            "event_code",
            "event_name",
            "event_description",
            "location_name",
            "city",
            "country",
            "port_code",
            "latitude",
            "longitude",
            "event_time",
            "source_type",
            "source_reference",
            "external_tracking_id",
            "vessel_name",
            "voyage_number",
            "is_exception",
            "exception_reason",
            "recorded_by",
        ]

        values = [data.get(column) for column in columns]
        placeholders = ", ".join("?" for _ in columns)

        with get_connection() as connection:
            cursor = connection.execute(
                f"""
                INSERT INTO shipment_tracking_events (
                    {", ".join(columns)}
                )
                VALUES ({placeholders})
                """,
                values,
            )
            connection.commit()
            return int(cursor.lastrowid)

    @staticmethod
    def add_status_history(
        shipment_id: int,
        previous_status: str | None,
        new_status: str,
        change_reason: str | None = None,
        changed_by: int | None = None,
    ) -> int:
        """Record a shipment status transition."""

        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO shipment_status_history (
                    shipment_id,
                    previous_status,
                    new_status,
                    change_reason,
                    changed_by
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    shipment_id,
                    previous_status,
                    new_status,
                    change_reason,
                    changed_by,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    @staticmethod
    def get_status_history(
        shipment_id: int,
    ) -> list[dict[str, Any]]:
        """Return complete status audit history."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT *
                FROM shipment_status_history
                WHERE shipment_id = ?
                ORDER BY changed_at DESC, id DESC
                """,
                (shipment_id,),
            ).fetchall()

    @staticmethod
    def get_filter_options() -> dict[str, list[str]]:
        """Return distinct values used by register filters."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            rows = connection.execute(
                """
                SELECT
                    shipment_status,
                    container_type,
                    supplier_name,
                    origin_port,
                    destination_port
                FROM shipments
                WHERE is_deleted = 0
                """
            ).fetchall()

        return {
            "statuses": _unique_values(
                rows,
                "shipment_status",
            ),
            "container_types": _unique_values(
                rows,
                "container_type",
            ),
            "suppliers": _unique_values(
                rows,
                "supplier_name",
            ),
            "origin_ports": _unique_values(
                rows,
                "origin_port",
            ),
            "destination_ports": _unique_values(
                rows,
                "destination_port",
            ),
        }

    @staticmethod
    def get_analytics_summary() -> dict[str, Any]:
        """Return overall shipment analytics metrics."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT
                    ROUND(
                        AVG(
                            CASE
                                WHEN actual_transit_days IS NOT NULL
                                THEN actual_transit_days
                            END
                        ),
                        1
                    ) AS average_transit_days,

                    COUNT(
                        CASE
                            WHEN delay_days > 0
                                 OR shipment_status = 'Delayed'
                            THEN 1
                        END
                    ) AS delayed_shipments,

                    ROUND(
                        AVG(
                            CASE
                                WHEN delay_days > 0
                                THEN delay_days
                            END
                        ),
                        1
                    ) AS average_delay_days,

                    COALESCE(
                        SUM(shipment_cost),
                        0
                    ) AS total_shipment_cost,

                    COALESCE(
                        AVG(shipment_cost),
                        0
                    ) AS average_shipment_cost,

                    COALESCE(
                        SUM(goods_value),
                        0
                    ) AS total_goods_value,

                    COALESCE(
                        SUM(total_shipment_value),
                        0
                    ) AS total_shipment_value
                FROM shipments
                WHERE is_deleted = 0
                  AND shipment_status != 'Cancelled'
                """
            ).fetchone()

    @staticmethod
    def get_country_performance() -> list[dict[str, Any]]:
        """Return shipment performance grouped by origin country."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT
                    COALESCE(origin_country, 'Unknown') AS origin_country,
                    COUNT(*) AS shipment_count,
                    ROUND(AVG(actual_transit_days), 1)
                        AS average_transit_days,
                    ROUND(AVG(delay_days), 1)
                        AS average_delay_days,
                    COALESCE(SUM(shipment_cost), 0)
                        AS total_shipment_cost,
                    COALESCE(SUM(total_shipment_value), 0)
                        AS total_shipment_value
                FROM shipments
                WHERE is_deleted = 0
                  AND shipment_status != 'Cancelled'
                GROUP BY COALESCE(origin_country, 'Unknown')
                ORDER BY shipment_count DESC
                """
            ).fetchall()

    @staticmethod
    def get_shipping_line_performance() -> list[dict[str, Any]]:
        """Return performance grouped by shipping line."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT
                    COALESCE(shipping_line, 'Not Assigned')
                        AS shipping_line,
                    COUNT(*) AS shipment_count,
                    ROUND(AVG(actual_transit_days), 1)
                        AS average_transit_days,
                    ROUND(AVG(delay_days), 1)
                        AS average_delay_days,
                    COALESCE(SUM(shipment_cost), 0)
                        AS total_shipment_cost,

                    ROUND(
                        100.0 * SUM(
                            CASE
                                WHEN delay_days = 0
                                     AND shipment_status != 'Delayed'
                                THEN 1
                                ELSE 0
                            END
                        ) / COUNT(*),
                        1
                    ) AS on_time_percentage

                FROM shipments
                WHERE is_deleted = 0
                  AND shipment_status != 'Cancelled'
                GROUP BY COALESCE(
                    shipping_line,
                    'Not Assigned'
                )
                ORDER BY shipment_count DESC
                """
            ).fetchall()

    @staticmethod
    def get_cost_analysis() -> list[dict[str, Any]]:
        """Return shipment-level cost analysis."""

        with get_connection() as connection:
            connection.row_factory = _dict_factory

            return connection.execute(
                """
                SELECT
                    id,
                    shipment_reference,
                    shipment_name,
                    supplier_name,
                    product_name,
                    currency,
                    goods_value,
                    freight_cost,
                    insurance_cost,
                    customs_cost,
                    port_charges,
                    warehouse_cost,
                    local_transport_cost,
                    other_costs,
                    shipment_cost,
                    total_shipment_value
                FROM shipments
                WHERE is_deleted = 0
                  AND shipment_status != 'Cancelled'
                ORDER BY total_shipment_value DESC
                """
            ).fetchall()

    @staticmethod
    def count_by_reference_prefix(prefix: str) -> int:
        """Count shipment references beginning with a prefix."""

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*)
                FROM shipments
                WHERE shipment_reference LIKE ?
                """,
                (f"{prefix}%",),
            ).fetchone()

            return int(row[0]) if row else 0

    @staticmethod
    def shipment_exists(shipment_id: int) -> bool:
        """Check whether an active shipment exists."""

        with get_connection() as connection:
            result = connection.execute(
                """
                SELECT 1
                FROM shipments
                WHERE id = ?
                  AND is_deleted = 0
                """,
                (shipment_id,),
            ).fetchone()

            return result is not None

    @staticmethod
    def reference_exists(shipment_reference: str) -> bool:
        """Check whether a shipment reference already exists."""

        with get_connection() as connection:
            result = connection.execute(
                """
                SELECT 1
                FROM shipments
                WHERE shipment_reference = ?
                """,
                (shipment_reference,),
            ).fetchone()

            return result is not None

    @staticmethod
    def get_current_timestamp() -> str:
        """Return a consistent database-compatible timestamp."""

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def _prepare_compatible_shipment_payload(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Build one canonical payload for both legacy and enterprise columns.

    This is temporary compatibility infrastructure for the controlled
    Shipment module refactor. It prevents data loss and guarantees that
    current Streamlit screens and the new enterprise services see the same
    shipment record.
    """

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = dict(data)

    reference = _first_value(
        payload.get("shipment_reference"),
        payload.get("shipment_number"),
    )

    if not reference:
        raise ValueError(
            "shipment_reference or shipment_number is required."
        )

    product_name = _first_value(
        payload.get("product_name"),
        "Unspecified Product",
    )
    supplier_name = _first_value(
        payload.get("supplier_name"),
        "Unassigned Supplier",
    )

    origin_port = _first_value(
        payload.get("origin_port"),
        payload.get("origin_location"),
        "Not Specified",
    )
    destination_port = _first_value(
        payload.get("destination_port"),
        payload.get("destination_location"),
        "Not Specified",
    )

    shipment_status = _first_value(
        payload.get("shipment_status"),
        payload.get("status"),
        "Draft",
    )

    quantity = _number(
        _first_value(
            payload.get("cargo_quantity"),
            payload.get("quantity"),
            0,
        )
    )
    unit = _first_value(
        payload.get("cargo_unit"),
        payload.get("unit"),
        "unit",
    )

    freight_cost = _number(payload.get("freight_cost"))
    insurance_cost = _number(payload.get("insurance_cost"))
    customs_cost = _number(payload.get("customs_cost"))
    biosecurity_cost = _number(payload.get("biosecurity_cost"))
    port_cost = _number(
        _first_value(
            payload.get("port_charges"),
            payload.get("port_cost"),
            0,
        )
    )
    local_delivery_cost = _number(
        _first_value(
            payload.get("local_transport_cost"),
            payload.get("local_delivery_cost"),
            0,
        )
    )
    storage_cost = _number(
        _first_value(
            payload.get("warehouse_cost"),
            payload.get("storage_cost"),
            0,
        )
    )
    other_costs = _number(payload.get("other_costs"))
    goods_value = _number(payload.get("goods_value"))

    shipment_cost = (
        freight_cost
        + insurance_cost
        + customs_cost
        + biosecurity_cost
        + port_cost
        + local_delivery_cost
        + storage_cost
        + other_costs
    )
    total_value = goods_value + shipment_cost

    payload.update(
        {
            # Legacy identity and required values
            "shipment_number": reference,
            "shipment_type": _first_value(
                payload.get("shipment_type"),
                "Import Shipment",
            ),
            "status": shipment_status,
            "supplier_name": supplier_name,
            "product_name": product_name,
            "cargo_description": _first_value(
                payload.get("cargo_description"),
                product_name,
            ),
            "quantity": quantity,
            "unit": unit,
            "origin_country": _first_value(
                payload.get("origin_country"),
                "Not Specified",
            ),
            "origin_location": origin_port,
            "destination_country": _first_value(
                payload.get("destination_country"),
                "Not Specified",
            ),
            "destination_location": destination_port,
            "transport_mode": _first_value(
                payload.get("transport_mode"),
                "Sea Freight",
            ),
            "service_type": _first_value(
                payload.get("service_type"),
                "Port to Port",
            ),
            "incoterm": _first_value(
                payload.get("incoterm"),
                "Not Specified",
            ),
            "customs_status": _first_value(
                payload.get("customs_status"),
                payload.get("customs_clearance_status"),
                "Not Started",
            ),
            "biosecurity_status": _first_value(
                payload.get("biosecurity_status"),
                "Not Required",
            ),
            "inspection_status": _first_value(
                payload.get("inspection_status"),
                "Not Required",
            ),
            "document_status": _first_value(
                payload.get("document_status"),
                "Incomplete",
            ),
            "risk_level": _first_value(
                payload.get("risk_level"),
                "Medium",
            ),
            "priority": _first_value(
                payload.get("priority"),
                "Normal",
            ),
            "created_at": _first_value(
                payload.get("created_at"),
                now,
            ),
            "updated_at": _first_value(
                payload.get("updated_at"),
                now,
            ),

            # Linked-record aliases
            "supplier_quote_id": _first_value(
                payload.get("supplier_quote_id"),
                payload.get("supplier_quotation_id"),
            ),
            "logistics_quote_id": _first_value(
                payload.get("logistics_quote_id"),
                payload.get("freight_quote_id"),
            ),
            "warehouse_quote_id": _first_value(
                payload.get("warehouse_quote_id"),
                payload.get("warehouse_id"),
            ),
            "supplier_quotation_id": _first_value(
                payload.get("supplier_quotation_id"),
                payload.get("supplier_quote_id"),
            ),
            "freight_quote_id": _first_value(
                payload.get("freight_quote_id"),
                payload.get("logistics_quote_id"),
            ),
            "warehouse_id": _first_value(
                payload.get("warehouse_id"),
                payload.get("warehouse_quote_id"),
            ),

            # Shipping aliases
            "shipment_reference": reference,
            "shipment_name": _first_value(
                payload.get("shipment_name"),
                f"{product_name} Shipment",
            ),
            "shipping_line": _first_value(
                payload.get("shipping_line"),
                payload.get("carrier_name"),
            ),
            "carrier_name": _first_value(
                payload.get("carrier_name"),
                payload.get("shipping_line"),
            ),
            "origin_port": origin_port,
            "destination_port": destination_port,
            "atd": _first_value(
                payload.get("atd"),
                payload.get("actual_departure_date"),
            ),
            "ata": _first_value(
                payload.get("ata"),
                payload.get("actual_arrival_date"),
            ),
            "actual_departure_date": _first_value(
                payload.get("actual_departure_date"),
                payload.get("atd"),
            ),
            "actual_arrival_date": _first_value(
                payload.get("actual_arrival_date"),
                payload.get("ata"),
            ),

            # Cargo aliases
            "cargo_quantity": quantity,
            "cargo_unit": unit,
            "gross_weight_kg": _number(
                payload.get("gross_weight_kg")
            ),
            "net_weight_kg": _number(
                payload.get("net_weight_kg")
            ),
            "volume_cbm": _number(payload.get("volume_cbm")),

            # Cost aliases and calculated totals
            "goods_value": goods_value,
            "freight_cost": freight_cost,
            "insurance_cost": insurance_cost,
            "customs_cost": customs_cost,
            "biosecurity_cost": biosecurity_cost,
            "port_cost": port_cost,
            "port_charges": port_cost,
            "local_delivery_cost": local_delivery_cost,
            "local_transport_cost": local_delivery_cost,
            "storage_cost": storage_cost,
            "warehouse_cost": storage_cost,
            "other_costs": other_costs,
            "shipment_cost": shipment_cost,
            "total_shipment_value": total_value,

            # Workflow aliases
            "shipment_status": shipment_status,
            "customs_clearance_status": _first_value(
                payload.get("customs_clearance_status"),
                payload.get("customs_status"),
                "Not Started",
            ),
            "current_location": _first_value(
                payload.get("current_location"),
                origin_port,
            ),
            "delay_days": int(
                _number(payload.get("delay_days"))
            ),

            # Boolean and governance defaults
            "insurance_required": _boolean_int(
                payload.get("insurance_required")
            ),
            "insurance_value": _number(
                payload.get("insurance_value")
            ),
            "commercial_invoice_received": _boolean_int(
                payload.get("commercial_invoice_received")
            ),
            "packing_list_received": _boolean_int(
                payload.get("packing_list_received")
            ),
            "bill_of_lading_received": _boolean_int(
                payload.get("bill_of_lading_received")
            ),
            "certificate_of_origin_received": _boolean_int(
                payload.get("certificate_of_origin_received")
            ),
            "phytosanitary_received": _boolean_int(
                payload.get("phytosanitary_received")
            ),
            "fumigation_received": _boolean_int(
                payload.get("fumigation_received")
            ),
            "insurance_certificate_received": _boolean_int(
                payload.get("insurance_certificate_received")
            ),
            "import_permit_received": _boolean_int(
                payload.get("import_permit_received")
            ),
            "inventory_received": _boolean_int(
                payload.get("inventory_received")
            ),
            "is_active": _boolean_int(
                payload.get("is_active", 1)
            ),
            "is_deleted": _boolean_int(
                payload.get("is_deleted", 0)
            ),
            "version": int(
                _number(payload.get("version", 1))
            )
            or 1,
        }
    )

    return payload


def _first_value(*values: Any) -> Any:
    """Return the first value that is not None or an empty string."""

    for value in values:
        if value is None:
            continue

        if isinstance(value, str) and not value.strip():
            continue

        return value

    return None


def _number(value: Any) -> float:
    """Convert optional numeric input to a safe float."""

    if value in (None, ""):
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid numeric value: {value}"
        ) from error


def _boolean_int(value: Any) -> int:
    """Convert common truthy values to SQLite integer booleans."""

    if isinstance(value, str):
        return int(
            value.strip().lower()
            in {"1", "true", "yes", "y", "on"}
        )

    return int(bool(value))

def _dict_factory(cursor, row) -> dict[str, Any]:
    """Convert SQLite rows to dictionaries."""

    return {
        description[0]: row[index]
        for index, description in enumerate(cursor.description)
    }


def _add_in_filter(
    conditions: list[str],
    parameters: list[Any],
    column: str,
    values: list[str] | None,
) -> None:
    """Add a safe SQL IN filter."""

    cleaned_values = [
        value
        for value in (values or [])
        if value is not None and str(value).strip()
    ]

    if not cleaned_values:
        return

    placeholders = ", ".join("?" for _ in cleaned_values)
    conditions.append(f"{column} IN ({placeholders})")
    parameters.extend(cleaned_values)


def _unique_values(
    rows: list[dict[str, Any]],
    key: str,
) -> list[str]:
    """Return sorted, non-empty unique values."""

    return sorted(
        {
            str(row[key]).strip()
            for row in rows
            if row.get(key) is not None
            and str(row[key]).strip()
        }
    )