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
        """Insert a shipment and return its database ID."""

        columns = [
            "shipment_reference",
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
            "created_by",
            "updated_by",
        ]

        values = [data.get(column) for column in columns]
        placeholders = ", ".join("?" for _ in columns)
        column_names = ", ".join(columns)

        with get_connection() as connection:
            cursor = connection.execute(
                f"""
                INSERT INTO shipments ({column_names})
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