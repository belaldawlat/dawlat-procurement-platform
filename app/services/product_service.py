from typing import Optional

from database.connection import get_connection
from models.product import Product


def row_to_product(row) -> Product:
    return Product(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        sku=row["sku"],
        unit=row["unit"],
        country_of_origin=row["country_of_origin"],
        description=row["description"],
        specifications=row["specifications"],
        packaging=row["packaging"],
        required_certificates=row["required_certificates"],
        storage_requirements=row["storage_requirements"],
        status=row["status"],
    )


def create_product(product: Product) -> int:
    if get_product_by_sku(product.sku) is not None:
        raise ValueError("That SKU already exists.")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO products (
                name,
                category,
                sku,
                unit,
                country_of_origin,
                description,
                specifications,
                packaging,
                required_certificates,
                storage_requirements,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product.name.strip(),
                product.category.strip(),
                product.sku.strip().upper(),
                product.unit.strip(),
                product.country_of_origin.strip()
                if product.country_of_origin
                else None,
                product.description.strip()
                if product.description
                else None,
                product.specifications.strip()
                if product.specifications
                else None,
                product.packaging.strip()
                if product.packaging
                else None,
                product.required_certificates.strip()
                if product.required_certificates
                else None,
                product.storage_requirements.strip()
                if product.storage_requirements
                else None,
                product.status,
            ),
        )

        return int(cursor.lastrowid)


def get_products(
    search: str = "",
    category: str = "All",
    status: str = "All",
) -> list[Product]:
    query = """
        SELECT *
        FROM products
        WHERE 1 = 1
    """

    parameters: list = []

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                name LIKE ?
                OR sku LIKE ?
                OR category LIKE ?
                OR country_of_origin LIKE ?
                OR description LIKE ?
            )
        """

        parameters.extend([search_value] * 5)

    if category != "All":
        query += " AND category = ?"
        parameters.append(category)

    if status != "All":
        query += " AND status = ?"
        parameters.append(status)

    query += " ORDER BY name ASC"

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [row_to_product(row) for row in rows]


def get_product_by_id(product_id: int) -> Optional[Product]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()

    return row_to_product(row) if row else None


def get_product_by_sku(sku: str) -> Optional[Product]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM products
            WHERE UPPER(sku) = UPPER(?)
            """,
            (sku.strip(),),
        ).fetchone()

    return row_to_product(row) if row else None


def update_product(product: Product) -> None:
    if product.id is None:
        raise ValueError("Product ID is required.")

    existing_product = get_product_by_sku(product.sku)

    if (
        existing_product is not None
        and existing_product.id != product.id
    ):
        raise ValueError("That SKU already exists.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE products
            SET name = ?,
                category = ?,
                sku = ?,
                unit = ?,
                country_of_origin = ?,
                description = ?,
                specifications = ?,
                packaging = ?,
                required_certificates = ?,
                storage_requirements = ?,
                status = ?
            WHERE id = ?
            """,
            (
                product.name.strip(),
                product.category.strip(),
                product.sku.strip().upper(),
                product.unit.strip(),
                product.country_of_origin.strip()
                if product.country_of_origin
                else None,
                product.description.strip()
                if product.description
                else None,
                product.specifications.strip()
                if product.specifications
                else None,
                product.packaging.strip()
                if product.packaging
                else None,
                product.required_certificates.strip()
                if product.required_certificates
                else None,
                product.storage_requirements.strip()
                if product.storage_requirements
                else None,
                product.status,
                product.id,
            ),
        )


def delete_product(product_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM products
            WHERE id = ?
            """,
            (product_id,),
        )


def count_products() -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM products
            """
        ).fetchone()

    return int(row["total"])


def get_product_categories() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT category
            FROM products
            ORDER BY category ASC
            """
        ).fetchall()

    return [row["category"] for row in rows]