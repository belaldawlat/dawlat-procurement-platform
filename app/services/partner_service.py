from typing import Optional

from database.connection import get_connection
from models.partner import Partner


def row_to_partner(row) -> Partner:
    return Partner(
        id=row["id"],
        company_name=row["company_name"],
        partner_type=row["partner_type"],
        country=row["country"],
        city=row["city"],
        contact_name=row["contact_name"],
        email=row["email"],
        phone=row["phone"],
        whatsapp=row["whatsapp"],
        website=row["website"],
        products_services=row["products_services"],
        status=row["status"],
        verification_status=row["verification_status"],
        rating=row["rating"],
        notes=row["notes"],
    )


def create_partner(partner: Partner) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO partners (
                company_name,
                partner_type,
                country,
                city,
                contact_name,
                email,
                phone,
                whatsapp,
                website,
                products_services,
                status,
                verification_status,
                rating,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                partner.company_name.strip(),
                partner.partner_type.strip(),
                partner.country.strip(),
                partner.city.strip() if partner.city else None,
                partner.contact_name.strip() if partner.contact_name else None,
                partner.email.strip() if partner.email else None,
                partner.phone.strip() if partner.phone else None,
                partner.whatsapp.strip() if partner.whatsapp else None,
                partner.website.strip() if partner.website else None,
                partner.products_services.strip()
                if partner.products_services
                else None,
                partner.status,
                partner.verification_status,
                partner.rating,
                partner.notes.strip() if partner.notes else None,
            ),
        )

        return int(cursor.lastrowid)


def get_partners(
    search: str = "",
    partner_type: str = "All",
    country: str = "All",
) -> list[Partner]:
    query = """
        SELECT *
        FROM partners
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
                OR products_services LIKE ?
                OR country LIKE ?
                OR city LIKE ?
            )
        """

        parameters.extend([search_value] * 6)

    if partner_type != "All":
        query += " AND partner_type = ?"
        parameters.append(partner_type)

    if country != "All":
        query += " AND country = ?"
        parameters.append(country)

    query += " ORDER BY company_name ASC"

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [row_to_partner(row) for row in rows]


def get_partner_by_id(partner_id: int) -> Optional[Partner]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM partners
            WHERE id = ?
            """,
            (partner_id,),
        ).fetchone()

    return row_to_partner(row) if row else None


def update_partner(partner: Partner) -> None:
    if partner.id is None:
        raise ValueError("Partner ID is required.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE partners
            SET company_name = ?,
                partner_type = ?,
                country = ?,
                city = ?,
                contact_name = ?,
                email = ?,
                phone = ?,
                whatsapp = ?,
                website = ?,
                products_services = ?,
                status = ?,
                verification_status = ?,
                rating = ?,
                notes = ?
            WHERE id = ?
            """,
            (
                partner.company_name.strip(),
                partner.partner_type.strip(),
                partner.country.strip(),
                partner.city.strip() if partner.city else None,
                partner.contact_name.strip() if partner.contact_name else None,
                partner.email.strip() if partner.email else None,
                partner.phone.strip() if partner.phone else None,
                partner.whatsapp.strip() if partner.whatsapp else None,
                partner.website.strip() if partner.website else None,
                partner.products_services.strip()
                if partner.products_services
                else None,
                partner.status,
                partner.verification_status,
                partner.rating,
                partner.notes.strip() if partner.notes else None,
                partner.id,
            ),
        )


def delete_partner(partner_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM partners
            WHERE id = ?
            """,
            (partner_id,),
        )


def count_partners() -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM partners
            """
        ).fetchone()

    return int(row["total"])


def get_partner_types() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT partner_type
            FROM partners
            ORDER BY partner_type ASC
            """
        ).fetchall()

    return [row["partner_type"] for row in rows]


def get_partner_countries() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT country
            FROM partners
            ORDER BY country ASC
            """
        ).fetchall()

    return [row["country"] for row in rows]