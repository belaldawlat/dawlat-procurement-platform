from datetime import datetime
from typing import Optional

from database.connection import get_connection
from models.warehouse_quote import WarehouseQuote


def row_to_warehouse_quote(row) -> WarehouseQuote:
    return WarehouseQuote(
        id=row["id"],
        provider_name=row["provider_name"],
        provider_type=row["provider_type"],
        logistics_quote_id=row["logistics_quote_id"],
        rfq_id=row["rfq_id"],
        supplier_quote_id=row["supplier_quote_id"],
        country=row["country"],
        state_region=row["state_region"],
        city=row["city"],
        address=row["address"],
        warehouse_type=row["warehouse_type"],
        service_model=row["service_model"],
        temperature_controlled=bool(
            row["temperature_controlled"]
        ),
        bonded_warehouse=bool(row["bonded_warehouse"]),
        food_grade=bool(row["food_grade"]),
        product_description=row["product_description"],
        quantity=float(row["quantity"]),
        storage_unit=row["storage_unit"],
        estimated_storage_days=int(
            row["estimated_storage_days"]
        ),
        currency=row["currency"],
        receiving_fee=float(row["receiving_fee"]),
        container_unloading_fee=float(
            row["container_unloading_fee"]
        ),
        devanning_fee=float(row["devanning_fee"]),
        storage_rate=float(row["storage_rate"]),
        minimum_monthly_charge=float(
            row["minimum_monthly_charge"]
        ),
        pallet_in_fee=float(row["pallet_in_fee"]),
        pallet_out_fee=float(row["pallet_out_fee"]),
        pick_pack_fee=float(row["pick_pack_fee"]),
        labelling_fee=float(row["labelling_fee"]),
        repacking_fee=float(row["repacking_fee"]),
        cross_docking_fee=float(row["cross_docking_fee"]),
        inventory_management_fee=float(
            row["inventory_management_fee"]
        ),
        local_delivery_fee=float(row["local_delivery_fee"]),
        disposal_fee=float(row["disposal_fee"]),
        other_costs=float(row["other_costs"]),
        free_storage_days=int(row["free_storage_days"]),
        minimum_term_months=int(row["minimum_term_months"]),
        capacity_description=row["capacity_description"],
        delivery_zones=row["delivery_zones"],
        operating_hours=row["operating_hours"],
        systems_integrations=row["systems_integrations"],
        insurance_details=row["insurance_details"],
        certifications=row["certifications"],
        inclusions=row["inclusions"],
        exclusions=row["exclusions"],
        price_score=int(row["price_score"]),
        location_score=int(row["location_score"]),
        service_score=int(row["service_score"]),
        capacity_score=int(row["capacity_score"]),
        technology_score=int(row["technology_score"]),
        reliability_score=int(row["reliability_score"]),
        communication_score=int(row["communication_score"]),
        compliance_score=int(row["compliance_score"]),
        risk_score=int(row["risk_score"]),
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_warehouse_quote(
    quote: WarehouseQuote,
) -> int:
    timestamp = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO warehouse_quotes (
                provider_name,
                provider_type,
                logistics_quote_id,
                rfq_id,
                supplier_quote_id,
                country,
                state_region,
                city,
                address,
                warehouse_type,
                service_model,
                temperature_controlled,
                bonded_warehouse,
                food_grade,
                product_description,
                quantity,
                storage_unit,
                estimated_storage_days,
                currency,
                receiving_fee,
                container_unloading_fee,
                devanning_fee,
                storage_rate,
                minimum_monthly_charge,
                pallet_in_fee,
                pallet_out_fee,
                pick_pack_fee,
                labelling_fee,
                repacking_fee,
                cross_docking_fee,
                inventory_management_fee,
                local_delivery_fee,
                disposal_fee,
                other_costs,
                free_storage_days,
                minimum_term_months,
                capacity_description,
                delivery_zones,
                operating_hours,
                systems_integrations,
                insurance_details,
                certifications,
                inclusions,
                exclusions,
                price_score,
                location_score,
                service_score,
                capacity_score,
                technology_score,
                reliability_score,
                communication_score,
                compliance_score,
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                quote.provider_name.strip(),
                quote.provider_type,
                quote.logistics_quote_id,
                quote.rfq_id,
                quote.supplier_quote_id,
                quote.country.strip(),
                quote.state_region.strip()
                if quote.state_region
                else None,
                quote.city.strip(),
                quote.address.strip()
                if quote.address
                else None,
                quote.warehouse_type,
                quote.service_model,
                int(quote.temperature_controlled),
                int(quote.bonded_warehouse),
                int(quote.food_grade),
                quote.product_description.strip(),
                quote.quantity,
                quote.storage_unit,
                quote.estimated_storage_days,
                quote.currency,
                quote.receiving_fee,
                quote.container_unloading_fee,
                quote.devanning_fee,
                quote.storage_rate,
                quote.minimum_monthly_charge,
                quote.pallet_in_fee,
                quote.pallet_out_fee,
                quote.pick_pack_fee,
                quote.labelling_fee,
                quote.repacking_fee,
                quote.cross_docking_fee,
                quote.inventory_management_fee,
                quote.local_delivery_fee,
                quote.disposal_fee,
                quote.other_costs,
                quote.free_storage_days,
                quote.minimum_term_months,
                quote.capacity_description,
                quote.delivery_zones,
                quote.operating_hours,
                quote.systems_integrations,
                quote.insurance_details,
                quote.certifications,
                quote.inclusions,
                quote.exclusions,
                quote.price_score,
                quote.location_score,
                quote.service_score,
                quote.capacity_score,
                quote.technology_score,
                quote.reliability_score,
                quote.communication_score,
                quote.compliance_score,
                quote.risk_score,
                quote.status,
                quote.notes,
                timestamp,
                timestamp,
            ),
        )

        return int(cursor.lastrowid)


def get_warehouse_quotes(
    search: str = "",
    provider_type: str = "All",
    warehouse_type: str = "All",
    status: str = "All",
) -> list[WarehouseQuote]:
    query = """
        SELECT *
        FROM warehouse_quotes
        WHERE 1 = 1
    """

    parameters: list = []

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                provider_name LIKE ?
                OR country LIKE ?
                OR state_region LIKE ?
                OR city LIKE ?
                OR address LIKE ?
                OR product_description LIKE ?
                OR delivery_zones LIKE ?
            )
        """

        parameters.extend([search_value] * 7)

    if provider_type != "All":
        query += " AND provider_type = ?"
        parameters.append(provider_type)

    if warehouse_type != "All":
        query += " AND warehouse_type = ?"
        parameters.append(warehouse_type)

    if status != "All":
        query += " AND status = ?"
        parameters.append(status)

    query += " ORDER BY id DESC"

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [row_to_warehouse_quote(row) for row in rows]


def get_warehouse_quote_by_id(
    quote_id: int,
) -> Optional[WarehouseQuote]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM warehouse_quotes
            WHERE id = ?
            """,
            (quote_id,),
        ).fetchone()

    return row_to_warehouse_quote(row) if row else None


def delete_warehouse_quote(quote_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM warehouse_quotes
            WHERE id = ?
            """,
            (quote_id,),
        )


def count_warehouse_quotes() -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM warehouse_quotes
            """
        ).fetchone()

    return int(row["total"])