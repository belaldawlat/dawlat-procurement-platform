from datetime import date, timedelta

import streamlit as st

from models.logistics_quote import LogisticsQuote
from services.logistics_quote_service import (
    create_logistics_quote,
    delete_logistics_quote,
    get_logistics_quotes,
)
from services.partner_service import get_partners
from services.rfq_service import get_rfqs
from services.supplier_quote_service import get_supplier_quotes


PROVIDER_TYPES = [
    "Freight Forwarder",
    "Customs Broker",
    "Freight & Customs Provider",
    "Shipping Line",
    "Air Freight Provider",
    "Courier",
    "Trucking Company",
    "3PL Provider",
    "Warehouse Provider",
    "Inspection Provider",
    "Other",
]

TRANSPORT_MODES = [
    "Sea Freight",
    "Air Freight",
    "Road Freight",
    "Rail Freight",
    "Courier",
    "Multimodal",
]

SERVICE_TYPES = [
    "Port to Port",
    "Door to Port",
    "Port to Door",
    "Door to Door",
    "Customs Clearance Only",
    "Freight Only",
    "Freight and Customs",
    "Full Supply Chain",
]

CONTAINER_TYPES = [
    "Not Applicable",
    "20ft General Purpose",
    "40ft General Purpose",
    "40ft High Cube",
    "20ft Reefer",
    "40ft Reefer",
    "LCL",
    "Air Cargo",
    "Pallet",
    "Parcel",
]

INCOTERMS = [
    "Not Specified",
    "EXW",
    "FCA",
    "FAS",
    "FOB",
    "CFR",
    "CIF",
    "CPT",
    "CIP",
    "DAP",
    "DPU",
    "DDP",
]

CURRENCIES = [
    "AUD",
    "USD",
    "EUR",
    "GBP",
    "CNY",
    "VND",
    "PKR",
    "INR",
]

STATUSES = [
    "Requested",
    "Received",
    "Under Review",
    "Clarification Required",
    "Shortlisted",
    "Selected",
    "Rejected",
    "Expired",
]


def calculate_provider_score(quote: LogisticsQuote) -> int:
    transit_score = max(
        0,
        100 - min(quote.transit_days, 100),
    )

    score = (
        quote.price_score * 0.25
        + quote.reliability_score * 0.25
        + quote.service_score * 0.20
        + quote.communication_score * 0.15
        + transit_score * 0.15
        - quote.risk_score * 0.15
    )

    return max(0, min(100, round(score)))


def show() -> None:
    st.title("🚢 Freight, Customs & Logistics")
    st.caption(
        "Manage freight forwarders, customs brokers, shipping providers, "
        "routes, service quotations, clearance costs and door delivery."
    )

    add_tab, register_tab, comparison_tab = st.tabs(
        [
            "➕ Record Logistics Quote",
            "📋 Logistics Register",
            "⚖️ Provider Comparison",
        ]
    )

    with add_tab:
        show_add_quote()

    with register_tab:
        show_register()

    with comparison_tab:
        show_comparison()


def show_add_quote() -> None:
    st.subheader("Record Freight or Customs Quotation")

    rfqs = get_rfqs()
    supplier_quotes = get_supplier_quotes()
    partners = get_partners()

    logistics_partners = [
        partner
        for partner in partners
        if partner.partner_type
        in {
            "Freight Forwarder",
            "Customs Broker",
            "Freight & Customs Provider",
            "Shipping Line",
            "Courier",
            "Trucking Company",
            "3PL Provider",
            "Warehouse",
            "Inspection Company",
        }
    ]

    provider_mode = st.radio(
        "Provider source",
        [
            "Existing Partner",
            "Manual Provider",
        ],
        horizontal=True,
    )

    selected_provider = None
    manual_provider_name = ""
    manual_provider_type = PROVIDER_TYPES[0]

    if provider_mode == "Existing Partner":
        if logistics_partners:
            selected_provider = st.selectbox(
                "Provider",
                logistics_partners,
                format_func=lambda provider: (
                    f"{provider.company_name} — "
                    f"{provider.partner_type} — "
                    f"{provider.country}"
                ),
            )
        else:
            st.info(
                "No logistics partners are saved yet. "
                "Select Manual Provider."
            )

    else:
        col1, col2 = st.columns(2)

        with col1:
            manual_provider_name = st.text_input(
                "Provider company name *"
            )

        with col2:
            manual_provider_type = st.selectbox(
                "Provider type",
                PROVIDER_TYPES,
            )

    st.markdown("### Linked Records")

    rfq_options = [None] + rfqs

    selected_rfq = st.selectbox(
        "Linked RFQ",
        rfq_options,
        format_func=lambda rfq: (
            "No linked RFQ"
            if rfq is None
            else f"{rfq.rfq_number} — {rfq.title}"
        ),
    )

    quote_options = [None] + supplier_quotes

    selected_supplier_quote = st.selectbox(
        "Linked supplier quotation",
        quote_options,
        format_func=lambda quote: (
            "No linked supplier quotation"
            if quote is None
            else (
                f"{quote.supplier_name} — "
                f"{quote.currency} {quote.quoted_total:,.2f}"
            )
        ),
    )

    st.markdown("### Route and Service")

    col1, col2 = st.columns(2)

    with col1:
        origin_country = st.text_input(
            "Origin country *",
        )

        origin_city_port = st.text_input(
            "Origin city or port",
            placeholder="Example: Ho Chi Minh City / Cat Lai Port",
        )

        transport_mode = st.selectbox(
            "Transport mode",
            TRANSPORT_MODES,
        )

        container_type = st.selectbox(
            "Container or cargo type",
            CONTAINER_TYPES,
        )

    with col2:
        destination_country = st.text_input(
            "Destination country *",
            value="Australia",
        )

        destination_city_port = st.text_input(
            "Destination city or port *",
            value="Melbourne",
        )

        service_type = st.selectbox(
            "Service type",
            SERVICE_TYPES,
        )

        incoterm = st.selectbox(
            "Related Incoterm",
            INCOTERMS,
        )

    cargo_description = st.text_area(
        "Cargo description *",
        placeholder=(
            "Example: Vietnamese ST25 rice in 5 kg and 25 kg bags"
        ),
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        quantity = st.number_input(
            "Quantity",
            min_value=0.0,
            value=1.0,
        )

    with col2:
        unit = st.text_input(
            "Unit",
            value="shipment",
        )

    with col3:
        gross_weight_kg = st.number_input(
            "Gross weight (kg)",
            min_value=0.0,
        )

    with col4:
        volume_cbm = st.number_input(
            "Volume (CBM)",
            min_value=0.0,
        )

    st.markdown("### Quoted Costs")

    currency = st.selectbox(
        "Currency",
        CURRENCIES,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        freight_cost = st.number_input(
            "International freight",
            min_value=0.0,
        )

        origin_charges = st.number_input(
            "Origin charges",
            min_value=0.0,
        )

        destination_charges = st.number_input(
            "Destination port charges",
            min_value=0.0,
        )

        customs_clearance_fee = st.number_input(
            "Customs clearance fee",
            min_value=0.0,
        )

    with col2:
        biosecurity_fee = st.number_input(
            "Biosecurity or quarantine",
            min_value=0.0,
        )

        inspection_fee = st.number_input(
            "Inspection fee",
            min_value=0.0,
        )

        local_delivery_fee = st.number_input(
            "Local delivery",
            min_value=0.0,
        )

        warehouse_fee = st.number_input(
            "Warehouse or storage",
            min_value=0.0,
        )

    with col3:
        insurance_cost = st.number_input(
            "Cargo insurance",
            min_value=0.0,
        )

        documentation_fee = st.number_input(
            "Documentation fee",
            min_value=0.0,
        )

        other_costs = st.number_input(
            "Other costs",
            min_value=0.0,
        )

    st.markdown("### Timing and Coverage")

    col1, col2 = st.columns(2)

    with col1:
        transit_days = st.number_input(
            "Estimated transit days",
            min_value=0,
            value=1,
            step=1,
        )

        validity_date = st.date_input(
            "Quotation valid until",
            value=date.today() + timedelta(days=30),
        )

    with col2:
        departure_frequency = st.text_input(
            "Departure frequency",
            placeholder="Example: Weekly",
        )

        route_details = st.text_area(
            "Route and transshipment details",
        )

    inclusions = st.text_area(
        "Included services",
        placeholder=(
            "Freight, clearance, terminal handling, delivery, "
            "biosecurity coordination, documentation, tracking."
        ),
    )

    exclusions = st.text_area(
        "Excluded costs and services",
        placeholder=(
            "Duty, GST, demurrage, detention, storage after free time, "
            "inspection, fumigation, unexpected government charges."
        ),
    )

    st.markdown("### Provider Evaluation")

    reliability_score = st.slider(
        "Reliability score",
        0,
        100,
        50,
    )

    communication_score = st.slider(
        "Communication score",
        0,
        100,
        50,
    )

    price_score = st.slider(
        "Price competitiveness",
        0,
        100,
        50,
    )

    service_score = st.slider(
        "Service coverage",
        0,
        100,
        50,
    )

    risk_score = st.slider(
        "Risk level",
        0,
        100,
        50,
        help="Higher means more risk.",
    )

    status = st.selectbox(
        "Quotation status",
        STATUSES,
        index=1,
    )

    notes = st.text_area(
        "Internal notes",
    )

    total_preview = (
        freight_cost
        + origin_charges
        + destination_charges
        + customs_clearance_fee
        + biosecurity_fee
        + inspection_fee
        + local_delivery_fee
        + warehouse_fee
        + insurance_cost
        + documentation_fee
        + other_costs
    )

    st.metric(
        "Quoted Logistics Total",
        f"{currency} {total_preview:,.2f}",
    )

    if not st.button(
        "Save Logistics Quotation",
        type="primary",
        width="stretch",
    ):
        return

    if provider_mode == "Existing Partner":
        if selected_provider is None:
            st.warning("Select an existing provider.")
            return

        provider_name = selected_provider.company_name
        provider_type = selected_provider.partner_type

    else:
        provider_name = manual_provider_name.strip()
        provider_type = manual_provider_type

        if not provider_name:
            st.warning("Provider company name is required.")
            return

    if not origin_country.strip():
        st.warning("Origin country is required.")
        return

    if not destination_country.strip():
        st.warning("Destination country is required.")
        return

    if not destination_city_port.strip():
        st.warning("Destination city or port is required.")
        return

    if not cargo_description.strip():
        st.warning("Cargo description is required.")
        return

    quote = LogisticsQuote(
        provider_name=provider_name,
        provider_type=provider_type,
        rfq_id=selected_rfq.id if selected_rfq else None,
        supplier_quote_id=(
            selected_supplier_quote.id
            if selected_supplier_quote
            else None
        ),
        origin_country=origin_country,
        origin_city_port=origin_city_port,
        destination_country=destination_country,
        destination_city_port=destination_city_port,
        transport_mode=transport_mode,
        service_type=service_type,
        container_type=container_type,
        incoterm=incoterm,
        cargo_description=cargo_description,
        quantity=quantity,
        unit=unit,
        gross_weight_kg=gross_weight_kg,
        volume_cbm=volume_cbm,
        currency=currency,
        freight_cost=freight_cost,
        origin_charges=origin_charges,
        destination_charges=destination_charges,
        customs_clearance_fee=customs_clearance_fee,
        biosecurity_fee=biosecurity_fee,
        inspection_fee=inspection_fee,
        local_delivery_fee=local_delivery_fee,
        warehouse_fee=warehouse_fee,
        insurance_cost=insurance_cost,
        documentation_fee=documentation_fee,
        other_costs=other_costs,
        transit_days=int(transit_days),
        validity_date=validity_date.isoformat(),
        departure_frequency=departure_frequency,
        route_details=route_details,
        inclusions=inclusions,
        exclusions=exclusions,
        reliability_score=reliability_score,
        communication_score=communication_score,
        price_score=price_score,
        service_score=service_score,
        risk_score=risk_score,
        status=status,
        notes=notes,
    )

    quote_id = create_logistics_quote(quote)

    st.success(
        f"Logistics quotation saved successfully. ID: {quote_id}"
    )

    st.info(
        f"Quoted logistics total: "
        f"{quote.currency} {quote.total_cost:,.2f}"
    )


def show_register() -> None:
    st.subheader("Freight and Customs Register")

    search = st.text_input(
        "Search logistics quotations",
        placeholder=(
            "Search provider, origin, destination, cargo or route"
        ),
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        provider_type = st.selectbox(
            "Provider type",
            ["All"] + PROVIDER_TYPES,
        )

    with col2:
        transport_mode = st.selectbox(
            "Transport mode",
            ["All"] + TRANSPORT_MODES,
        )

    with col3:
        status = st.selectbox(
            "Status",
            ["All"] + STATUSES,
        )

    quotes = get_logistics_quotes(
        search=search,
        provider_type=provider_type,
        transport_mode=transport_mode,
        status=status,
    )

    st.caption(f"{len(quotes)} logistics quotation(s) found")

    if not quotes:
        st.info("No logistics quotations found.")
        return

    st.dataframe(
        [
            {
                "ID": quote.id,
                "Provider": quote.provider_name,
                "Type": quote.provider_type,
                "Mode": quote.transport_mode,
                "Service": quote.service_type,
                "Origin": (
                    f"{quote.origin_city_port or ''}, "
                    f"{quote.origin_country}"
                ).strip(", "),
                "Destination": (
                    f"{quote.destination_city_port}, "
                    f"{quote.destination_country}"
                ),
                "Container": quote.container_type or "",
                "Currency": quote.currency,
                "Total Cost": quote.total_cost,
                "Transit Days": quote.transit_days,
                "Risk": quote.risk_score,
                "Score": calculate_provider_score(quote),
                "Status": quote.status,
            }
            for quote in quotes
        ],
        hide_index=True,
        width="stretch",
    )

    selected_quote = st.selectbox(
        "Select logistics quotation",
        quotes,
        format_func=lambda quote: (
            f"{quote.provider_name} — "
            f"{quote.currency} {quote.total_cost:,.2f}"
        ),
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Logistics Cost",
        f"{selected_quote.currency} "
        f"{selected_quote.total_cost:,.2f}",
    )

    col2.metric(
        "Transit Time",
        f"{selected_quote.transit_days} days",
    )

    col3.metric(
        "Provider Score",
        f"{calculate_provider_score(selected_quote)}/100",
    )

    col4.metric(
        "Risk",
        f"{selected_quote.risk_score}/100",
    )

    with st.expander("Route, inclusions and exclusions"):
        st.markdown("**Route**")
        st.write(
            selected_quote.route_details
            or "No route details recorded."
        )

        st.markdown("**Included services**")
        st.write(
            selected_quote.inclusions
            or "No inclusions recorded."
        )

        st.markdown("**Excluded services and costs**")
        st.write(
            selected_quote.exclusions
            or "No exclusions recorded."
        )

    confirm_delete = st.checkbox(
        f"Confirm deletion of quotation from "
        f"{selected_quote.provider_name}"
    )

    if st.button(
        "Delete Logistics Quotation",
        disabled=not confirm_delete,
    ):
        delete_logistics_quote(selected_quote.id)
        st.success("Logistics quotation deleted.")
        st.rerun()


def show_comparison() -> None:
    st.subheader("Logistics Provider Comparison")

    quotes = get_logistics_quotes()

    if not quotes:
        st.info(
            "Record at least one logistics quotation first."
        )
        return

    same_currency = st.checkbox(
        "I confirm the compared quotations use the same currency",
        value=False,
    )

    ranked_quotes = sorted(
        quotes,
        key=lambda quote: calculate_provider_score(quote),
        reverse=True,
    )

    best_quote = ranked_quotes[0]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Recommended Provider",
        best_quote.provider_name,
    )

    col2.metric(
        "Decision Score",
        f"{calculate_provider_score(best_quote)}/100",
    )

    col3.metric(
        "Quoted Total",
        f"{best_quote.currency} "
        f"{best_quote.total_cost:,.2f}",
    )

    col4.metric(
        "Transit Time",
        f"{best_quote.transit_days} days",
    )

    st.dataframe(
        [
            {
                "Rank": rank,
                "Provider": quote.provider_name,
                "Provider Type": quote.provider_type,
                "Transport": quote.transport_mode,
                "Service": quote.service_type,
                "Currency": quote.currency,
                "Total Cost": quote.total_cost,
                "Transit Days": quote.transit_days,
                "Reliability": quote.reliability_score,
                "Communication": quote.communication_score,
                "Price": quote.price_score,
                "Service Coverage": quote.service_score,
                "Risk": quote.risk_score,
                "Decision Score": calculate_provider_score(quote),
            }
            for rank, quote in enumerate(
                ranked_quotes,
                start=1,
            )
        ],
        hide_index=True,
        width="stretch",
    )

    if not same_currency:
        st.warning(
            "Do not compare total prices directly when quotations use "
            "different currencies. Convert them using a verified exchange "
            "rate before selecting a provider."
        )

    st.info(
        "Before selection, confirm free storage time, demurrage, "
        "detention, customs exclusions, biosecurity fees, GST, duty, "
        "route changes and door-delivery responsibilities."
    )