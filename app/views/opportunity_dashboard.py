from collections import Counter
from typing import Optional

import pandas as pd
import streamlit as st

from models.market_opportunity import MarketOpportunity
from services.market_opportunity_service import get_opportunities


HIGH_PRIORITY_SCORE = 70


def calculate_opportunity_score(
    opportunity: MarketOpportunity,
) -> int:
    urgency_bonus = {
        "Low": 0,
        "Medium": 5,
        "High": 10,
        "Critical": 15,
    }.get(opportunity.urgency, 0)

    score = (
        opportunity.demand_score * 0.40
        + opportunity.confidence_score * 0.35
        + (100 - opportunity.competition_score) * 0.25
        + urgency_bonus
    )

    return max(0, min(100, round(score)))


def get_priority_label(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Strong"
    if score >= 55:
        return "Moderate"
    if score >= 40:
        return "Weak"

    return "Low Priority"


def get_next_action(
    opportunity: MarketOpportunity,
    score: int,
) -> str:
    status = opportunity.status

    if status == "Research":
        return "Verify buyer demand and collect written specifications."

    if status == "Verifying Demand":
        return "Confirm quantity, budget, delivery date, and payment terms."

    if status == "Contacting Buyer":
        return "Follow up with the buyer and qualify the opportunity."

    if status == "Finding Local Supplier":
        return "Compare suitable Australian suppliers and delivery times."

    if status == "Finding International Supplier":
        return "Search verified international suppliers and request quotations."

    if status == "Quotation Requested":
        return "Track supplier responses and quotation deadlines."

    if status == "Costing":
        return "Complete landed-cost and margin calculations."

    if status == "Negotiating":
        return "Negotiate price, payment terms, MOQ, and delivery."

    if status == "Awaiting Buyer":
        return "Follow up with the buyer and confirm the buying decision."

    if status == "Won":
        return "Create the sales order and begin fulfilment."

    if status == "Completed":
        return "Review performance and identify repeat-sales potential."

    if status in {"Lost", "On Hold"}:
        return "Record the reason and schedule a future review."

    if score >= 70:
        return "Prioritise buyer verification and begin supplier matching."

    return "Continue research before committing time or capital."


def parse_numeric_value(value: Optional[str]) -> Optional[float]:
    if not value:
        return None

    cleaned = "".join(
        character
        for character in value
        if character.isdigit() or character in ".,-"
    )

    cleaned = cleaned.replace(",", "")

    try:
        return float(cleaned)
    except ValueError:
        return None


def show() -> None:
    st.title("📊 Opportunity Intelligence Dashboard")
    st.caption(
        "Monitor market demand, supply gaps, buyer opportunities, "
        "commercial potential, pipeline progress, and recommended actions."
    )

    opportunities = get_opportunities()

    if not opportunities:
        st.info(
            "No market opportunities are available yet. "
            "Create an opportunity inside Market Intelligence first."
        )
        return

    enriched_opportunities = [
        {
            "record": opportunity,
            "score": calculate_opportunity_score(opportunity),
        }
        for opportunity in opportunities
    ]

    total_opportunities = len(enriched_opportunities)

    high_priority_count = sum(
        1
        for item in enriched_opportunities
        if item["score"] >= HIGH_PRIORITY_SCORE
    )

    active_count = sum(
        1
        for item in enriched_opportunities
        if item["record"].status
        not in {"Won", "Lost", "Completed"}
    )

    won_count = sum(
        1
        for item in enriched_opportunities
        if item["record"].status == "Won"
    )

    average_score = round(
        sum(item["score"] for item in enriched_opportunities)
        / total_opportunities
    )

    st.subheader("Executive Summary")

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Total Opportunities", total_opportunities)
    col2.metric("High Priority", high_priority_count)
    col3.metric("Active Pipeline", active_count)
    col4.metric("Won", won_count)
    col5.metric("Average Score", f"{average_score}/100")

    st.markdown("---")

    ranked_opportunities = sorted(
        enriched_opportunities,
        key=lambda item: item["score"],
        reverse=True,
    )

    top_opportunity = ranked_opportunities[0]
    top_record = top_opportunity["record"]
    top_score = top_opportunity["score"]

    st.subheader("🏆 Highest-Priority Opportunity")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Opportunity Score", f"{top_score}/100")
    col2.metric("Demand", f"{top_record.demand_score}/100")
    col3.metric("Confidence", f"{top_record.confidence_score}/100")
    col4.metric(
        "Competition",
        f"{top_record.competition_score}/100",
    )

    st.markdown(f"### {top_record.title}")
    st.write(f"**Product or service:** {top_record.product}")
    st.write(f"**Buyer:** {top_record.buyer_company or 'Not confirmed'}")
    st.write(f"**Country:** {top_record.country}")
    st.write(f"**Industry:** {top_record.industry}")
    st.write(f"**Priority:** {get_priority_label(top_score)}")
    st.write(
        f"**Recommended next action:** "
        f"{get_next_action(top_record, top_score)}"
    )

    st.markdown("---")
    st.subheader("Opportunity Ranking")

    ranking_data = [
        {
            "Rank": index,
            "Opportunity": item["record"].title,
            "Product": item["record"].product,
            "Buyer": item["record"].buyer_company or "",
            "Country": item["record"].country,
            "Industry": item["record"].industry,
            "Score": item["score"],
            "Priority": get_priority_label(item["score"]),
            "Urgency": item["record"].urgency,
            "Status": item["record"].status,
            "Next Action": get_next_action(
                item["record"],
                item["score"],
            ),
        }
        for index, item in enumerate(
            ranked_opportunities,
            start=1,
        )
    ]

    st.dataframe(
        ranking_data,
        hide_index=True,
        width="stretch",
    )

    st.markdown("---")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Pipeline by Status")

        status_counts = Counter(
            opportunity.status for opportunity in opportunities
        )

        status_dataframe = pd.DataFrame(
            {
                "Status": list(status_counts.keys()),
                "Opportunities": list(status_counts.values()),
            }
        ).set_index("Status")

        st.bar_chart(status_dataframe)

    with chart_col2:
        st.subheader("Opportunities by Country")

        country_counts = Counter(
            opportunity.country for opportunity in opportunities
        )

        country_dataframe = pd.DataFrame(
            {
                "Country": list(country_counts.keys()),
                "Opportunities": list(country_counts.values()),
            }
        ).set_index("Country")

        st.bar_chart(country_dataframe)

    st.markdown("---")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Opportunities by Product")

        product_counts = Counter(
            opportunity.product for opportunity in opportunities
        )

        product_dataframe = pd.DataFrame(
            {
                "Product": list(product_counts.keys()),
                "Opportunities": list(product_counts.values()),
            }
        ).set_index("Product")

        st.bar_chart(product_dataframe)

    with chart_col2:
        st.subheader("Opportunities by Industry")

        industry_counts = Counter(
            opportunity.industry for opportunity in opportunities
        )

        industry_dataframe = pd.DataFrame(
            {
                "Industry": list(industry_counts.keys()),
                "Opportunities": list(industry_counts.values()),
            }
        ).set_index("Industry")

        st.bar_chart(industry_dataframe)

    st.markdown("---")
    st.subheader("Commercial Estimates")

    commercial_rows = []

    for item in ranked_opportunities:
        opportunity = item["record"]

        landed_cost = parse_numeric_value(
            opportunity.estimated_landed_cost
        )
        sale_price = parse_numeric_value(
            opportunity.estimated_sale_price
        )

        estimated_unit_profit = None

        if landed_cost is not None and sale_price is not None:
            estimated_unit_profit = sale_price - landed_cost

        commercial_rows.append(
            {
                "Opportunity": opportunity.title,
                "Product": opportunity.product,
                "Quantity": opportunity.estimated_quantity or "",
                "Target Price": opportunity.target_price or "",
                "Landed Cost": opportunity.estimated_landed_cost or "",
                "Sale Price": opportunity.estimated_sale_price or "",
                "Expected Margin": opportunity.expected_margin or "",
                "Estimated Unit Profit": (
                    round(estimated_unit_profit, 2)
                    if estimated_unit_profit is not None
                    else ""
                ),
            }
        )

    st.dataframe(
        commercial_rows,
        hide_index=True,
        width="stretch",
    )

    st.markdown("---")
    st.subheader("Recommended Actions")

    action_rows = [
        {
            "Priority": get_priority_label(item["score"]),
            "Score": item["score"],
            "Opportunity": item["record"].title,
            "Buyer": item["record"].buyer_company or "Not confirmed",
            "Status": item["record"].status,
            "Recommended Action": get_next_action(
                item["record"],
                item["score"],
            ),
        }
        for item in ranked_opportunities
    ]

    st.dataframe(
        action_rows,
        hide_index=True,
        width="stretch",
    )