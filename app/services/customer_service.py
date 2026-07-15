from typing import Optional

from database.connection import get_connection
from models.customer import Customer


def row_to_customer(row) -> Customer:
    return Customer(
        id=row["id"],
        company_name=row["company_name"],
        customer_type=row["customer_type"],
        country=row["country"],
        city=row["city"],
        contact_name=row["contact_name"],
        email=row["email"],
        phone=row["phone"],
        whatsapp=row["whatsapp"],
        website=row["website"],
        products_of_interest=row["products_of_interest"],
        estimated_demand=row["estimated_demand"],
        preferred_packaging=row["preferred_packaging"],
        payment_terms=row["payment_terms"],
        credit_status=row["credit_status"],
        lead_status=row["lead_status"],
        source=row["source"],
        notes=row["notes"],
    )


def create_customer(customer: Customer) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO customers (
                company_name,
                customer_type,
                country,
                city,
                contact_name,
                email,
                phone,
                whatsapp,
                website,
                products_of_interest,
                estimated_demand,
                preferred_packaging,
                payment_terms,
                credit_status,
                lead_status,
                source,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer.company_name.strip(),
                customer.customer_type.strip(),
                customer.country.strip(),
                customer.city.strip() if customer.city else None,
                customer.contact_name.strip() if customer.contact_name else None,
                customer.email.strip() if customer.email else None,
                customer.phone.strip() if customer.phone else None,
                customer.whatsapp.strip() if customer.whatsapp else None,
                customer.website.strip() if customer.website else None,
                customer.products_of_interest.strip()
                if customer.products_of_interest
                else None,
                customer.estimated_demand.strip()
                if customer.estimated_demand
                else None,
                customer.preferred_packaging.strip()
                if customer.preferred_packaging
                else None,
                customer.payment_terms.strip()
                if customer.payment_terms
                else None,
                customer.credit_status,
                customer.lead_status,
                customer.source.strip() if customer.source else None,
                customer.notes.strip() if customer.notes else None,
            ),
        )

        return int(cursor.lastrowid)


def get_customers(
    search: str = "",
    customer_type: str = "All",
    lead_status: str = "All",
) -> list[Customer]:
    query = """
        SELECT *
        FROM customers
        WHERE 1 = 1
    """

    parameters: list = []

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                company_name LIKE ?
                OR contact_name LIKE ?
                OR email LIKE ?
                OR country LIKE ?
                OR city LIKE ?
                OR products_of_interest LIKE ?
            )
        """

        parameters.extend([search_value] * 6)

    if customer_type != "All":
        query += " AND customer_type = ?"
        parameters.append(customer_type)

    if lead_status != "All":
        query += " AND lead_status = ?"
        parameters.append(lead_status)

    query += " ORDER BY company_name ASC"

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [row_to_customer(row) for row in rows]


def get_customer_by_id(customer_id: int) -> Optional[Customer]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM customers
            WHERE id = ?
            """,
            (customer_id,),
        ).fetchone()

    return row_to_customer(row) if row else None


def update_customer(customer: Customer) -> None:
    if customer.id is None:
        raise ValueError("Customer ID is required.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE customers
            SET company_name = ?,
                customer_type = ?,
                country = ?,
                city = ?,
                contact_name = ?,
                email = ?,
                phone = ?,
                whatsapp = ?,
                website = ?,
                products_of_interest = ?,
                estimated_demand = ?,
                preferred_packaging = ?,
                payment_terms = ?,
                credit_status = ?,
                lead_status = ?,
                source = ?,
                notes = ?
            WHERE id = ?
            """,
            (
                customer.company_name.strip(),
                customer.customer_type.strip(),
                customer.country.strip(),
                customer.city.strip() if customer.city else None,
                customer.contact_name.strip() if customer.contact_name else None,
                customer.email.strip() if customer.email else None,
                customer.phone.strip() if customer.phone else None,
                customer.whatsapp.strip() if customer.whatsapp else None,
                customer.website.strip() if customer.website else None,
                customer.products_of_interest.strip()
                if customer.products_of_interest
                else None,
                customer.estimated_demand.strip()
                if customer.estimated_demand
                else None,
                customer.preferred_packaging.strip()
                if customer.preferred_packaging
                else None,
                customer.payment_terms.strip()
                if customer.payment_terms
                else None,
                customer.credit_status,
                customer.lead_status,
                customer.source.strip() if customer.source else None,
                customer.notes.strip() if customer.notes else None,
                customer.id,
            ),
        )


def delete_customer(customer_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM customers
            WHERE id = ?
            """,
            (customer_id,),
        )


def count_customers() -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM customers
            """
        ).fetchone()

    return int(row["total"])