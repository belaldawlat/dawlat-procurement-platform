from datetime import datetime
from typing import Optional

from database.connection import get_connection
from models.logistics_quote import LogisticsQuote


def row_to_logistics_quote(row) -> LogisticsQuote:
    return LogisticsQuote(
        id=row["id"],
        provider_name=row["provider_name"],
        provider_type=row["provider_type"],
        rfq_id=row["rfq_id"],
        supplier_quote_id=row["supplier_quote_id"],
        origin_country=row["origin_country"],
        origin_city_port=row["origin_city_port"],
        destination_country=row["destination_country"],
        destination_city_port=row["destination_city_port"],
        transport_mode=row["transport_mode"],
        service_type=row["service_type"],
        container_type=row["container_type"],
        incoterm=row["incoterm"],
        cargo_description=row["cargo_description"],
        quantity=float(row["quantity"]),
        unit=row["unit"],
        gross_weight_kg=float(row["gross_weight_kg"]),
        volume_cbm=float(row["volume_cbm"]),
        currency=row["currency"],
        freight_cost=float(row["freight_cost"]),
        origin_charges=float(row["origin_charges"]),
        destination_charges=float(row["destination_charges"]),
        customs_clearance_fee=float(row["customs_clearance_fee"]),
        biosecurity_fee=float(row["biosecurity_fee"]),
        inspection_fee=float(row["inspection_fee"]),
        local_delivery_fee=float(row["local_delivery_fee"]),
        warehouse_fee=float(row["warehouse_fee"]),
        insurance_cost=float(row["insurance_cost"]),
        documentation_fee=float(row["documentation_fee"]),
        other_costs=float(row["other_costs"]),
        transit_days=int(row["transit_days"]),
        validity_date=row["validity_date"],
        departure_frequency=row["departure_frequency"],
        route_details=row["route_details"],
        inclusions=row["inclusions"],
        exclusions=row["exclusions"],
        reliability_score=int(row["reliability_score"]),
        communication_score=int(row["communication_score"]),
        price_score=int(row["price_score"]),
        service_score=int(row["service_score"]),
        risk_score=int(row["risk_score"]),
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_logistics_quote(quote: LogisticsQuote) -> int:
    timestamp = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO logistics_quotes (
                provider_name,
                provider_type,
                rfq_id,
                supplier_quote_id,
                origin_country,
                origin_city_port,
                destination_country,
                destination_city_port,
                transport_mode,
                service_type,
                container_type,
                incoterm,
                cargo_description,
                quantity,
                unit,
                gross_weight_kg,
                volume_cbm,
                currency,
                freight_cost,
                origin_charges,
                destination_charges,
                customs_clearance_fee,
                biosecurity_fee,
                inspection_fee,
                local_delivery_fee,
                warehouse_fee,
                insurance_cost,
                documentation_fee,
                other_costs,
                transit_days,
                validity_date,
                departure_frequency,
                route_details,
                inclusions,
                exclusions,
                reliability_score,
                communication_score,
                price_score,
                service_score,
                risk_score,
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
                quote.provider_name.strip(),
                quote.provider_type,
                quote.rfq_id,
                quote.supplier_quote_id,
                quote.origin_country.strip(),
                quote.origin_city_port.strip()
                if quote.origin_city_port
                else None,
                quote.destination_country.strip(),
                quote.destination_city_port.strip(),
                quote.transport_mode,
                quote.service_type,
                quote.container_type,
                quote.incoterm,
                quote.cargo_description.strip(),
                quote.quantity,
                quote.unit,
                quote.gross_weight_kg,
                quote.volume_cbm,
                quote.currency,
                quote.freight_cost,
                quote.origin_charges,
                quote.destination_charges,
                quote.customs_clearance_fee,
                quote.biosecurity_fee,
                quote.inspection_fee,
                quote.local_delivery_fee,
                quote.warehouse_fee,
                quote.insurance_cost,
                quote.documentation_fee,
                quote.other_costs,
                quote.transit_days,
                quote.validity_date,
                quote.departure_frequency,
                quote.route_details,
                quote.inclusions,
                quote.exclusions,
                quote.reliability_score,
                quote.communication_score,
                quote.price_score,
                quote.service_score,
                quote.risk_score,
                quote.status,
                quote.notes,
                timestamp,
                timestamp,
            ),
        )

        return int(cursor.lastrowid)


def get_logistics_quotes(
    search: str = "",
    provider_type: str = "All",
    transport_mode: str = "All",
    status: str = "All",
) -> list[LogisticsQuote]:
    query = """
        SELECT *
        FROM logistics_quotes
        WHERE 1 = 1
    """

    parameters: list = []

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                provider_name LIKE ?
                OR origin_country LIKE ?
                OR origin_city_port LIKE ?
                OR destination_country LIKE ?
                OR destination_city_port LIKE ?
                OR cargo_description LIKE ?
                OR route_details LIKE ?
            )
        """

        parameters.extend([search_value] * 7)

    if provider_type != "All":
        query += " AND provider_type = ?"
        parameters.append(provider_type)

    if transport_mode != "All":
        query += " AND transport_mode = ?"
        parameters.append(transport_mode)

    if status != "All":
        query += " AND status = ?"
        parameters.append(status)

    query += " ORDER BY id DESC"

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [row_to_logistics_quote(row) for row in rows]


def get_logistics_quote_by_id(
    quote_id: int,
) -> Optional[LogisticsQuote]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM logistics_quotes
            WHERE id = ?
            """,
            (quote_id,),
        ).fetchone()

    return row_to_logistics_quote(row) if row else None


def delete_logistics_quote(quote_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM logistics_quotes
            WHERE id = ?
            """,
            (quote_id,),
        )


def count_logistics_quotes() -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM logistics_quotes
            """
        ).fetchone()

    return int(row["total"])