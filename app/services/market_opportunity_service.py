from typing import Optional

from database.connection import get_connection
from models.market_opportunity import MarketOpportunity


def row_to_opportunity(row) -> MarketOpportunity:
    return MarketOpportunity(
        id=row["id"],
        title=row["title"],
        product=row["product"],
        industry=row["industry"],
        country=row["country"],
        state=row["state"],
        city=row["city"],
        buyer_company=row["buyer_company"],
        opportunity_type=row["opportunity_type"],
        estimated_quantity=row["estimated_quantity"],
        target_price=row["target_price"],
        estimated_landed_cost=row["estimated_landed_cost"],
        estimated_sale_price=row["estimated_sale_price"],
        expected_margin=row["expected_margin"],
        urgency=row["urgency"],
        demand_score=row["demand_score"],
        competition_score=row["competition_score"],
        confidence_score=row["confidence_score"],
        status=row["status"],
        source=row["source"],
        notes=row["notes"],
    )


def create_opportunity(opportunity: MarketOpportunity) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO market_opportunities (
                title,
                product,
                industry,
                country,
                state,
                city,
                buyer_company,
                opportunity_type,
                estimated_quantity,
                target_price,
                estimated_landed_cost,
                estimated_sale_price,
                expected_margin,
                urgency,
                demand_score,
                competition_score,
                confidence_score,
                status,
                source,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity.title.strip(),
                opportunity.product.strip(),
                opportunity.industry.strip(),
                opportunity.country.strip(),
                opportunity.state.strip() if opportunity.state else None,
                opportunity.city.strip() if opportunity.city else None,
                opportunity.buyer_company.strip()
                if opportunity.buyer_company
                else None,
                opportunity.opportunity_type,
                opportunity.estimated_quantity.strip()
                if opportunity.estimated_quantity
                else None,
                opportunity.target_price.strip()
                if opportunity.target_price
                else None,
                opportunity.estimated_landed_cost.strip()
                if opportunity.estimated_landed_cost
                else None,
                opportunity.estimated_sale_price.strip()
                if opportunity.estimated_sale_price
                else None,
                opportunity.expected_margin.strip()
                if opportunity.expected_margin
                else None,
                opportunity.urgency,
                opportunity.demand_score,
                opportunity.competition_score,
                opportunity.confidence_score,
                opportunity.status,
                opportunity.source.strip()
                if opportunity.source
                else None,
                opportunity.notes.strip()
                if opportunity.notes
                else None,
            ),
        )

        return int(cursor.lastrowid)


def get_opportunities(
    search: str = "",
    country: str = "All",
    industry: str = "All",
    status: str = "All",
    urgency: str = "All",
    opportunity_type: str = "All",
) -> list[MarketOpportunity]:
    query = """
        SELECT *
        FROM market_opportunities
        WHERE 1 = 1
    """

    parameters: list = []

    if search.strip():
        search_value = f"%{search.strip()}%"

        query += """
            AND (
                title LIKE ?
                OR product LIKE ?
                OR industry LIKE ?
                OR buyer_company LIKE ?
                OR country LIKE ?
                OR city LIKE ?
                OR notes LIKE ?
            )
        """

        parameters.extend([search_value] * 7)

    if country != "All":
        query += " AND country = ?"
        parameters.append(country)

    if industry != "All":
        query += " AND industry = ?"
        parameters.append(industry)

    if status != "All":
        query += " AND status = ?"
        parameters.append(status)

    if urgency != "All":
        query += " AND urgency = ?"
        parameters.append(urgency)

    if opportunity_type != "All":
        query += " AND opportunity_type = ?"
        parameters.append(opportunity_type)

    query += " ORDER BY id DESC"

    with get_connection() as connection:
        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [row_to_opportunity(row) for row in rows]


def get_opportunity_by_id(
    opportunity_id: int,
) -> Optional[MarketOpportunity]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM market_opportunities
            WHERE id = ?
            """,
            (opportunity_id,),
        ).fetchone()

    return row_to_opportunity(row) if row else None


def update_opportunity(opportunity: MarketOpportunity) -> None:
    if opportunity.id is None:
        raise ValueError("Opportunity ID is required.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE market_opportunities
            SET title = ?,
                product = ?,
                industry = ?,
                country = ?,
                state = ?,
                city = ?,
                buyer_company = ?,
                opportunity_type = ?,
                estimated_quantity = ?,
                target_price = ?,
                estimated_landed_cost = ?,
                estimated_sale_price = ?,
                expected_margin = ?,
                urgency = ?,
                demand_score = ?,
                competition_score = ?,
                confidence_score = ?,
                status = ?,
                source = ?,
                notes = ?
            WHERE id = ?
            """,
            (
                opportunity.title.strip(),
                opportunity.product.strip(),
                opportunity.industry.strip(),
                opportunity.country.strip(),
                opportunity.state.strip() if opportunity.state else None,
                opportunity.city.strip() if opportunity.city else None,
                opportunity.buyer_company.strip()
                if opportunity.buyer_company
                else None,
                opportunity.opportunity_type,
                opportunity.estimated_quantity.strip()
                if opportunity.estimated_quantity
                else None,
                opportunity.target_price.strip()
                if opportunity.target_price
                else None,
                opportunity.estimated_landed_cost.strip()
                if opportunity.estimated_landed_cost
                else None,
                opportunity.estimated_sale_price.strip()
                if opportunity.estimated_sale_price
                else None,
                opportunity.expected_margin.strip()
                if opportunity.expected_margin
                else None,
                opportunity.urgency,
                opportunity.demand_score,
                opportunity.competition_score,
                opportunity.confidence_score,
                opportunity.status,
                opportunity.source.strip()
                if opportunity.source
                else None,
                opportunity.notes.strip()
                if opportunity.notes
                else None,
                opportunity.id,
            ),
        )


def delete_opportunity(opportunity_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM market_opportunities
            WHERE id = ?
            """,
            (opportunity_id,),
        )


def count_opportunities() -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM market_opportunities
            """
        ).fetchone()

    return int(row["total"])


def get_opportunity_countries() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT country
            FROM market_opportunities
            WHERE country IS NOT NULL
            ORDER BY country ASC
            """
        ).fetchall()

    return [row["country"] for row in rows]


def get_opportunity_industries() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT industry
            FROM market_opportunities
            WHERE industry IS NOT NULL
            ORDER BY industry ASC
            """
        ).fetchall()

    return [row["industry"] for row in rows]