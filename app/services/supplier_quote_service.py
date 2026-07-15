from datetime import datetime
from typing import Optional

from database.connection import get_connection
from models.supplier_quote import SupplierQuote


def row_to_supplier_quote(row) -> SupplierQuote:
    return SupplierQuote(
        id=row["id"],
        rfq_id=row["rfq_id"],
        supplier_id=row["supplier_id"],
        supplier_name=row["supplier_name"],
        quote_reference=row["quote_reference"],
        currency=row["currency"],
        unit_price=float(row["unit_price"]),
        quantity=float(row["quantity"]),
        freight_cost=float(row["freight_cost"]),
        insurance_cost=float(row["insurance_cost"]),
        other_costs=float(row["other_costs"]),
        incoterm=row["incoterm"],
        moq=row["moq"],
        lead_time_days=int(row["lead_time_days"]),
        payment_terms=row["payment_terms"],
        packaging=row["packaging"],
        certificates=row["certificates"],
        sample_available=bool(row["sample_available"]),
        sample_cost=float(row["sample_cost"]),
        quotation_valid_until=row["quotation_valid_until"],
        quality_score=int(row["quality_score"]),
        compliance_score=int(row["compliance_score"]),
        communication_score=int(row["communication_score"]),
        reliability_score=int(row["reliability_score"]),
        risk_score=int(row["risk_score"]),
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_supplier_quote(quote: SupplierQuote) -> int:
    timestamp = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO supplier_quotes (
                rfq_id,
                supplier_id,
                supplier_name,
                quote_reference,
                currency,
                unit_price,
                quantity,
                freight_cost,
                insurance_cost,
                other_costs,
                incoterm,
                moq,
                lead_time_days,
                payment_terms,
                packaging,
                certificates,
                sample_available,
                sample_cost,
                quotation_valid_until,
                quality_score,
                compliance_score,
                communication_score,
                reliability_score,
                risk_score,
                status,
                notes,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                quote.rfq_id,
                quote.supplier_id,
                quote.supplier_name.strip(),
                quote.quote_reference.strip()
                if quote.quote_reference
                else None,
                quote.currency,
                quote.unit_price,
                quote.quantity,
                quote.freight_cost,
                quote.insurance_cost,
                quote.other_costs,
                quote.incoterm,
                quote.moq.strip() if quote.moq else None,
                quote.lead_time_days,
                quote.payment_terms.strip()
                if quote.payment_terms
                else None,
                quote.packaging.strip()
                if quote.packaging
                else None,
                quote.certificates.strip()
                if quote.certificates
                else None,
                int(quote.sample_available),
                quote.sample_cost,
                quote.quotation_valid_until,
                quote.quality_score,
                quote.compliance_score,
                quote.communication_score,
                quote.reliability_score,
                quote.risk_score,
                quote.status,
                quote.notes.strip() if quote.notes else None,
                timestamp,
                timestamp,
            ),
        )

        return int(cursor.lastrowid)


def get_supplier_quotes(
    rfq_id: Optional[int] = None,
    search: str = "",
    status: str = "All",
) -> list[SupplierQuote]:
    query = """
        SELECT *
        FROM supplier_quotes
        WHERE 1 = 1
    """

    parameters: list = []

    if rfq_id is not None:
        query += " AND rfq_id = ?"
        parameters.append(rfq_id)

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                supplier_name LIKE ?
                OR quote_reference LIKE ?
                OR incoterm LIKE ?
                OR payment_terms LIKE ?
                OR notes LIKE ?
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

    return [row_to_supplier_quote(row) for row in rows]


def get_supplier_quote_by_id(
    quote_id: int,
) -> Optional[SupplierQuote]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM supplier_quotes
            WHERE id = ?
            """,
            (quote_id,),
        ).fetchone()

    return row_to_supplier_quote(row) if row else None


def delete_supplier_quote(quote_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM supplier_quotes
            WHERE id = ?
            """,
            (quote_id,),
        )


def count_supplier_quotes() -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM supplier_quotes
            """
        ).fetchone()

    return int(row["total"])