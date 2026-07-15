import streamlit as st

from models.warehouse_quote import WarehouseQuote
from services.logistics_quote_service import (
    get_logistics_quotes,
)
from services.partner_service import get_partners
from services.rfq_service import get_rfqs
from services.supplier_quote_service import (
    get_supplier_quotes,
)
from services.warehouse_quote_service import (
    create_warehouse_quote,
    delete_warehouse_quote,
    get_warehouse_quotes,
)


PROVIDER_TYPES = [
    "Warehouse Provider",
    "3PL Provider",
    "Fulfilment Centre",
    "Cold Storage Provider",
    "Bonded Warehouse",
    "Cross-Docking Provider",
    "Container Depot",
    "Distribution Centre",
    "Other",
]

WAREHOUSE_TYPES = [
    "Dry Storage",
    "Food-Grade Dry Storage",
    "Cold Storage",
    "Frozen Storage",
    "Bonded Storage",
    "Hazardous Goods Storage",
    "General Warehouse",
    "Fulfilment Centre",
    "Container Yard",
    "Cross-Dock Facility",
]

SERVICE_MODELS = [
    "Storage Only",
    "Storage and Distribution",
    "Full 3PL",
    "E-commerce Fulfilment",
    "Wholesale Distribution",
    "Cross-Docking",
    "Container Unpacking",
    "Pick and Pack",
    "Custom Service Package",
]

STORAGE_UNITS = [
    "pallet per day",
    "pallet per week",
    "pallet per month",
    "carton per day",
    "carton per month",
    "square metre per day",
    "square metre per month",
    "cubic metre per day",
    "cubic metre per month",
    "tonne per day",
    "tonne per month",
    "container",
    "shipment",
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


def calculate_provider_score(
    quote: WarehouseQuote,
) -> int:
    score = (
        quote.price_score * 0.20
        + quote.location_score * 0.15
        + quote.service_score * 0.15
        + quote.capacity_score * 0.10
        + quote.technology_score * 0.10
        + quote.reliability_score * 0.10
        + quote.communication_score * 0.05
        + quote.compliance_score * 0.15
        - quote.risk_score * 0.15
    )

    return max(0, min(100, round(score)))


def show() -> None:
    st.title("🏭 Warehouses & 3PL")
    st.caption(
        "Manage warehouse providers, fulfilment centres, "
        "storage pricing, container unloading, pick and pack, "
        "distribution services, capacity, compliance and risk."
    )

    add_tab, register_tab, comparison_tab = st.tabs(
        [
            "➕ Record Warehouse Quote",
            "📋 Warehouse Register",
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
    partners = get_partners()
    rfqs = get_rfqs()
    supplier_quotes = get_supplier_quotes()
    logistics_quotes = get_logistics_quotes()

    warehouse_partners = [
        partner
        for partner in partners
        if partner.partner_type
        in {
            "Warehouse Provider",
            "Warehouse",
            "3PL Provider",
            "Fulfilment Centre",
            "Cold Storage Provider",
            "Bonded Warehouse",
            "Distribution Centre",
        }
    ]

    st.subheader("Record Warehouse or 3PL Quotation")

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
        if warehouse_partners:
            selected_provider = st.selectbox(
                "Warehouse or 3PL provider",
                warehouse_partners,
                format_func=lambda provider: (
                    f"{provider.company_name} — "
                    f"{provider.partner_type} — "
                    f"{provider.country}"
                ),
            )
        else:
            st.info(
                "No warehouse or 3PL partners are saved. "
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

    logistics_options = [None] + logistics_quotes

    selected_logistics_quote = st.selectbox(
        "Linked logistics quotation",
        logistics_options,
        format_func=lambda quote: (
            "No linked logistics quotation"
            if quote is None
            else (
                f"{quote.provider_name} — "
                f"{quote.origin_country} to "
                f"{quote.destination_city_port}"
            )
        ),
    )

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

    supplier_quote_options = [None] + supplier_quotes

    selected_supplier_quote = st.selectbox(
        "Linked supplier quotation",
        supplier_quote_options,
        format_func=lambda quote: (
            "No linked supplier quotation"
            if quote is None
            else (
                f"{quote.supplier_name} — "
                f"{quote.currency} {quote.quoted_total:,.2f}"
            )
        ),
    )

    st.markdown("### Location and Facility")

    col1, col2 = st.columns(2)

    with col1:
        country = st.text_input(
            "Country *",
            value="Australia",
        )

        state_region = st.text_input(
            "State or region",
            value="Victoria",
        )

        city = st.text_input(
            "City *",
            value="Melbourne",
        )

        address = st.text_input(
            "Warehouse address",
        )

    with col2:
        warehouse_type = st.selectbox(
            "Warehouse type",
            WAREHOUSE_TYPES,
        )

        service_model = st.selectbox(
            "Service model",
            SERVICE_MODELS,
        )

        temperature_controlled = st.checkbox(
            "Temperature controlled"
        )

        bonded_warehouse = st.checkbox(
            "Bonded warehouse"
        )

        food_grade = st.checkbox(
            "Food-grade facility"
        )

    st.markdown("### Storage Requirement")

    product_description = st.text_area(
        "Product or cargo description *",
        placeholder=(
            "Example: ST25 rice packed in 5 kg and 25 kg bags"
        ),
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        quantity = st.number_input(
            "Storage quantity *",
            min_value=0.0,
            value=1.0,
        )

    with col2:
        storage_unit = st.selectbox(
            "Storage pricing unit",
            STORAGE_UNITS,
        )

    with col3:
        estimated_storage_days = st.number_input(
            "Estimated storage days",
            min_value=0,
            value=30,
            step=1,
        )

    st.markdown("### Pricing")

    currency = st.selectbox(
        "Currency",
        CURRENCIES,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        receiving_fee = st.number_input(
            "Receiving fee",
            min_value=0.0,
        )

        container_unloading_fee = st.number_input(
            "Container unloading fee",
            min_value=0.0,
        )

        devanning_fee = st.number_input(
            "Devanning fee",
            min_value=0.0,
        )

        storage_rate = st.number_input(
            f"Storage rate per {storage_unit}",
            min_value=0.0,
        )

        minimum_monthly_charge = st.number_input(
            "Minimum monthly charge",
            min_value=0.0,
        )

    with col2:
        pallet_in_fee = st.number_input(
            "Pallet-in fee",
            min_value=0.0,
        )

        pallet_out_fee = st.number_input(
            "Pallet-out fee",
            min_value=0.0,
        )

        pick_pack_fee = st.number_input(
            "Pick-and-pack fee",
            min_value=0.0,
        )

        labelling_fee = st.number_input(
            "Labelling fee",
            min_value=0.0,
        )

        repacking_fee = st.number_input(
            "Repacking fee",
            min_value=0.0,
        )

    with col3:
        cross_docking_fee = st.number_input(
            "Cross-docking fee",
            min_value=0.0,
        )

        inventory_management_fee = st.number_input(
            "Inventory management fee",
            min_value=0.0,
        )

        local_delivery_fee = st.number_input(
            "Local delivery fee",
            min_value=0.0,
        )

        disposal_fee = st.number_input(
            "Returns or disposal fee",
            min_value=0.0,
        )

        other_costs = st.number_input(
            "Other costs",
            min_value=0.0,
        )

    col1, col2 = st.columns(2)

    with col1:
        free_storage_days = st.number_input(
            "Free storage days",
            min_value=0,
            value=0,
            step=1,
        )

    with col2:
        minimum_term_months = st.number_input(
            "Minimum contract term in months",
            min_value=0,
            value=0,
            step=1,
        )

    st.markdown("### Capacity and Services")

    capacity_description = st.text_area(
        "Capacity and availability",
        placeholder=(
            "Available pallets, maximum stock, container capacity, "
            "seasonal limits and expansion options."
        ),
    )

    delivery_zones = st.text_area(
        "Delivery zones and transport coverage",
    )

    operating_hours = st.text_input(
        "Operating hours",
    )

    systems_integrations = st.text_area(
        "Warehouse systems and integrations",
        placeholder=(
            "WMS, barcode scanning, API, Shopify, marketplaces, "
            "EDI, customer portal and stock reporting."
        ),
    )

    insurance_details = st.text_area(
        "Insurance coverage",
    )

    certifications = st.text_area(
        "Licences and certifications",
        placeholder=(
            "Food licence, HACCP, ISO, bonded approval, "
            "dangerous-goods approval or cold-chain certification."
        ),
    )

    inclusions = st.text_area(
        "Included services",
    )

    exclusions = st.text_area(
        "Excluded services and additional charges",
    )

    st.markdown("### Provider Evaluation")

    price_score = st.slider(
        "Price competitiveness",
        0,
        100,
        50,
    )

    location_score = st.slider(
        "Location suitability",
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

    capacity_score = st.slider(
        "Capacity and scalability",
        0,
        100,
        50,
    )

    technology_score = st.slider(
        "Technology and system capability",
        0,
        100,
        50,
    )

    reliability_score = st.slider(
        "Reliability",
        0,
        100,
        50,
    )

    communication_score = st.slider(
        "Communication",
        0,
        100,
        50,
    )

    compliance_score = st.slider(
        "Compliance and certification",
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

    preview_quote = WarehouseQuote(
        provider_name="Preview",
        provider_type=manual_provider_type,
        logistics_quote_id=None,
        rfq_id=None,
        supplier_quote_id=None,
        country=country,
        state_region=state_region,
        city=city,
        address=address,
        warehouse_type=warehouse_type,
        service_model=service_model,
        temperature_controlled=temperature_controlled,
        bonded_warehouse=bonded_warehouse,
        food_grade=food_grade,
        product_description=product_description,
        quantity=quantity,
        storage_unit=storage_unit,
        estimated_storage_days=int(
            estimated_storage_days
        ),
        currency=currency,
        receiving_fee=receiving_fee,
        container_unloading_fee=container_unloading_fee,
        devanning_fee=devanning_fee,
        storage_rate=storage_rate,
        minimum_monthly_charge=minimum_monthly_charge,
        pallet_in_fee=pallet_in_fee,
        pallet_out_fee=pallet_out_fee,
        pick_pack_fee=pick_pack_fee,
        labelling_fee=labelling_fee,
        repacking_fee=repacking_fee,
        cross_docking_fee=cross_docking_fee,
        inventory_management_fee=inventory_management_fee,
        local_delivery_fee=local_delivery_fee,
        disposal_fee=disposal_fee,
        other_costs=other_costs,
        free_storage_days=int(free_storage_days),
        minimum_term_months=int(minimum_term_months),
        capacity_description=capacity_description,
        delivery_zones=delivery_zones,
        operating_hours=operating_hours,
        systems_integrations=systems_integrations,
        insurance_details=insurance_details,
        certifications=certifications,
        inclusions=inclusions,
        exclusions=exclusions,
        price_score=price_score,
        location_score=location_score,
        service_score=service_score,
        capacity_score=capacity_score,
        technology_score=technology_score,
        reliability_score=reliability_score,
        communication_score=communication_score,
        compliance_score=compliance_score,
        risk_score=risk_score,
        status=status,
        notes=notes,
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Estimated Storage Cost",
        f"{currency} "
        f"{preview_quote.estimated_storage_cost:,.2f}",
    )

    col2.metric(
        "Total Estimated Cost",
        f"{currency} "
        f"{preview_quote.total_estimated_cost:,.2f}",
    )

    col3.metric(
        "Provider Score",
        f"{calculate_provider_score(preview_quote)}/100",
    )

    if not st.button(
        "Save Warehouse Quotation",
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

    if not country.strip():
        st.warning("Country is required.")
        return

    if not city.strip():
        st.warning("City is required.")
        return

    if not product_description.strip():
        st.warning(
            "Product or cargo description is required."
        )
        return

    if quantity <= 0:
        st.warning(
            "Storage quantity must be greater than zero."
        )
        return

    quote = WarehouseQuote(
        provider_name=provider_name,
        provider_type=provider_type,
        logistics_quote_id=(
            selected_logistics_quote.id
            if selected_logistics_quote
            else None
        ),
        rfq_id=(
            selected_rfq.id
            if selected_rfq
            else None
        ),
        supplier_quote_id=(
            selected_supplier_quote.id
            if selected_supplier_quote
            else None
        ),
        country=country,
        state_region=state_region,
        city=city,
        address=address,
        warehouse_type=warehouse_type,
        service_model=service_model,
        temperature_controlled=temperature_controlled,
        bonded_warehouse=bonded_warehouse,
        food_grade=food_grade,
        product_description=product_description,
        quantity=quantity,
        storage_unit=storage_unit,
        estimated_storage_days=int(
            estimated_storage_days
        ),
        currency=currency,
        receiving_fee=receiving_fee,
        container_unloading_fee=container_unloading_fee,
        devanning_fee=devanning_fee,
        storage_rate=storage_rate,
        minimum_monthly_charge=minimum_monthly_charge,
        pallet_in_fee=pallet_in_fee,
        pallet_out_fee=pallet_out_fee,
        pick_pack_fee=pick_pack_fee,
        labelling_fee=labelling_fee,
        repacking_fee=repacking_fee,
        cross_docking_fee=cross_docking_fee,
        inventory_management_fee=inventory_management_fee,
        local_delivery_fee=local_delivery_fee,
        disposal_fee=disposal_fee,
        other_costs=other_costs,
        free_storage_days=int(free_storage_days),
        minimum_term_months=int(
            minimum_term_months
        ),
        capacity_description=capacity_description,
        delivery_zones=delivery_zones,
        operating_hours=operating_hours,
        systems_integrations=systems_integrations,
        insurance_details=insurance_details,
        certifications=certifications,
        inclusions=inclusions,
        exclusions=exclusions,
        price_score=price_score,
        location_score=location_score,
        service_score=service_score,
        capacity_score=capacity_score,
        technology_score=technology_score,
        reliability_score=reliability_score,
        communication_score=communication_score,
        compliance_score=compliance_score,
        risk_score=risk_score,
        status=status,
        notes=notes,
    )

    quote_id = create_warehouse_quote(quote)

    st.success(
        f"Warehouse quotation saved successfully. ID: {quote_id}"
    )

    st.info(
        f"Estimated total: "
        f"{quote.currency} {quote.total_estimated_cost:,.2f}"
    )


def show_register() -> None:
    st.subheader("Warehouse and 3PL Register")

    search = st.text_input(
        "Search warehouse quotations",
        placeholder=(
            "Search provider, city, address, product or delivery zone"
        ),
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        provider_type = st.selectbox(
            "Provider type",
            ["All"] + PROVIDER_TYPES,
        )

    with col2:
        warehouse_type = st.selectbox(
            "Warehouse type",
            ["All"] + WAREHOUSE_TYPES,
        )

    with col3:
        status = st.selectbox(
            "Status",
            ["All"] + STATUSES,
        )

    quotes = get_warehouse_quotes(
        search=search,
        provider_type=provider_type,
        warehouse_type=warehouse_type,
        status=status,
    )

    st.caption(
        f"{len(quotes)} warehouse quotation(s) found"
    )

    if not quotes:
        st.info("No warehouse quotations found.")
        return

    st.dataframe(
        [
            {
                "ID": quote.id,
                "Provider": quote.provider_name,
                "Type": quote.provider_type,
                "Facility": quote.warehouse_type,
                "Service": quote.service_model,
                "Location": (
                    f"{quote.city}, "
                    f"{quote.state_region or ''}, "
                    f"{quote.country}"
                ).replace(", ,", ","),
                "Quantity": (
                    f"{quote.quantity:g} "
                    f"{quote.storage_unit}"
                ),
                "Storage Days": quote.estimated_storage_days,
                "Currency": quote.currency,
                "Storage Cost": (
                    quote.estimated_storage_cost
                ),
                "Total Cost": (
                    quote.total_estimated_cost
                ),
                "Score": calculate_provider_score(quote),
                "Risk": quote.risk_score,
                "Status": quote.status,
            }
            for quote in quotes
        ],
        hide_index=True,
        width="stretch",
    )

    selected_quote = st.selectbox(
        "Select warehouse quotation",
        quotes,
        format_func=lambda quote: (
            f"{quote.provider_name} — "
            f"{quote.city} — "
            f"{quote.currency} "
            f"{quote.total_estimated_cost:,.2f}"
        ),
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Estimated Cost",
        f"{selected_quote.currency} "
        f"{selected_quote.total_estimated_cost:,.2f}",
    )

    col2.metric(
        "Storage Cost",
        f"{selected_quote.currency} "
        f"{selected_quote.estimated_storage_cost:,.2f}",
    )

    col3.metric(
        "Provider Score",
        f"{calculate_provider_score(selected_quote)}/100",
    )

    col4.metric(
        "Risk",
        f"{selected_quote.risk_score}/100",
    )

    with st.expander(
        "Facility, services and conditions"
    ):
        st.markdown("**Capacity**")
        st.write(
            selected_quote.capacity_description
            or "No capacity information recorded."
        )

        st.markdown("**Delivery zones**")
        st.write(
            selected_quote.delivery_zones
            or "No delivery zones recorded."
        )

        st.markdown("**Systems and integrations**")
        st.write(
            selected_quote.systems_integrations
            or "No system details recorded."
        )

        st.markdown("**Certifications**")
        st.write(
            selected_quote.certifications
            or "No certifications recorded."
        )

        st.markdown("**Included services**")
        st.write(
            selected_quote.inclusions
            or "No inclusions recorded."
        )

        st.markdown("**Excluded services**")
        st.write(
            selected_quote.exclusions
            or "No exclusions recorded."
        )

    confirm_delete = st.checkbox(
        f"Confirm deletion of quotation from "
        f"{selected_quote.provider_name}"
    )

    if st.button(
        "Delete Warehouse Quotation",
        disabled=not confirm_delete,
    ):
        delete_warehouse_quote(selected_quote.id)
        st.success("Warehouse quotation deleted.")
        st.rerun()


def show_comparison() -> None:
    st.subheader("Warehouse Provider Comparison")

    quotes = get_warehouse_quotes()

    if not quotes:
        st.info(
            "Record at least one warehouse quotation first."
        )
        return

    ranked_quotes = sorted(
        quotes,
        key=calculate_provider_score,
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
        "Estimated Cost",
        f"{best_quote.currency} "
        f"{best_quote.total_estimated_cost:,.2f}",
    )

    col4.metric(
        "Location",
        f"{best_quote.city}, {best_quote.country}",
    )

    st.dataframe(
        [
            {
                "Rank": rank,
                "Provider": quote.provider_name,
                "Facility": quote.warehouse_type,
                "Service": quote.service_model,
                "Location": (
                    f"{quote.city}, {quote.country}"
                ),
                "Currency": quote.currency,
                "Estimated Cost": (
                    quote.total_estimated_cost
                ),
                "Free Storage Days": (
                    quote.free_storage_days
                ),
                "Price": quote.price_score,
                "Location Score": quote.location_score,
                "Service": quote.service_score,
                "Capacity": quote.capacity_score,
                "Technology": quote.technology_score,
                "Reliability": quote.reliability_score,
                "Compliance": quote.compliance_score,
                "Risk": quote.risk_score,
                "Decision Score": (
                    calculate_provider_score(quote)
                ),
            }
            for rank, quote in enumerate(
                ranked_quotes,
                start=1,
            )
        ],
        hide_index=True,
        width="stretch",
    )

    st.warning(
        "Confirm that all quotations use comparable quantities, "
        "storage periods, pricing units and currencies before "
        "selecting a provider."
    )

    st.info(
        "Before appointment, verify insurance, food or product "
        "licensing, security, pest control, stock accuracy, "
        "damage liability, service levels, minimum charges, "
        "contract termination and peak-season capacity."
    )