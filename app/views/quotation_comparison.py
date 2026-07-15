import streamlit as st

from services.rfq_service import get_rfqs
from services.supplier_quote_service import get_supplier_quotes


def calculate_quote_score(quote, lowest_total: float) -> int:
    if quote.quoted_total > 0:
        price_score = min(
            100,
            (lowest_total / quote.quoted_total) * 100,
        )
    else:
        price_score = 0

    lead_time_score = max(
        0,
        100 - min(quote.lead_time_days, 100),
    )

    score = (
        price_score * 0.30
        + quote.quality_score * 0.20
        + quote.compliance_score * 0.15
        + quote.reliability_score * 0.15
        + quote.communication_score * 0.10
        + lead_time_score * 0.10
        - quote.risk_score * 0.15
    )

    return max(0, min(100, round(score)))


def recommendation_label(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Strong"
    if score >= 55:
        return "Moderate"
    if score >= 40:
        return "Weak"

    return "High Risk"


def show() -> None:
    st.title("⚖️ Quotation Comparison")
    st.caption(
        "Compare supplier offers by price, lead time, quality, "
        "compliance, reliability, communication and risk."
    )

    rfqs = get_rfqs()

    if not rfqs:
        st.warning("Create an RFQ first.")
        return

    selected_rfq = st.selectbox(
        "Select RFQ",
        rfqs,
        format_func=lambda rfq: (
            f"{rfq.rfq_number} — {rfq.title}"
        ),
    )

    quotes = get_supplier_quotes(
        rfq_id=selected_rfq.id,
    )

    if not quotes:
        st.info(
            "No supplier quotations have been recorded for this RFQ."
        )
        return

    lowest_total = min(
        quote.quoted_total for quote in quotes
    )

    ranked_quotes = sorted(
        [
            {
                "quote": quote,
                "score": calculate_quote_score(
                    quote,
                    lowest_total,
                ),
            }
            for quote in quotes
        ],
        key=lambda item: item["score"],
        reverse=True,
    )

    best = ranked_quotes[0]

    st.subheader("Recommended Supplier")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Supplier",
        best["quote"].supplier_name,
    )

    col2.metric(
        "Decision Score",
        f"{best['score']}/100",
    )

    col3.metric(
        "Quoted Total",
        f"{best['quote'].currency} "
        f"{best['quote'].quoted_total:,.2f}",
    )

    col4.metric(
        "Lead Time",
        f"{best['quote'].lead_time_days} days",
    )

    st.success(
        f"{recommendation_label(best['score'])} offer. "
        "Review compliance evidence and full landed cost "
        "before awarding the order."
    )

    st.markdown("---")
    st.subheader("Side-by-Side Comparison")

    rows = []

    for rank, item in enumerate(
        ranked_quotes,
        start=1,
    ):
        quote = item["quote"]

        rows.append(
            {
                "Rank": rank,
                "Supplier": quote.supplier_name,
                "Currency": quote.currency,
                "Unit Price": quote.unit_price,
                "Goods Total": quote.goods_total,
                "Freight": quote.freight_cost,
                "Insurance": quote.insurance_cost,
                "Other Costs": quote.other_costs,
                "Quoted Total": quote.quoted_total,
                "Incoterm": quote.incoterm,
                "MOQ": quote.moq or "",
                "Lead Time": quote.lead_time_days,
                "Quality": quote.quality_score,
                "Compliance": quote.compliance_score,
                "Reliability": quote.reliability_score,
                "Communication": quote.communication_score,
                "Risk": quote.risk_score,
                "Score": item["score"],
                "Recommendation": recommendation_label(
                    item["score"]
                ),
            }
        )

    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
    )

    st.markdown("---")
    st.subheader("Decision Notes")

    st.warning(
        "Quoted totals may use different currencies or Incoterms. "
        "Do not treat them as directly comparable until exchange rates, "
        "duties, GST, port charges, biosecurity, customs brokerage, "
        "warehouse and local delivery are added through Landed Cost."
    )