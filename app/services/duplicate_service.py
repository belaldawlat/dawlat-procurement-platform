from dataclasses import dataclass
from typing import Optional

from database.connection import get_connection
from utils.validation import normalized_name_string


@dataclass
class DuplicateMatch:
    entity_type: str
    record_id: int
    display_name: str
    reason: str


ENTITY_CONFIG = {
    "product": {
        "table": "products",
        "name_column": "name",
        "secondary_columns": ["sku"],
    },
    "supplier": {
        "table": "partners",
        "name_column": "company_name",
        "secondary_columns": [
            "email",
            "phone",
            "website",
        ],
        "condition": "partner_type = 'Supplier'",
    },
    "partner": {
        "table": "partners",
        "name_column": "company_name",
        "secondary_columns": [
            "email",
            "phone",
            "website",
        ],
    },
    "customer": {
        "table": "customers",
        "name_column": "company_name",
        "secondary_columns": [
            "email",
            "phone",
            "website",
        ],
    },
    "opportunity": {
        "table": "market_opportunities",
        "name_column": "title",
        "secondary_columns": [
            "buyer_company",
            "product",
        ],
    },
}


def find_duplicates(
    entity_type: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    website: Optional[str] = None,
    sku: Optional[str] = None,
) -> list[DuplicateMatch]:
    config = ENTITY_CONFIG.get(entity_type)

    if config is None:
        raise ValueError(
            f"Unsupported entity type: {entity_type}"
        )

    table = config["table"]
    name_column = config["name_column"]
    secondary_columns = config.get(
        "secondary_columns",
        [],
    )

    query = f"""
        SELECT *
        FROM {table}
        WHERE 1 = 1
    """

    condition = config.get("condition")

    if condition:
        query += f" AND {condition}"

    with get_connection() as connection:
        rows = connection.execute(query).fetchall()

    matches: list[DuplicateMatch] = []

    submitted_name = normalized_name_string(name)
    submitted_values = {
        "email": (email or "").strip().lower(),
        "phone": (phone or "").strip(),
        "website": (website or "").strip().lower(),
        "sku": (sku or "").strip().upper(),
    }

    for row in rows:
        display_name = str(row[name_column])
        existing_name = normalized_name_string(display_name)

        reasons: list[str] = []

        if (
            submitted_name
            and existing_name
            and submitted_name == existing_name
        ):
            reasons.append("same or very similar name")

        for column in secondary_columns:
            submitted_value = submitted_values.get(
                column,
                "",
            )

            existing_value = row[column]

            if existing_value is None or not submitted_value:
                continue

            existing_text = str(existing_value).strip()

            if column in {"email", "website"}:
                existing_text = existing_text.lower()

            if column == "sku":
                existing_text = existing_text.upper()

            if existing_text == submitted_value:
                reasons.append(f"same {column}")

        if reasons:
            matches.append(
                DuplicateMatch(
                    entity_type=entity_type,
                    record_id=int(row["id"]),
                    display_name=display_name,
                    reason=", ".join(reasons),
                )
            )

    return matches