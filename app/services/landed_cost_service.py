from datetime import datetime
from typing import Optional

from database.connection import get_connection
from models.landed_cost import LandedCost


def row_to_landed_cost(row) -> LandedCost:
    return LandedCost(
        id=row["id"],
        name=row["name"],
        rfq_id=row["rfq_id"],
        supplier_quote_id=row["supplier_quote_id"],
        product_name=row["product_name"],
        supplier_name=row["supplier_name"],
        origin_country=row["origin_country"],
        destination=row["destination"],
        source_currency=row["source_currency"],
        reporting_currency=row["reporting_currency"],
        exchange_rate=float(row["exchange_rate"]),
        quantity=float(row["quantity"]),
        unit=row["unit"],
        unit_price_source=float(row["unit_price_source"]),
        goods_value_source=float(row["goods_value_source"]),
        goods_value_reporting=float(row["goods_value_reporting"]),
        international_freight=float(row["international_freight"]),
        international_insurance=float(row["international_insurance"]),
        origin_charges=float(row["origin_charges"]),
        destination_port_charges=float(
            row["destination_port_charges"]
        ),
        customs_broker_fee=float(row["customs_broker_fee"]),
        biosecurity_fee=float(row["biosecurity_fee"]),
        inspection_fee=float(row["inspection_fee"]),
        duty_rate=float(row["duty_rate"]),
        duty_amount=float(row["duty_amount"]),
        gst_rate=float(row["gst_rate"]),
        gst_amount=float(row["gst_amount"]),
        local_transport=float(row["local_transport"]),
        warehouse_cost=float(row["warehouse_cost"]),
        packaging_cost=float(row["packaging_cost"]),
        bank_fee=float(row["bank_fee"]),
        finance_cost=float(row["finance_cost"]),
        contingency=float(row["contingency"]),
        other_costs=float(row["other_costs"]),
        total_landed_cost=float(row["total_landed_cost"]),
        landed_cost_per_unit=float(row["landed_cost_per_unit"]),
        selling_price_per_unit=float(row["selling_price_per_unit"]),
        expected_revenue=float(row["expected_revenue"]),
        gross_profit=float(row["gross_profit"]),
        gross_margin_percent=float(row["gross_margin_percent"]),
        roi_percent=float(row["roi_percent"]),
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_landed_cost(record: LandedCost) -> int:
    timestamp = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO landed_costs (
                name,
                rfq_id,
                supplier_quote_id,
                product_name,
                supplier_name,
                origin_country,
                destination,
                source_currency,
                reporting_currency,
                exchange_rate,
                quantity,
                unit,
                unit_price_source,
                goods_value_source,
                goods_value_reporting,
                international_freight,
                international_insurance,
                origin_charges,
                destination_port_charges,
                customs_broker_fee,
                biosecurity_fee,
                inspection_fee,
                duty_rate,
                duty_amount,
                gst_rate,
                gst_amount,
                local_transport,
                warehouse_cost,
                packaging_cost,
                bank_fee,
                finance_cost,
                contingency,
                other_costs,
                total_landed_cost,
                landed_cost_per_unit,
                selling_price_per_unit,
                expected_revenue,
                gross_profit,
                gross_margin_percent,
                roi_percent,
                status,
                notes,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                record.name.strip(),
                record.rfq_id,
                record.supplier_quote_id,
                record.product_name.strip(),
                record.supplier_name.strip()
                if record.supplier_name
                else None,
                record.origin_country.strip()
                if record.origin_country
                else None,
                record.destination.strip(),
                record.source_currency,
                record.reporting_currency,
                record.exchange_rate,
                record.quantity,
                record.unit,
                record.unit_price_source,
                record.goods_value_source,
                record.goods_value_reporting,
                record.international_freight,
                record.international_insurance,
                record.origin_charges,
                record.destination_port_charges,
                record.customs_broker_fee,
                record.biosecurity_fee,
                record.inspection_fee,
                record.duty_rate,
                record.duty_amount,
                record.gst_rate,
                record.gst_amount,
                record.local_transport,
                record.warehouse_cost,
                record.packaging_cost,
                record.bank_fee,
                record.finance_cost,
                record.contingency,
                record.other_costs,
                record.total_landed_cost,
                record.landed_cost_per_unit,
                record.selling_price_per_unit,
                record.expected_revenue,
                record.gross_profit,
                record.gross_margin_percent,
                record.roi_percent,
                record.status,
                record.notes.strip() if record.notes else None,
                timestamp,
                timestamp,
            ),
        )

        return int(cursor.lastrowid)


def get_landed_costs(
    search: str = "",
    status: str = "All",
) -> list[LandedCost]:
    query = """
        SELECT *
        FROM landed_costs
        WHERE 1 = 1
    """

    parameters: list = []

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                name LIKE ?
                OR product_name LIKE ?
                OR supplier_name LIKE ?
                OR origin_country LIKE ?
                OR destination LIKE ?
            )
        """

        parameters.extend([search_value] * 5)

    if status != "All":
        query += " AND status = ?"
        parameters.append(status)

    query += " ORDER BY id DESC"

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [row_to_landed_cost(row) for row in rows]


def get_landed_cost_by_id(
    landed_cost_id: int,
) -> Optional[LandedCost]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM landed_costs
            WHERE id = ?
            """,
            (landed_cost_id,),
        ).fetchone()

    return row_to_landed_cost(row) if row else None


def delete_landed_cost(landed_cost_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM landed_costs
            WHERE id = ?
            """,
            (landed_cost_id,),
        )


def count_landed_costs() -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM landed_costs
            """
        ).fetchone()

    return int(row["total"])