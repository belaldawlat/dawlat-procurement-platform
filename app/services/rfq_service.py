from datetime import datetime
from typing import Optional

from database.connection import get_connection
from models.rfq import RFQ


def row_to_rfq(row) -> RFQ:
    return RFQ(
        id=row["id"],
        rfq_number=row["rfq_number"],
        title=row["title"],
        product_id=row["product_id"],
        product_name=row["product_name"],
        opportunity_id=row["opportunity_id"],
        supplier_id=row["supplier_id"],
        supplier_name=row["supplier_name"],
        quantity=row["quantity"],
        unit=row["unit"],
        specifications=row["specifications"],
        packaging_requirements=row["packaging_requirements"],
        certificate_requirements=row["certificate_requirements"],
        destination=row["destination"],
        preferred_incoterm=row["preferred_incoterm"],
        sample_requirements=row["sample_requirements"],
        payment_requirements=row["payment_requirements"],
        required_documents=row["required_documents"],
        response_deadline=row["response_deadline"],
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def generate_rfq_number() -> str:
    current_year = datetime.now().year

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM rfqs
            WHERE rfq_number LIKE ?
            """,
            (f"RFQ-{current_year}-%",),
        ).fetchone()

    sequence = int(row["total"]) + 1

    return f"RFQ-{current_year}-{sequence:04d}"


def create_rfq(rfq: RFQ) -> int:
    timestamp = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO rfqs (
                rfq_number,
                title,
                product_id,
                product_name,
                opportunity_id,
                supplier_id,
                supplier_name,
                quantity,
                unit,
                specifications,
                packaging_requirements,
                certificate_requirements,
                destination,
                preferred_incoterm,
                sample_requirements,
                payment_requirements,
                required_documents,
                response_deadline,
                status,
                notes,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                rfq.rfq_number,
                rfq.title.strip(),
                rfq.product_id,
                rfq.product_name.strip(),
                rfq.opportunity_id,
                rfq.supplier_id,
                rfq.supplier_name.strip()
                if rfq.supplier_name
                else None,
                rfq.quantity.strip(),
                rfq.unit.strip(),
                rfq.specifications.strip()
                if rfq.specifications
                else None,
                rfq.packaging_requirements.strip()
                if rfq.packaging_requirements
                else None,
                rfq.certificate_requirements.strip()
                if rfq.certificate_requirements
                else None,
                rfq.destination.strip()
                if rfq.destination
                else None,
                rfq.preferred_incoterm,
                rfq.sample_requirements.strip()
                if rfq.sample_requirements
                else None,
                rfq.payment_requirements.strip()
                if rfq.payment_requirements
                else None,
                rfq.required_documents.strip()
                if rfq.required_documents
                else None,
                rfq.response_deadline,
                rfq.status,
                rfq.notes.strip() if rfq.notes else None,
                timestamp,
                timestamp,
            ),
        )

        return int(cursor.lastrowid)


def get_rfqs(
    search: str = "",
    status: str = "All",
    supplier_name: str = "All",
) -> list[RFQ]:
    query = """
        SELECT *
        FROM rfqs
        WHERE 1 = 1
    """

    parameters: list = []

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                rfq_number LIKE ?
                OR title LIKE ?
                OR product_name LIKE ?
                OR supplier_name LIKE ?
                OR destination LIKE ?
                OR specifications LIKE ?
            )
        """

        parameters.extend([search_value] * 6)

    if status != "All":
        query += " AND status = ?"
        parameters.append(status)

    if supplier_name != "All":
        query += " AND supplier_name = ?"
        parameters.append(supplier_name)

    query += """
        ORDER BY
            CASE status
                WHEN 'Draft' THEN 1
                WHEN 'Ready' THEN 2
                WHEN 'Sent' THEN 3
                WHEN 'Partially Responded' THEN 4
                WHEN 'Fully Responded' THEN 5
                WHEN 'Under Review' THEN 6
                WHEN 'Awarded' THEN 7
                WHEN 'Closed' THEN 8
                WHEN 'Cancelled' THEN 9
                ELSE 10
            END,
            id DESC
    """

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [row_to_rfq(row) for row in rows]


def get_rfq_by_id(rfq_id: int) -> Optional[RFQ]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM rfqs
            WHERE id = ?
            """,
            (rfq_id,),
        ).fetchone()

    return row_to_rfq(row) if row else None


def update_rfq(rfq: RFQ) -> None:
    if rfq.id is None:
        raise ValueError("RFQ ID is required.")

    timestamp = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE rfqs
            SET title = ?,
                product_id = ?,
                product_name = ?,
                opportunity_id = ?,
                supplier_id = ?,
                supplier_name = ?,
                quantity = ?,
                unit = ?,
                specifications = ?,
                packaging_requirements = ?,
                certificate_requirements = ?,
                destination = ?,
                preferred_incoterm = ?,
                sample_requirements = ?,
                payment_requirements = ?,
                required_documents = ?,
                response_deadline = ?,
                status = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                rfq.title.strip(),
                rfq.product_id,
                rfq.product_name.strip(),
                rfq.opportunity_id,
                rfq.supplier_id,
                rfq.supplier_name.strip()
                if rfq.supplier_name
                else None,
                rfq.quantity.strip(),
                rfq.unit.strip(),
                rfq.specifications.strip()
                if rfq.specifications
                else None,
                rfq.packaging_requirements.strip()
                if rfq.packaging_requirements
                else None,
                rfq.certificate_requirements.strip()
                if rfq.certificate_requirements
                else None,
                rfq.destination.strip()
                if rfq.destination
                else None,
                rfq.preferred_incoterm,
                rfq.sample_requirements.strip()
                if rfq.sample_requirements
                else None,
                rfq.payment_requirements.strip()
                if rfq.payment_requirements
                else None,
                rfq.required_documents.strip()
                if rfq.required_documents
                else None,
                rfq.response_deadline,
                rfq.status,
                rfq.notes.strip() if rfq.notes else None,
                timestamp,
                rfq.id,
            ),
        )


def delete_rfq(rfq_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM rfqs
            WHERE id = ?
            """,
            (rfq_id,),
        )


def count_rfqs() -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM rfqs
            """
        ).fetchone()

    return int(row["total"])


def get_rfq_supplier_names() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT supplier_name
            FROM rfqs
            WHERE supplier_name IS NOT NULL
              AND supplier_name != ''
            ORDER BY supplier_name ASC
            """
        ).fetchall()

    return [row["supplier_name"] for row in rows]