import streamlit as st

from models.market_opportunity import MarketOpportunity
from services.market_opportunity_service import (
    create_opportunity,
    delete_opportunity,
    get_opportunities,
    get_opportunity_countries,
    get_opportunity_industries,
    update_opportunity,
)


OPPORTUNITY_TYPES = [
    "Local Supply",
    "Import Coordination",
    "Back-to-Back Order",
    "Brokerage",
    "Commission",
    "Distribution",
    "Tender",
    "Urgent Demand",
    "Government",
    "Manufacturing",
    "Wholesale",
    "Retail",
    "Export",
]

URGENCY_LEVELS = [
    "Low",
    "Medium",
    "High",
    "Critical",
]

STATUSES = [
    "Research",
    "Verifying Demand",
    "Contacting Buyer",
    "Finding Local Supplier",
    "Finding International Supplier",
    "Quotation Requested",
    "Costing",
    "Negotiating",
    "Awaiting Buyer",
    "Won",
    "Lost",
    "On Hold",
    "Completed",
]


def calculate_opportunity_score(
    demand_score: int,
    competition_score: int,
    confidence_score: int,
    urgency: str,
) -> int:
    urgency_bonus = {
        "Low": 0,
        "Medium": 5,
        "High": 10,
        "Critical": 15,
    }.get(urgency, 0)

    # A higher competition score means more competition,
    # so it reduces the opportunity score.
    score = (
        demand_score * 0.40
        + confidence_score * 0.35
        + (100 - competition_score) * 0.25
        + urgency_bonus
    )

    return max(0, min(100, round(score)))


def get_recommendation(score: int) -> str:
    if score >= 85:
        return "★★★★★ Excellent opportunity"
    if score >= 70:
        return "★★★★ Strong opportunity"
    if score >= 55:
        return "★★★ Moderate opportunity"
    if score >= 40:
        return "★★ Weak opportunity"

    return "★ Low-priority opportunity"


def show() -> None:
    st.title("🧠 Market Intelligence")
    st.caption(
        "Identify Australian market demand, buyer needs, supply gaps, "
        "local sourcing options, international sourcing opportunities, "
        "and potential commercial transactions."
    )

    add_tab, pipeline_tab = st.tabs(
        [
            "➕ Add Opportunity",
            "📈 Opportunity Pipeline",
        ]
    )

    with add_tab:
        show_add_opportunity()

    with pipeline_tab:
        show_opportunity_pipeline()


def show_add_opportunity() -> None:
    st.subheader("Record Market Demand or Supply Gap")

    with st.form(
        "add_market_opportunity_form",
        clear_on_submit=True,
    ):
        title = st.text_input(
            "Opportunity title *",
            placeholder="Example: Melbourne wholesaler seeking ST25 rice",
        )

        product = st.text_input(
            "Product or service *",
            placeholder="Example: ST25 premium rice",
        )

        industry = st.text_input(
            "Industry *",
            placeholder="Example: Food wholesale",
        )

        country = st.text_input(
            "Country *",
            value="Australia",
        )

        col1, col2 = st.columns(2)

        with col1:
            state = st.text_input(
                "State or region",
                placeholder="Example: Victoria",
            )

        with col2:
            city = st.text_input(
                "City",
                placeholder="Example: Melbourne",
            )

        buyer_company = st.text_input(
            "Buyer or company",
            placeholder="Company requesting or likely to need the product",
        )

        opportunity_type = st.selectbox(
            "Opportunity type",
            OPPORTUNITY_TYPES,
        )

        estimated_quantity = st.text_input(
            "Estimated quantity or demand",
            placeholder="Example: 20 tonnes per month",
        )

        specifications = st.text_area(
            "Buyer requirements and specifications",
            placeholder=(
                "Quality, grade, packaging, certificates, delivery location, "
                "delivery deadline, frequency, current supplier problems, "
                "and any other confirmed requirements."
            ),
            height=160,
        )

        st.markdown("#### Commercial Estimate")

        col1, col2 = st.columns(2)

        with col1:
            target_price = st.text_input(
                "Buyer target price",
                placeholder="Example: AUD 2,100 per tonne",
            )

            estimated_landed_cost = st.text_input(
                "Estimated landed cost",
                placeholder="Example: AUD 1,650 per tonne",
            )

        with col2:
            estimated_sale_price = st.text_input(
                "Estimated sale price",
                placeholder="Example: AUD 2,050 per tonne",
            )

            expected_margin = st.text_input(
                "Expected margin",
                placeholder="Example: AUD 400 per tonne or 19.5%",
            )

        urgency = st.selectbox(
            "Urgency",
            URGENCY_LEVELS,
            index=1,
        )

        st.markdown("#### Intelligence Scores")

        demand_score = st.slider(
            "Demand confidence",
            min_value=0,
            max_value=100,
            value=50,
            help="How strong and well-supported is the buyer demand?",
        )

        competition_score = st.slider(
            "Competition level",
            min_value=0,
            max_value=100,
            value=50,
            help="Higher values mean stronger competition.",
        )

        confidence_score = st.slider(
            "Information confidence",
            min_value=0,
            max_value=100,
            value=50,
            help="How reliable and recently verified is the evidence?",
        )

        status = st.selectbox(
            "Pipeline status",
            STATUSES,
        )

        source = st.text_input(
            "Evidence or source",
            placeholder=(
                "Buyer conversation, company website, tender, directory, "
                "Google Maps, sales enquiry, referral, or market research"
            ),
        )

        notes = st.text_area(
            "Internal analysis and next actions",
            placeholder=(
                "Local suppliers checked, international sourcing options, "
                "working-capital needs, compliance issues, payment risk, "
                "competitors, follow-up date, and recommended next action."
            ),
            height=180,
        )

        submitted = st.form_submit_button(
            "Save Market Opportunity",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if (
        not title.strip()
        or not product.strip()
        or not industry.strip()
        or not country.strip()
    ):
        st.warning(
            "Title, product or service, industry, and country are required."
        )
        return

    combined_notes = (
        f"Buyer requirements:\n{specifications.strip() or 'Not provided'}"
        f"\n\nInternal analysis:\n{notes.strip() or 'Not provided'}"
    )

    opportunity_id = create_opportunity(
        MarketOpportunity(
            title=title,
            product=product,
            industry=industry,
            country=country,
            state=state,
            city=city,
            buyer_company=buyer_company,
            opportunity_type=opportunity_type,
            estimated_quantity=estimated_quantity,
            target_price=target_price,
            estimated_landed_cost=estimated_landed_cost,
            estimated_sale_price=estimated_sale_price,
            expected_margin=expected_margin,
            urgency=urgency,
            demand_score=demand_score,
            competition_score=competition_score,
            confidence_score=confidence_score,
            status=status,
            source=source,
            notes=combined_notes,
        )
    )

    score = calculate_opportunity_score(
        demand_score=demand_score,
        competition_score=competition_score,
        confidence_score=confidence_score,
        urgency=urgency,
    )

    st.success(
        f"Market opportunity saved successfully. ID: {opportunity_id}"
    )
    st.info(
        f"Opportunity score: {score}/100 — {get_recommendation(score)}"
    )


def show_opportunity_pipeline() -> None:
    st.subheader("Market Opportunity Pipeline")

    search = st.text_input(
        "Search opportunities",
        placeholder=(
            "Search by opportunity, product, buyer, industry, "
            "country, city, or notes"
        ),
    )

    countries = ["All"] + get_opportunity_countries()
    industries = ["All"] + get_opportunity_industries()

    col1, col2, col3 = st.columns(3)

    with col1:
        country = st.selectbox(
            "Country",
            countries,
        )

        urgency = st.selectbox(
            "Urgency",
            ["All"] + URGENCY_LEVELS,
        )

    with col2:
        industry = st.selectbox(
            "Industry",
            industries,
        )

        opportunity_type = st.selectbox(
            "Opportunity type",
            ["All"] + OPPORTUNITY_TYPES,
        )

    with col3:
        status = st.selectbox(
            "Status",
            ["All"] + STATUSES,
        )

    opportunities = get_opportunities(
        search=search,
        country=country,
        industry=industry,
        status=status,
        urgency=urgency,
        opportunity_type=opportunity_type,
    )

    st.caption(f"{len(opportunities)} opportunity record(s) found")

    if not opportunities:
        st.info("No market opportunities found.")
        return

    table_data = []

    for opportunity in opportunities:
        score = calculate_opportunity_score(
            demand_score=opportunity.demand_score,
            competition_score=opportunity.competition_score,
            confidence_score=opportunity.confidence_score,
            urgency=opportunity.urgency,
        )

        table_data.append(
            {
                "ID": opportunity.id,
                "Opportunity": opportunity.title,
                "Product": opportunity.product,
                "Buyer": opportunity.buyer_company or "",
                "Industry": opportunity.industry,
                "Country": opportunity.country,
                "Type": opportunity.opportunity_type,
                "Quantity": opportunity.estimated_quantity or "",
                "Margin": opportunity.expected_margin or "",
                "Demand": opportunity.demand_score,
                "Confidence": opportunity.confidence_score,
                "Score": score,
                "Urgency": opportunity.urgency,
                "Status": opportunity.status,
            }
        )

    st.dataframe(
        table_data,
        hide_index=True,
        width="stretch",
    )

    selected_opportunity = st.selectbox(
        "Select opportunity",
        options=opportunities,
        format_func=lambda opportunity: (
            f"{opportunity.title} — {opportunity.product}"
        ),
    )

    score = calculate_opportunity_score(
        demand_score=selected_opportunity.demand_score,
        competition_score=selected_opportunity.competition_score,
        confidence_score=selected_opportunity.confidence_score,
        urgency=selected_opportunity.urgency,
    )

    st.markdown("---")
    st.subheader("Opportunity Intelligence")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Opportunity Score", f"{score}/100")
    col2.metric("Demand", f"{selected_opportunity.demand_score}/100")
    col3.metric(
        "Competition",
        f"{selected_opportunity.competition_score}/100",
    )
    col4.metric(
        "Confidence",
        f"{selected_opportunity.confidence_score}/100",
    )

    st.info(get_recommendation(score))

    st.markdown("---")
    st.subheader("Edit or Delete Opportunity")

    with st.form(
        f"edit_market_opportunity_{selected_opportunity.id}"
    ):
        title = st.text_input(
            "Opportunity title",
            value=selected_opportunity.title,
        )

        product = st.text_input(
            "Product or service",
            value=selected_opportunity.product,
        )

        industry = st.text_input(
            "Industry",
            value=selected_opportunity.industry,
        )

        country = st.text_input(
            "Country",
            value=selected_opportunity.country,
        )

        state = st.text_input(
            "State or region",
            value=selected_opportunity.state or "",
        )

        city = st.text_input(
            "City",
            value=selected_opportunity.city or "",
        )

        buyer_company = st.text_input(
            "Buyer or company",
            value=selected_opportunity.buyer_company or "",
        )

        opportunity_type = st.selectbox(
            "Opportunity type",
            OPPORTUNITY_TYPES,
            index=(
                OPPORTUNITY_TYPES.index(
                    selected_opportunity.opportunity_type
                )
                if selected_opportunity.opportunity_type
                in OPPORTUNITY_TYPES
                else 0
            ),
        )

        estimated_quantity = st.text_input(
            "Estimated quantity",
            value=selected_opportunity.estimated_quantity or "",
        )

        target_price = st.text_input(
            "Buyer target price",
            value=selected_opportunity.target_price or "",
        )

        estimated_landed_cost = st.text_input(
            "Estimated landed cost",
            value=selected_opportunity.estimated_landed_cost or "",
        )

        estimated_sale_price = st.text_input(
            "Estimated sale price",
            value=selected_opportunity.estimated_sale_price or "",
        )

        expected_margin = st.text_input(
            "Expected margin",
            value=selected_opportunity.expected_margin or "",
        )

        urgency = st.selectbox(
            "Urgency",
            URGENCY_LEVELS,
            index=URGENCY_LEVELS.index(selected_opportunity.urgency),
        )

        demand_score = st.slider(
            "Demand confidence",
            0,
            100,
            selected_opportunity.demand_score,
        )

        competition_score = st.slider(
            "Competition level",
            0,
            100,
            selected_opportunity.competition_score,
        )

        confidence_score = st.slider(
            "Information confidence",
            0,
            100,
            selected_opportunity.confidence_score,
        )

        status = st.selectbox(
            "Status",
            STATUSES,
            index=(
                STATUSES.index(selected_opportunity.status)
                if selected_opportunity.status in STATUSES
                else 0
            ),
        )

        source = st.text_input(
            "Source",
            value=selected_opportunity.source or "",
        )

        notes = st.text_area(
            "Analysis and notes",
            value=selected_opportunity.notes or "",
            height=200,
        )

        update_submitted = st.form_submit_button(
            "Update Opportunity",
            type="primary",
            width="stretch",
        )

    if update_submitted:
        if (
            not title.strip()
            or not product.strip()
            or not industry.strip()
            or not country.strip()
        ):
            st.warning(
                "Title, product, industry, and country are required."
            )
        else:
            update_opportunity(
                MarketOpportunity(
                    id=selected_opportunity.id,
                    title=title,
                    product=product,
                    industry=industry,
                    country=country,
                    state=state,
                    city=city,
                    buyer_company=buyer_company,
                    opportunity_type=opportunity_type,
                    estimated_quantity=estimated_quantity,
                    target_price=target_price,
                    estimated_landed_cost=estimated_landed_cost,
                    estimated_sale_price=estimated_sale_price,
                    expected_margin=expected_margin,
                    urgency=urgency,
                    demand_score=demand_score,
                    competition_score=competition_score,
                    confidence_score=confidence_score,
                    status=status,
                    source=source,
                    notes=notes,
                )
            )

            st.success("Market opportunity updated successfully.")
            st.rerun()

    confirm_delete = st.checkbox(
        f"Confirm deletion of {selected_opportunity.title}"
    )

    if st.button(
        "Delete Opportunity",
        disabled=not confirm_delete,
    ):
        delete_opportunity(selected_opportunity.id)
        st.success("Market opportunity deleted successfully.")
        st.rerun()