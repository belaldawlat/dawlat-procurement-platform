from typing import Optional

from database.connection import get_connection
from models.supplier import Supplier


def create_supplier(supplier: Supplier) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO suppliers (
                company_name,
                category,
                country,
                contact_name,
                email,
                phone,
                website,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                supplier.company_name.strip(),
                supplier.category.strip(),
                supplier.country.strip(),
                supplier.contact_name.strip() if supplier.contact_name else None,
                supplier.email.strip() if supplier.email else None,
                supplier.phone.strip() if supplier.phone else None,
                supplier.website.strip() if supplier.website else None,
                supplier.notes.strip() if supplier.notes else None,
            ),
        )

        return int(cursor.lastrowid)


def get_suppliers(search: str = "") -> list[Supplier]:
    query = """
        SELECT
            id,
            company_name,
            category,
            country,
            contact_name,
            email,
            phone,
            website,
            notes
        FROM suppliers
    """

    parameters: tuple = ()

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            WHERE company_name LIKE ?
               OR category LIKE ?
               OR country LIKE ?
               OR contact_name LIKE ?
               OR email LIKE ?
        """

        parameters = (
            search_value,
            search_value,
            search_value,
            search_value,
            search_value,
        )

    query += " ORDER BY company_name ASC"

    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [
        Supplier(
            id=row["id"],
            company_name=row["company_name"],
            category=row["category"],
            country=row["country"],
            contact_name=row["contact_name"],
            email=row["email"],
            phone=row["phone"],
            website=row["website"],
            notes=row["notes"],
        )
        for row in rows
    ]


def get_supplier(supplier_id: int) -> Optional[Supplier]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM suppliers
            WHERE id = ?
            """,
            (supplier_id,),
        ).fetchone()

    if row is None:
        return None

    return Supplier(
        id=row["id"],
        company_name=row["company_name"],
        category=row["category"],
        country=row["country"],
        contact_name=row["contact_name"],
        email=row["email"],
        phone=row["phone"],
        website=row["website"],
        notes=row["notes"],
    )


def update_supplier(supplier: Supplier) -> None:
    if supplier.id is None:
        raise ValueError("Supplier ID is required.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE suppliers
            SET company_name = ?,
                category = ?,
                country = ?,
                contact_name = ?,
                email = ?,
                phone = ?,
                website = ?,
                notes = ?
            WHERE id = ?
            """,
            (
                supplier.company_name.strip(),
                supplier.category.strip(),
                supplier.country.strip(),
                supplier.contact_name.strip() if supplier.contact_name else None,
                supplier.email.strip() if supplier.email else None,
                supplier.phone.strip() if supplier.phone else None,
                supplier.website.strip() if supplier.website else None,
                supplier.notes.strip() if supplier.notes else None,
                supplier.id,
            ),
        )


def delete_supplier(supplier_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM suppliers WHERE id = ?",
            (supplier_id,),
        )


def count_suppliers() -> int:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM suppliers"
        ).fetchone()

    return int(row["total"])
