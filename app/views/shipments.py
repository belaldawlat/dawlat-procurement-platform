from datetime import date, timedelta

import streamlit as st

from models.shipment import Shipment, ShipmentMilestone
from services.logistics_quote_service import (
    get_logistics_quotes,
)
from services.rfq_service import get_rfqs
from services.shipment_service import (
    create_shipment,
    create_shipment_milestone,
    delete_shipment,
    ensure_shipment_tables,
    generate_shipment_number,
    get_shipment_milestones,
    get_shipments,
    update_shipment_status,
)
from services.supplier_quote_service import (
    get_supplier_quotes,
)
from services.warehouse_quote_service import (
    get_warehouse_quotes,
)


SHIPMENT_TYPES = [
    "Import Shipment",
    "Export Shipment",
    "Domestic Transfer",
    "Sample Shipment",
    "Customer Delivery",
    "Supplier Return",
]

SHIPMENT_STATUSES = [
    "Planning",
    "Booking Requested",
    "Booked",
    "Awaiting Pickup",
    "Picked Up",
    "In Transit",
    "Arrived at Port",
    "Customs Clearance",
    "Biosecurity Hold",
    "Inspection Hold",
    "Released",
    "Out for Delivery",
    "Delivered",
    "Completed",
    "Delayed",
    "Cancelled",
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
    "Courier",
    "Custom Service",
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

CLEARANCE_STATUSES = [
    "Not Started",
    "Documents Submitted",
    "Under Review",
    "Additional Information Required",
    "Inspection Required",
    "On Hold",
    "Released",
    "Completed",
    "Not Required",
]

DOCUMENT_STATUSES = [
    "Incomplete",
    "Partially Complete",
    "Complete",
    "Verified",
    "Issue Identified",
]

RISK_LEVELS = [
    "Low",
    "Medium",
    "High",
    "Critical",
]

PRIORITIES = [
    "Low",
    "Normal",
    "High",
    "Urgent",
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

MILESTONE_TYPES = [
    "Shipment Created",
    "Booking Requested",
    "Booking Confirmed",
    "Cargo Ready",
    "Cargo Picked Up",
    "Container Loaded",
    "Export Customs Cleared",
    "Departed Origin",
    "Transshipment",
    "Arrived Destination",
    "Import Documents Submitted",
    "Customs Cleared",
    "Biosecurity Cleared",
    "Inspection Completed",
    "Container Released",
    "Local Delivery Started",
    "Delivered to Warehouse",
    "Inventory Received",
    "Shipment Completed",
    "Delay Reported",
    "Other",
]


def show() -> None:
    ensure_shipment_tables()

    st.title("🚚 Shipment Control & Tracking")
    st.caption(
        "Plan and track shipments from supplier pickup through "
        "international transport, customs, biosecurity, warehouse "
        "delivery and inventory receipt."
    )

    overview_tab, create_tab, register_tab, milestone_tab = st.tabs(
        [
            "📊 Shipment Overview",
            "➕ Create Shipment",
            "📋 Shipment Register",
            "🧭 Milestones",
        ]
    )

    with overview_tab:
        show_overview()

    with create_tab:
        show_create_shipment()

    with register_tab:
        show_register()

    with milestone_tab:
        show_milestones()


def show_overview() -> None:
    shipments = get_shipments()

    if not shipments:
        st.info(
            "No shipments exist yet. Create the first shipment."
        )
        return

    active_shipments = [
        shipment
        for shipment in shipments
        if shipment.status
        not in {
            "Delivered",
            "Completed",
            "Cancelled",
        }
    ]

    overdue_shipments = [
        shipment
        for shipment in shipments
        if shipment.is_overdue
    ]

    delayed_shipments = [
        shipment
        for shipment in shipments
        if shipment.status == "Delayed"
        or shipment.delay_reason
    ]

    delivered_shipments = [
        shipment
        for shipment in shipments
        if shipment.status
        in {
            "Delivered",
            "Completed",
        }
    ]

    total_value = sum(
        shipment.total_value
        for shipment in shipments
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Total Shipments",
        len(shipments),
    )

    col2.metric(
        "Active",
        len(active_shipments),
    )

    col3.metric(
        "Overdue",
        len(overdue_shipments),
    )

    col4.metric(
        "Delivered",
        len(delivered_shipments),
    )

    col5.metric(
        "Total Value",
        f"AUD {total_value:,.2f}",
    )

    if overdue_shipments:
        st.error(
            f"{len(overdue_shipments)} shipment(s) are past "
            "their estimated arrival date."
        )

    if delayed_shipments:
        st.warning(
            f"{len(delayed_shipments)} shipment(s) have delays "
            "or recorded delay reasons."
        )

    st.markdown("---")
    st.subheader("Active Shipment Pipeline")

    if not active_shipments:
        st.success("No active shipments.")
        return

    st.dataframe(
        [
            {
                "Shipment": shipment.shipment_number,
                "Product": shipment.product_name,
                "Supplier": shipment.supplier_name,
                "Mode": shipment.transport_mode,
                "Origin": shipment.origin_location,
                "Destination": shipment.destination_location,
                "ETD": shipment.etd or "",
                "ETA": shipment.eta or "",
                "Status": shipment.status,
                "Customs": shipment.customs_status,
                "Documents": (
                    f"{shipment.document_completion_percent}%"
                ),
                "Risk": shipment.risk_level,
                "Priority": shipment.priority,
                "Overdue": (
                    "Yes"
                    if shipment.is_overdue
                    else "No"
                ),
            }
            for shipment in active_shipments
        ],
        hide_index=True,
        width="stretch",
    )


def show_create_shipment() -> None:
    st.subheader("Create Shipment")

    rfqs = get_rfqs()
    supplier_quotes = get_supplier_quotes()
    logistics_quotes = get_logistics_quotes()
    warehouse_quotes = get_warehouse_quotes()

    shipment_number = generate_shipment_number()

    st.text_input(
        "Shipment number",
        value=shipment_number,
        disabled=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        shipment_type = st.selectbox(
            "Shipment type",
            SHIPMENT_TYPES,
        )

    with col2:
        status = st.selectbox(
            "Initial status",
            SHIPMENT_STATUSES,
        )

    st.markdown("### Linked Procurement Records")

    selected_rfq = st.selectbox(
        "Linked RFQ",
        [None] + rfqs,
        format_func=lambda rfq: (
            "No linked RFQ"
            if rfq is None
            else f"{rfq.rfq_number} — {rfq.title}"
        ),
    )

    selected_supplier_quote = st.selectbox(
        "Linked supplier quotation",
        [None] + supplier_quotes,
        format_func=lambda quote: (
            "No linked supplier quotation"
            if quote is None
            else (
                f"{quote.supplier_name} — "
                f"{quote.currency} "
                f"{quote.quoted_total:,.2f}"
            )
        ),
    )

    selected_logistics_quote = st.selectbox(
        "Linked logistics quotation",
        [None] + logistics_quotes,
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

    selected_warehouse = st.selectbox(
        "Destination warehouse",
        [None] + warehouse_quotes,
        format_func=lambda warehouse: (
            "No linked warehouse"
            if warehouse is None
            else (
                f"{warehouse.provider_name} — "
                f"{warehouse.city}, {warehouse.country}"
            )
        ),
    )

    default_supplier = ""
    default_product = ""
    default_quantity = 1.0
    default_unit = "shipment"
    default_currency = "AUD"
    default_goods_value = 0.0

    if selected_supplier_quote:
        default_supplier = (
            selected_supplier_quote.supplier_name
        )
        default_quantity = (
            selected_supplier_quote.quantity
        )
        default_currency = (
            selected_supplier_quote.currency
        )
        default_goods_value = (
            selected_supplier_quote.goods_total
        )

    if selected_rfq:
        default_product = selected_rfq.product_name
        default_unit = selected_rfq.unit

        if not default_supplier:
            default_supplier = (
                selected_rfq.supplier_name or ""
            )

    default_logistics_provider = ""
    default_origin_country = ""
    default_origin_location = ""
    default_destination_country = "Australia"
    default_destination_location = "Melbourne"
    default_transport_mode = "Sea Freight"
    default_service_type = "Door to Door"
    default_container_type = "20ft General Purpose"
    default_incoterm = "CIF"
    default_freight = 0.0
    default_insurance = 0.0
    default_customs = 0.0
    default_biosecurity = 0.0
    default_port = 0.0
    default_delivery = 0.0
    default_storage = 0.0

    if selected_logistics_quote:
        default_logistics_provider = (
            selected_logistics_quote.provider_name
        )
        default_origin_country = (
            selected_logistics_quote.origin_country
        )
        default_origin_location = (
            selected_logistics_quote.origin_city_port
            or selected_logistics_quote.origin_country
        )
        default_destination_country = (
            selected_logistics_quote.destination_country
        )
        default_destination_location = (
            selected_logistics_quote.destination_city_port
        )
        default_transport_mode = (
            selected_logistics_quote.transport_mode
        )
        default_service_type = (
            selected_logistics_quote.service_type
        )
        default_container_type = (
            selected_logistics_quote.container_type
            or default_container_type
        )
        default_incoterm = (
            selected_logistics_quote.incoterm
            or default_incoterm
        )
        default_freight = (
            selected_logistics_quote.freight_cost
        )
        default_insurance = (
            selected_logistics_quote.insurance_cost
        )
        default_customs = (
            selected_logistics_quote.customs_clearance_fee
        )
        default_biosecurity = (
            selected_logistics_quote.biosecurity_fee
        )
        default_port = (
            selected_logistics_quote.destination_charges
        )
        default_delivery = (
            selected_logistics_quote.local_delivery_fee
        )
        default_storage = (
            selected_logistics_quote.warehouse_fee
        )

    default_warehouse_name = ""

    if selected_warehouse:
        default_warehouse_name = (
            selected_warehouse.provider_name
        )

    st.markdown("### Parties and Cargo")

    col1, col2 = st.columns(2)

    with col1:
        supplier_name = st.text_input(
            "Supplier name *",
            value=default_supplier,
        )

        logistics_provider = st.text_input(
            "Logistics provider",
            value=default_logistics_provider,
        )

        warehouse_name = st.text_input(
            "Destination warehouse",
            value=default_warehouse_name,
        )

    with col2:
        product_name = st.text_input(
            "Product name *",
            value=default_product,
        )

        cargo_description = st.text_area(
            "Cargo description *",
            value=default_product,
        )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        quantity = st.number_input(
            "Quantity *",
            min_value=0.0,
            value=float(default_quantity),
        )

    with col2:
        unit = st.text_input(
            "Unit",
            value=default_unit,
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

    st.markdown("### Route and Transport")

    col1, col2 = st.columns(2)

    with col1:
        origin_country = st.text_input(
            "Origin country *",
            value=default_origin_country,
        )

        origin_location = st.text_input(
            "Origin location or port *",
            value=default_origin_location,
        )

        transport_mode = st.selectbox(
            "Transport mode",
            TRANSPORT_MODES,
            index=(
                TRANSPORT_MODES.index(
                    default_transport_mode
                )
                if default_transport_mode
                in TRANSPORT_MODES
                else 0
            ),
        )

        incoterm = st.selectbox(
            "Incoterm",
            INCOTERMS,
            index=(
                INCOTERMS.index(default_incoterm)
                if default_incoterm in INCOTERMS
                else 0
            ),
        )

    with col2:
        destination_country = st.text_input(
            "Destination country *",
            value=default_destination_country,
        )

        destination_location = st.text_input(
            "Destination location or port *",
            value=default_destination_location,
        )

        service_type = st.selectbox(
            "Service type",
            SERVICE_TYPES,
            index=(
                SERVICE_TYPES.index(
                    default_service_type
                )
                if default_service_type
                in SERVICE_TYPES
                else 0
            ),
        )

        container_type = st.selectbox(
            "Container or cargo type",
            CONTAINER_TYPES,
            index=(
                CONTAINER_TYPES.index(
                    default_container_type
                )
                if default_container_type
                in CONTAINER_TYPES
                else 0
            ),
        )

    st.markdown("### Transport References")

    col1, col2, col3 = st.columns(3)

    with col1:
        booking_number = st.text_input(
            "Booking number"
        )

        bill_of_lading_number = st.text_input(
            "Bill of lading number"
        )

    with col2:
        airway_bill_number = st.text_input(
            "Airway bill number"
        )

        tracking_number = st.text_input(
            "Tracking number"
        )

    with col3:
        container_number = st.text_input(
            "Container number"
        )

        seal_number = st.text_input(
            "Seal number"
        )

    col1, col2 = st.columns(2)

    with col1:
        carrier_name = st.text_input(
            "Carrier or shipping line"
        )

        vessel_name = st.text_input(
            "Vessel name"
        )

    with col2:
        voyage_number = st.text_input(
            "Voyage number"
        )

        flight_number = st.text_input(
            "Flight number"
        )

    st.markdown("### Dates")

    col1, col2, col3 = st.columns(3)

    with col1:
        planned_pickup_date = st.date_input(
            "Planned pickup",
            value=date.today(),
        )

        etd = st.date_input(
            "Estimated departure",
            value=date.today() + timedelta(days=3),
        )

    with col2:
        eta = st.date_input(
            "Estimated arrival",
            value=date.today() + timedelta(days=30),
        )

        record_actual_pickup = st.checkbox(
            "Record actual pickup"
        )

        actual_pickup_date = (
            st.date_input(
                "Actual pickup date",
                value=date.today(),
            )
            if record_actual_pickup
            else None
        )

    with col3:
        record_actual_departure = st.checkbox(
            "Record actual departure"
        )

        actual_departure_date = (
            st.date_input(
                "Actual departure date",
                value=date.today(),
            )
            if record_actual_departure
            else None
        )

        record_actual_arrival = st.checkbox(
            "Record actual arrival"
        )

        actual_arrival_date = (
            st.date_input(
                "Actual arrival date",
                value=date.today(),
            )
            if record_actual_arrival
            else None
        )

    st.markdown("### Customs, Biosecurity and Documents")

    col1, col2 = st.columns(2)

    with col1:
        customs_status = st.selectbox(
            "Customs status",
            CLEARANCE_STATUSES,
        )

        biosecurity_status = st.selectbox(
            "Biosecurity status",
            CLEARANCE_STATUSES,
            index=CLEARANCE_STATUSES.index(
                "Not Required"
            ),
        )

    with col2:
        inspection_status = st.selectbox(
            "Inspection status",
            CLEARANCE_STATUSES,
            index=CLEARANCE_STATUSES.index(
                "Not Required"
            ),
        )

        document_status = st.selectbox(
            "Document status",
            DOCUMENT_STATUSES,
        )

    col1, col2 = st.columns(2)

    with col1:
        commercial_invoice_received = st.checkbox(
            "Commercial invoice received"
        )

        packing_list_received = st.checkbox(
            "Packing list received"
        )

        bill_of_lading_received = st.checkbox(
            "Bill of lading or airway bill received"
        )

        certificate_of_origin_received = st.checkbox(
            "Certificate of origin received"
        )

    with col2:
        phytosanitary_received = st.checkbox(
            "Phytosanitary certificate received"
        )

        fumigation_received = st.checkbox(
            "Fumigation certificate received"
        )

        insurance_certificate_received = st.checkbox(
            "Insurance certificate received"
        )

        import_permit_received = st.checkbox(
            "Import permit received"
        )

    other_documents = st.text_area(
        "Other documents"
    )

    st.markdown("### Shipment Costs")

    currency = st.selectbox(
        "Currency",
        CURRENCIES,
        index=(
            CURRENCIES.index(default_currency)
            if default_currency in CURRENCIES
            else 0
        ),
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        goods_value = st.number_input(
            "Goods value",
            min_value=0.0,
            value=float(default_goods_value),
        )

        freight_cost = st.number_input(
            "Freight cost",
            min_value=0.0,
            value=float(default_freight),
        )

        insurance_cost = st.number_input(
            "Insurance cost",
            min_value=0.0,
            value=float(default_insurance),
        )

    with col2:
        customs_cost = st.number_input(
            "Customs and broker cost",
            min_value=0.0,
            value=float(default_customs),
        )

        biosecurity_cost = st.number_input(
            "Biosecurity cost",
            min_value=0.0,
            value=float(default_biosecurity),
        )

        port_cost = st.number_input(
            "Port and terminal cost",
            min_value=0.0,
            value=float(default_port),
        )

    with col3:
        local_delivery_cost = st.number_input(
            "Local delivery cost",
            min_value=0.0,
            value=float(default_delivery),
        )

        storage_cost = st.number_input(
            "Storage cost",
            min_value=0.0,
            value=float(default_storage),
        )

        other_costs = st.number_input(
            "Other shipment costs",
            min_value=0.0,
        )

    total_cost = (
        freight_cost
        + insurance_cost
        + customs_cost
        + biosecurity_cost
        + port_cost
        + local_delivery_cost
        + storage_cost
        + other_costs
    )

    col1, col2 = st.columns(2)

    col1.metric(
        "Shipment Costs",
        f"{currency} {total_cost:,.2f}",
    )

    col2.metric(
        "Total Shipment Value",
        f"{currency} {goods_value + total_cost:,.2f}",
    )

    st.markdown("### Risk and Management")

    col1, col2 = st.columns(2)

    with col1:
        risk_level = st.selectbox(
            "Risk level",
            RISK_LEVELS,
            index=1,
        )

    with col2:
        priority = st.selectbox(
            "Priority",
            PRIORITIES,
            index=1,
        )

    delay_reason = st.text_area(
        "Delay reason or current issue"
    )

    notes = st.text_area(
        "Internal notes"
    )

    if not st.button(
        "Create Shipment",
        type="primary",
        width="stretch",
    ):
        return

    required_values = {
        "Supplier name": supplier_name,
        "Product name": product_name,
        "Cargo description": cargo_description,
        "Origin country": origin_country,
        "Origin location": origin_location,
        "Destination country": destination_country,
        "Destination location": destination_location,
    }

    for field_name, field_value in required_values.items():
        if not field_value.strip():
            st.warning(f"{field_name} is required.")
            return

    if quantity <= 0:
        st.warning(
            "Quantity must be greater than zero."
        )
        return

    shipment_id = create_shipment(
        Shipment(
            shipment_number=shipment_number,
            shipment_type=shipment_type,
            status=status,
            rfq_id=selected_rfq.id
            if selected_rfq
            else None,
            supplier_quote_id=(
                selected_supplier_quote.id
                if selected_supplier_quote
                else None
            ),
            logistics_quote_id=(
                selected_logistics_quote.id
                if selected_logistics_quote
                else None
            ),
            warehouse_quote_id=(
                selected_warehouse.id
                if selected_warehouse
                else None
            ),
            supplier_name=supplier_name,
            logistics_provider=logistics_provider,
            warehouse_name=warehouse_name,
            product_name=product_name,
            cargo_description=cargo_description,
            quantity=quantity,
            unit=unit,
            gross_weight_kg=gross_weight_kg,
            volume_cbm=volume_cbm,
            origin_country=origin_country,
            origin_location=origin_location,
            destination_country=destination_country,
            destination_location=destination_location,
            transport_mode=transport_mode,
            service_type=service_type,
            incoterm=incoterm,
            container_type=container_type,
            booking_number=booking_number,
            bill_of_lading_number=(
                bill_of_lading_number
            ),
            airway_bill_number=airway_bill_number,
            container_number=container_number,
            seal_number=seal_number,
            tracking_number=tracking_number,
            carrier_name=carrier_name,
            vessel_name=vessel_name,
            voyage_number=voyage_number,
            flight_number=flight_number,
            planned_pickup_date=(
                planned_pickup_date.isoformat()
            ),
            actual_pickup_date=(
                actual_pickup_date.isoformat()
                if actual_pickup_date
                else None
            ),
            etd=etd.isoformat(),
            actual_departure_date=(
                actual_departure_date.isoformat()
                if actual_departure_date
                else None
            ),
            eta=eta.isoformat(),
            actual_arrival_date=(
                actual_arrival_date.isoformat()
                if actual_arrival_date
                else None
            ),
            customs_clearance_date=None,
            warehouse_delivery_date=None,
            customs_status=customs_status,
            biosecurity_status=biosecurity_status,
            inspection_status=inspection_status,
            document_status=document_status,
            commercial_invoice_received=(
                commercial_invoice_received
            ),
            packing_list_received=(
                packing_list_received
            ),
            bill_of_lading_received=(
                bill_of_lading_received
            ),
            certificate_of_origin_received=(
                certificate_of_origin_received
            ),
            phytosanitary_received=(
                phytosanitary_received
            ),
            fumigation_received=fumigation_received,
            insurance_certificate_received=(
                insurance_certificate_received
            ),
            import_permit_received=(
                import_permit_received
            ),
            other_documents=other_documents,
            currency=currency,
            goods_value=goods_value,
            freight_cost=freight_cost,
            insurance_cost=insurance_cost,
            customs_cost=customs_cost,
            biosecurity_cost=biosecurity_cost,
            port_cost=port_cost,
            local_delivery_cost=local_delivery_cost,
            storage_cost=storage_cost,
            other_costs=other_costs,
            delay_reason=delay_reason,
            risk_level=risk_level,
            priority=priority,
            inventory_received=False,
            notes=notes,
        )
    )

    st.success(
        f"Shipment created successfully. ID: {shipment_id}"
    )

    st.info(
        f"Shipment number: {shipment_number}"
    )


def show_register() -> None:
    st.subheader("Shipment Register")

    search = st.text_input(
        "Search shipments",
        placeholder=(
            "Search shipment, supplier, product, booking, "
            "container, tracking, origin or destination"
        ),
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        status_filter = st.selectbox(
            "Status",
            ["All"] + SHIPMENT_STATUSES,
        )

    with col2:
        transport_filter = st.selectbox(
            "Transport mode",
            ["All"] + TRANSPORT_MODES,
        )

    with col3:
        risk_filter = st.selectbox(
            "Risk level",
            ["All"] + RISK_LEVELS,
        )

    shipments = get_shipments(
        search=search,
        status=status_filter,
        transport_mode=transport_filter,
        risk_level=risk_filter,
    )

    st.caption(
        f"{len(shipments)} shipment(s) found"
    )

    if not shipments:
        st.info("No shipments found.")
        return

    st.dataframe(
        [
            {
                "ID": shipment.id,
                "Shipment": shipment.shipment_number,
                "Product": shipment.product_name,
                "Supplier": shipment.supplier_name,
                "Logistics Provider": (
                    shipment.logistics_provider or ""
                ),
                "Mode": shipment.transport_mode,
                "Origin": shipment.origin_location,
                "Destination": (
                    shipment.destination_location
                ),
                "Quantity": (
                    f"{shipment.quantity:g} "
                    f"{shipment.unit}"
                ),
                "ETD": shipment.etd or "",
                "ETA": shipment.eta or "",
                "Status": shipment.status,
                "Customs": shipment.customs_status,
                "Documents": (
                    f"{shipment.document_completion_percent}%"
                ),
                "Currency": shipment.currency,
                "Total Value": shipment.total_value,
                "Risk": shipment.risk_level,
                "Priority": shipment.priority,
                "Overdue": (
                    "Yes"
                    if shipment.is_overdue
                    else "No"
                ),
            }
            for shipment in shipments
        ],
        hide_index=True,
        width="stretch",
    )

    selected_shipment = st.selectbox(
        "Select shipment",
        shipments,
        format_func=lambda shipment: (
            f"{shipment.shipment_number} — "
            f"{shipment.product_name} — "
            f"{shipment.status}"
        ),
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Status",
        selected_shipment.status,
    )

    col2.metric(
        "Document Completion",
        f"{selected_shipment.document_completion_percent}%",
    )

    col3.metric(
        "Total Value",
        f"{selected_shipment.currency} "
        f"{selected_shipment.total_value:,.2f}",
    )

    col4.metric(
        "Overdue",
        "Yes"
        if selected_shipment.is_overdue
        else "No",
    )

    with st.expander(
        "Shipment details and references"
    ):
        st.write(
            f"**Supplier:** "
            f"{selected_shipment.supplier_name}"
        )

        st.write(
            f"**Logistics provider:** "
            f"{selected_shipment.logistics_provider or 'Not recorded'}"
        )

        st.write(
            f"**Warehouse:** "
            f"{selected_shipment.warehouse_name or 'Not recorded'}"
        )

        st.write(
            f"**Route:** "
            f"{selected_shipment.origin_location}, "
            f"{selected_shipment.origin_country} → "
            f"{selected_shipment.destination_location}, "
            f"{selected_shipment.destination_country}"
        )

        st.write(
            f"**Booking:** "
            f"{selected_shipment.booking_number or 'Not recorded'}"
        )

        st.write(
            f"**Bill of lading:** "
            f"{selected_shipment.bill_of_lading_number or 'Not recorded'}"
        )

        st.write(
            f"**Container:** "
            f"{selected_shipment.container_number or 'Not recorded'}"
        )

        st.write(
            f"**Tracking:** "
            f"{selected_shipment.tracking_number or 'Not recorded'}"
        )

    st.markdown("---")
    st.subheader("Update Shipment Control Status")

    with st.form(
        f"shipment_update_{selected_shipment.id}"
    ):
        col1, col2 = st.columns(2)

        with col1:
            updated_status = st.selectbox(
                "Shipment status",
                SHIPMENT_STATUSES,
                index=SHIPMENT_STATUSES.index(
                    selected_shipment.status
                ),
            )

            updated_customs = st.selectbox(
                "Customs status",
                CLEARANCE_STATUSES,
                index=(
                    CLEARANCE_STATUSES.index(
                        selected_shipment.customs_status
                    )
                    if selected_shipment.customs_status
                    in CLEARANCE_STATUSES
                    else 0
                ),
            )

            updated_biosecurity = st.selectbox(
                "Biosecurity status",
                CLEARANCE_STATUSES,
                index=(
                    CLEARANCE_STATUSES.index(
                        selected_shipment.biosecurity_status
                    )
                    if selected_shipment.biosecurity_status
                    in CLEARANCE_STATUSES
                    else 0
                ),
            )

        with col2:
            updated_inspection = st.selectbox(
                "Inspection status",
                CLEARANCE_STATUSES,
                index=(
                    CLEARANCE_STATUSES.index(
                        selected_shipment.inspection_status
                    )
                    if selected_shipment.inspection_status
                    in CLEARANCE_STATUSES
                    else 0
                ),
            )

            updated_document_status = st.selectbox(
                "Document status",
                DOCUMENT_STATUSES,
                index=(
                    DOCUMENT_STATUSES.index(
                        selected_shipment.document_status
                    )
                    if selected_shipment.document_status
                    in DOCUMENT_STATUSES
                    else 0
                ),
            )

            updated_risk = st.selectbox(
                "Risk level",
                RISK_LEVELS,
                index=RISK_LEVELS.index(
                    selected_shipment.risk_level
                ),
            )

        updated_priority = st.selectbox(
            "Priority",
            PRIORITIES,
            index=PRIORITIES.index(
                selected_shipment.priority
            ),
        )

        updated_delay_reason = st.text_area(
            "Delay reason",
            value=(
                selected_shipment.delay_reason
                or ""
            ),
        )

        inventory_received = st.checkbox(
            "Inventory has been received",
            value=selected_shipment.inventory_received,
            help=(
                "Use this after the warehouse has confirmed "
                "physical receipt and inventory has been updated."
            ),
        )

        updated_notes = st.text_area(
            "Notes",
            value=selected_shipment.notes or "",
        )

        update_submitted = st.form_submit_button(
            "Update Shipment",
            type="primary",
            width="stretch",
        )

    if update_submitted:
        update_shipment_status(
            selected_shipment.id,
            status=updated_status,
            customs_status=updated_customs,
            biosecurity_status=(
                updated_biosecurity
            ),
            inspection_status=(
                updated_inspection
            ),
            document_status=(
                updated_document_status
            ),
            risk_level=updated_risk,
            priority=updated_priority,
            delay_reason=updated_delay_reason,
            inventory_received=inventory_received,
            notes=updated_notes,
        )

        st.success(
            "Shipment updated successfully."
        )

        st.rerun()

    confirm_delete = st.checkbox(
        f"Confirm deletion of "
        f"{selected_shipment.shipment_number}"
    )

    if st.button(
        "Delete Shipment",
        disabled=not confirm_delete,
    ):
        delete_shipment(
            selected_shipment.id
        )

        st.success("Shipment deleted.")

        st.rerun()


def show_milestones() -> None:
    st.subheader("Shipment Milestone Timeline")

    shipments = get_shipments()

    if not shipments:
        st.info("Create a shipment first.")
        return

    selected_shipment = st.selectbox(
        "Shipment",
        shipments,
        format_func=lambda shipment: (
            f"{shipment.shipment_number} — "
            f"{shipment.product_name}"
        ),
        key="milestone_shipment",
    )

    milestones = get_shipment_milestones(
        selected_shipment.id
    )

    if milestones:
        st.dataframe(
            [
                {
                    "Date": milestone.milestone_date,
                    "Milestone": milestone.milestone_type,
                    "Status": milestone.status,
                    "Location": milestone.location or "",
                    "Responsible": (
                        milestone.responsible_party or ""
                    ),
                    "Reference": (
                        milestone.reference_number or ""
                    ),
                    "Description": (
                        milestone.description or ""
                    ),
                    "Notes": milestone.notes or "",
                }
                for milestone in milestones
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info(
            "No milestones recorded."
        )

    st.markdown("---")
    st.subheader("Add Shipment Milestone")

    milestone_type = st.selectbox(
        "Milestone type",
        MILESTONE_TYPES,
    )

    milestone_date = st.date_input(
        "Milestone date",
        value=date.today(),
    )

    milestone_status = st.selectbox(
        "Milestone status",
        [
            "Planned",
            "In Progress",
            "Completed",
            "Delayed",
            "Cancelled",
        ],
        index=2,
    )

    col1, col2 = st.columns(2)

    with col1:
        location = st.text_input(
            "Location"
        )

        responsible_party = st.text_input(
            "Responsible party"
        )

    with col2:
        reference_number = st.text_input(
            "Reference number"
        )

        description = st.text_area(
            "Description"
        )

    milestone_notes = st.text_area(
        "Milestone notes"
    )

    if st.button(
        "Add Milestone",
        type="primary",
        width="stretch",
    ):
        milestone_id = create_shipment_milestone(
            ShipmentMilestone(
                shipment_id=selected_shipment.id,
                milestone_type=milestone_type,
                milestone_date=(
                    milestone_date.isoformat()
                ),
                status=milestone_status,
                location=location,
                description=description,
                responsible_party=(
                    responsible_party
                ),
                reference_number=(
                    reference_number
                ),
                notes=milestone_notes,
            )
        )

        st.success(
            f"Milestone added successfully. "
            f"ID: {milestone_id}"
        )

        st.rerun()