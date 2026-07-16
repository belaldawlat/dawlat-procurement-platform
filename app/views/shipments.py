from datetime import date, timedelta

import pandas as pd
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
    add_shipment_tracking_event,
    get_enterprise_shipment,
    get_shipment_analytics,
    get_shipment_documents,
    get_shipment_milestones,
    get_shipment_timeline,
    get_shipment_tracking_events,
    get_shipments,
    update_shipment_document,
    update_shipment_status,
    update_shipment_timeline_stage,
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
    _apply_enterprise_styles()

    st.title("🚢 Global Shipment Command Centre")
    st.caption(
        "Control international shipments, customs, documents, tracking, "
        "costs, delivery risk and operational performance from one workspace."
    )

    dashboard_tab, create_tab, register_tab, timeline_tab, documents_tab, tracking_tab, analytics_tab = st.tabs(
        [
            "📊 Dashboard",
            "➕ Create Shipment",
            "📋 Register",
            "🧭 Timeline",
            "📄 Documents",
            "📍 Tracking",
            "📈 Analytics",
        ]
    )

    with dashboard_tab:
        show_overview()

    with create_tab:
        show_create_shipment()

    with register_tab:
        show_register()

    with timeline_tab:
        show_milestones()

    with documents_tab:
        show_documents()

    with tracking_tab:
        show_tracking()

    with analytics_tab:
        show_analytics()


def show_overview() -> None:
    shipments = get_shipments()

    active = [
        item for item in shipments
        if item.status not in {"Delivered", "Completed", "Cancelled"}
    ]
    in_transit = [
        item for item in shipments
        if item.status in {"Picked Up", "In Transit", "Arrived at Port"}
    ]
    delivered = [
        item for item in shipments
        if item.status in {"Delivered", "Completed"}
    ]
    delayed = [
        item for item in shipments
        if item.status == "Delayed" or item.delay_reason or item.is_overdue
    ]
    customs = [
        item for item in shipments
        if item.status in {
            "Customs Clearance",
            "Biosecurity Hold",
            "Inspection Hold",
        }
        or item.customs_status in {
            "Documents Submitted",
            "Under Review",
            "Additional Information Required",
            "Inspection Required",
            "On Hold",
        }
    ]
    total_value = sum(item.total_value for item in shipments)

    st.subheader("Executive Shipment Dashboard")
    cols = st.columns(6)
    metrics = [
        ("Active Shipments", len(active)),
        ("In Transit", len(in_transit)),
        ("Delivered", len(delivered)),
        ("Delayed / Overdue", len(delayed)),
        ("Customs Clearance", len(customs)),
        ("Total Shipment Value", f"AUD {total_value:,.0f}"),
    ]
    for column, (label, value) in zip(cols, metrics):
        column.metric(label, value)

    if not shipments:
        st.info("No shipments exist yet.")
        st.markdown("### ST25 Premium Rice Test Shipment")
        st.write(
            "Create a realistic Vietnam-to-Melbourne shipment to test "
            "the dashboard, register, timeline, documents, tracking and analytics."
        )
        if st.button(
            "Create ST25 Test Shipment",
            type="primary",
            use_container_width=True,
            key="dashboard_create_st25",
        ):
            shipment_id, shipment_number = _create_st25_test_shipment()
            st.success(
                f"ST25 test shipment created: {shipment_number} "
                f"(ID {shipment_id})."
            )
            st.rerun()
        return

    alert_col, action_col = st.columns([2, 1])
    with alert_col:
        if delayed:
            st.error(
                f"{len(delayed)} shipment(s) require delay or ETA attention."
            )
        elif customs:
            st.warning(
                f"{len(customs)} shipment(s) are in customs, biosecurity "
                "or inspection workflow."
            )
        else:
            st.success("No critical shipment exceptions detected.")

    with action_col:
        if not any(
            "ST25" in item.product_name.upper()
            and "VIETNAM" in item.origin_country.upper()
            for item in shipments
        ):
            if st.button(
                "Create ST25 Test Shipment",
                use_container_width=True,
                key="dashboard_create_st25_existing",
            ):
                shipment_id, shipment_number = _create_st25_test_shipment()
                st.success(
                    f"Created {shipment_number} (ID {shipment_id})."
                )
                st.rerun()

    st.markdown("### Active Shipment Pipeline")
    pipeline = active if active else shipments[:10]
    st.dataframe(
        [
            {
                "Shipment": item.shipment_number,
                "Product": item.product_name,
                "Supplier": item.supplier_name,
                "Route": f"{item.origin_location} → {item.destination_location}",
                "Mode": item.transport_mode,
                "ETD": item.etd or "",
                "ETA": item.eta or "",
                "Status": item.status,
                "Customs": item.customs_status,
                "Documents": f"{item.document_completion_percent}%",
                "Risk": item.risk_level,
                "Priority": item.priority,
                "Overdue": "Yes" if item.is_overdue else "No",
                "Value": item.total_value,
            }
            for item in pipeline
        ],
        hide_index=True,
        use_container_width=True,
    )

    left, right = st.columns(2)

    with left:
        st.markdown("### Upcoming Arrivals")
        arrivals = sorted(
            [
                item for item in active
                if item.eta
            ],
            key=lambda item: item.eta or "9999-12-31",
        )[:8]
        if arrivals:
            st.dataframe(
                [
                    {
                        "Shipment": item.shipment_number,
                        "ETA": item.eta,
                        "Destination": item.destination_location,
                        "Status": item.status,
                        "Priority": item.priority,
                    }
                    for item in arrivals
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No upcoming arrivals recorded.")

    with right:
        st.markdown("### Operational Exceptions")
        exceptions = delayed + [
            item for item in customs if item not in delayed
        ]
        if exceptions:
            st.dataframe(
                [
                    {
                        "Shipment": item.shipment_number,
                        "Issue": item.delay_reason
                        or item.customs_status
                        or item.status,
                        "ETA": item.eta or "",
                        "Risk": item.risk_level,
                        "Priority": item.priority,
                    }
                    for item in exceptions[:8]
                ],
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.success("No operational exceptions.")


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
def show_documents() -> None:
    st.subheader("Shipment Document Control")
    shipment = _select_shipment("documents_shipment")
    if shipment is None:
        return

    documents = get_shipment_documents(shipment.id)
    if not documents:
        st.info("No document checklist is available.")
        return

    required = [item for item in documents if item.get("is_required")]
    received = [item for item in required if item.get("is_received")]
    verified = [
        item for item in required
        if item.get("verification_status") == "Verified"
    ]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Required", len(required))
    col2.metric("Received", len(received))
    col3.metric("Verified", len(verified))
    completion = (
        round(len(verified) / len(required) * 100)
        if required else 100
    )
    col4.metric("Verified Completion", f"{completion}%")

    st.dataframe(
        [
            {
                "ID": item["id"],
                "Document": item["document_type"],
                "Number": item.get("document_number") or "",
                "Received": "Yes" if item.get("is_received") else "No",
                "Verification": item.get("verification_status") or "",
                "Issuer": item.get("issuing_authority") or "",
                "Issued": item.get("issued_date") or "",
                "Expiry": item.get("expiry_date") or "",
                "File": item.get("file_name") or "",
                "Notes": item.get("notes") or "",
            }
            for item in documents
        ],
        hide_index=True,
        use_container_width=True,
    )

    selected = st.selectbox(
        "Select document to update",
        documents,
        format_func=lambda item: item["document_type"],
        key="document_record",
    )

    with st.form(f"document_update_{selected['id']}"):
        col1, col2 = st.columns(2)
        with col1:
            document_number = st.text_input(
                "Document number",
                value=selected.get("document_number") or "",
            )
            issuing_authority = st.text_input(
                "Issuing authority",
                value=selected.get("issuing_authority") or "",
            )
            issued_date = st.text_input(
                "Issued date (YYYY-MM-DD)",
                value=selected.get("issued_date") or "",
            )
        with col2:
            expiry_date = st.text_input(
                "Expiry date (YYYY-MM-DD)",
                value=selected.get("expiry_date") or "",
            )
            verification_status = st.selectbox(
                "Verification status",
                [
                    "Pending",
                    "Verified",
                    "Rejected",
                    "Expired",
                    "Not Required",
                ],
                index=_safe_index(
                    [
                        "Pending",
                        "Verified",
                        "Rejected",
                        "Expired",
                        "Not Required",
                    ],
                    selected.get("verification_status"),
                ),
            )
            is_received = st.checkbox(
                "Document received",
                value=bool(selected.get("is_received")),
            )

        notes = st.text_area(
            "Document notes",
            value=selected.get("notes") or "",
        )

        submitted = st.form_submit_button(
            "Update Document",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        update_shipment_document(
            selected["id"],
            {
                "document_number": document_number.strip() or None,
                "issuing_authority": issuing_authority.strip() or None,
                "issued_date": issued_date.strip() or None,
                "expiry_date": expiry_date.strip() or None,
                "verification_status": verification_status,
                "is_received": int(is_received),
                "notes": notes.strip() or None,
            },
        )
        st.success("Document updated.")
        st.rerun()


def show_tracking() -> None:
    st.subheader("Shipment Tracking Centre")
    shipment = _select_shipment("tracking_shipment")
    if shipment is None:
        return

    enterprise = get_enterprise_shipment(shipment.id) or {}
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", shipment.status)
    col2.metric(
        "Current Location",
        enterprise.get("current_location")
        or shipment.origin_location,
    )
    col3.metric("Vessel", shipment.vessel_name or "Not assigned")
    col4.metric("ETA", shipment.eta or "Not recorded")

    events = get_shipment_tracking_events(shipment.id)
    if events:
        st.dataframe(
            [
                {
                    "Time": item.get("event_time") or "",
                    "Event": item.get("event_name") or "",
                    "Location": item.get("location_name") or "",
                    "Country": item.get("country") or "",
                    "Source": item.get("source_type") or "",
                    "Vessel": item.get("vessel_name") or "",
                    "Voyage": item.get("voyage_number") or "",
                    "Exception": "Yes" if item.get("is_exception") else "No",
                    "Description": item.get("event_description") or "",
                }
                for item in events
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No tracking events recorded.")

    st.markdown("### Add Tracking Event")
    with st.form(f"tracking_event_{shipment.id}"):
        col1, col2 = st.columns(2)
        with col1:
            event_name = st.text_input("Event name *")
            event_time = st.text_input(
                "Event time",
                value=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            location_name = st.text_input("Location")
            country = st.text_input("Country")
        with col2:
            source_type = st.selectbox(
                "Source",
                [
                    "Manual",
                    "Shipping Line",
                    "Carrier API",
                    "Port",
                    "Customs",
                    "Warehouse",
                    "System",
                ],
            )
            vessel_name = st.text_input(
                "Vessel",
                value=shipment.vessel_name or "",
            )
            voyage_number = st.text_input(
                "Voyage",
                value=shipment.voyage_number or "",
            )
            is_exception = st.checkbox("Exception or delay event")

        description = st.text_area("Description")
        exception_reason = st.text_area("Exception reason")
        submitted = st.form_submit_button(
            "Add Tracking Event",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not event_name.strip():
            st.warning("Event name is required.")
            return

        add_shipment_tracking_event(
            shipment.id,
            {
                "event_code": event_name.upper().replace(" ", "_"),
                "event_name": event_name.strip(),
                "event_description": description.strip() or None,
                "location_name": location_name.strip() or None,
                "city": None,
                "country": country.strip() or None,
                "port_code": None,
                "latitude": None,
                "longitude": None,
                "event_time": event_time.strip(),
                "source_type": source_type,
                "source_reference": shipment.tracking_number,
                "external_tracking_id": None,
                "vessel_name": vessel_name.strip() or None,
                "voyage_number": voyage_number.strip() or None,
                "is_exception": int(is_exception),
                "exception_reason": exception_reason.strip() or None,
                "recorded_by": None,
            },
        )
        st.success("Tracking event added.")
        st.rerun()


def show_analytics() -> None:
    st.subheader("Shipment Analytics")
    analytics = get_shipment_analytics()
    summary = analytics.get("summary") or {}

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(
        "Average Transit Time",
        f"{summary.get('average_transit_days') or 0} days",
    )
    col2.metric(
        "Delayed Shipments",
        int(summary.get("delayed_shipments") or 0),
    )
    col3.metric(
        "Average Delay",
        f"{summary.get('average_delay_days') or 0} days",
    )
    col4.metric(
        "Total Shipment Cost",
        f"AUD {float(summary.get('total_shipment_cost') or 0):,.0f}",
    )
    col5.metric(
        "Total Shipment Value",
        f"AUD {float(summary.get('total_shipment_value') or 0):,.0f}",
    )

    country_rows = analytics.get("country_performance") or []
    line_rows = analytics.get("shipping_line_performance") or []
    cost_rows = analytics.get("cost_analysis") or []

    left, right = st.columns(2)
    with left:
        st.markdown("### Country Performance")
        if country_rows:
            country_df = pd.DataFrame(country_rows)
            st.dataframe(
                country_df,
                hide_index=True,
                use_container_width=True,
            )
            chart = country_df.set_index("origin_country")[
                ["shipment_count"]
            ]
            st.bar_chart(chart)
        else:
            st.info("No country performance data.")

    with right:
        st.markdown("### Shipping Line Performance")
        if line_rows:
            line_df = pd.DataFrame(line_rows)
            st.dataframe(
                line_df,
                hide_index=True,
                use_container_width=True,
            )
            chart = line_df.set_index("shipping_line")[
                ["on_time_percentage"]
            ]
            st.bar_chart(chart)
        else:
            st.info("No shipping-line performance data.")

    st.markdown("### Shipment Cost Analysis")
    if cost_rows:
        st.dataframe(
            pd.DataFrame(cost_rows),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No shipment cost data.")

    shipments = get_shipments()
    delayed = [
        item for item in shipments
        if item.status == "Delayed" or item.delay_reason or item.is_overdue
    ]
    st.markdown("### Operational Intelligence")
    if delayed:
        st.warning(
            f"{len(delayed)} shipment(s) require attention. Prioritise "
            "high-risk and urgent records, confirm revised ETA, customs "
            "requirements and customer delivery impact."
        )
    elif shipments:
        st.success(
            "Current shipment portfolio has no recorded delay exceptions."
        )
    else:
        st.info("Create shipments to generate operational intelligence.")


def _select_shipment(key: str) -> Shipment | None:
    shipments = get_shipments()
    if not shipments:
        st.info("Create a shipment first.")
        return None

    return st.selectbox(
        "Shipment",
        shipments,
        format_func=lambda item: (
            f"{item.shipment_number} — {item.product_name} — {item.status}"
        ),
        key=key,
    )


def _create_st25_test_shipment() -> tuple[int, str]:
    existing = [
        item for item in get_shipments(search="ST25")
        if item.origin_country.lower() == "vietnam"
        and "melbourne" in item.destination_location.lower()
    ]
    if existing:
        return int(existing[0].id), existing[0].shipment_number

    shipment_number = generate_shipment_number()
    today = date.today()
    etd = today + timedelta(days=7)
    eta = etd + timedelta(days=24)

    shipment = Shipment(
        shipment_number=shipment_number,
        shipment_type="Import Shipment",
        status="Booked",
        rfq_id=None,
        supplier_quote_id=None,
        logistics_quote_id=None,
        warehouse_quote_id=None,
        supplier_name="Mekong Delta Premium Foods JSC",
        logistics_provider="Dawlat Global Freight Partner",
        warehouse_name="Melbourne Food-Grade 3PL Warehouse",
        product_name="ST25 Premium Fragrant Rice",
        cargo_description=(
            "Vietnamese ST25 premium fragrant rice packed in "
            "25 kg food-grade PP export bags."
        ),
        quantity=20.0,
        unit="metric tonnes",
        gross_weight_kg=20400.0,
        volume_cbm=32.0,
        origin_country="Vietnam",
        origin_location="Cat Lai Port, Ho Chi Minh City",
        destination_country="Australia",
        destination_location="Port of Melbourne, Victoria",
        transport_mode="Sea Freight",
        service_type="Port to Door",
        incoterm="CIF",
        container_type="20ft General Purpose",
        booking_number="DG-ST25-BOOK-001",
        bill_of_lading_number="BL-VNSGN-AUMEL-26001",
        airway_bill_number=None,
        container_number="MSCU1234567",
        seal_number="DG260715",
        tracking_number="DG-ST25-2026-001",
        carrier_name="MSC",
        vessel_name="MSC Melbourne Star",
        voyage_number="MS2607S",
        flight_number=None,
        planned_pickup_date=(today + timedelta(days=3)).isoformat(),
        actual_pickup_date=None,
        etd=etd.isoformat(),
        actual_departure_date=None,
        eta=eta.isoformat(),
        actual_arrival_date=None,
        customs_clearance_date=None,
        warehouse_delivery_date=None,
        customs_status="Not Started",
        biosecurity_status="Documents Submitted",
        inspection_status="Not Required",
        document_status="Partially Complete",
        commercial_invoice_received=True,
        packing_list_received=True,
        bill_of_lading_received=False,
        certificate_of_origin_received=True,
        phytosanitary_received=True,
        fumigation_received=True,
        insurance_certificate_received=True,
        import_permit_received=False,
        other_documents=(
            "Rice quality certificate and laboratory test report pending review."
        ),
        currency="AUD",
        goods_value=32500.0,
        freight_cost=3850.0,
        insurance_cost=420.0,
        customs_cost=650.0,
        biosecurity_cost=780.0,
        port_cost=1450.0,
        local_delivery_cost=890.0,
        storage_cost=600.0,
        other_costs=350.0,
        delay_reason=None,
        risk_level="Medium",
        priority="High",
        inventory_received=False,
        notes=(
            "Enterprise Phase 9 test shipment from Ho Chi Minh City "
            "to Melbourne. Use this record to test every shipment screen."
        ),
    )
    shipment_id = create_shipment(shipment)

    test_milestones = [
        (
            "Booking Confirmed",
            today.isoformat(),
            "Completed",
            "Ho Chi Minh City",
            "Booking confirmed with shipping line.",
        ),
        (
            "Cargo Ready",
            (today + timedelta(days=2)).isoformat(),
            "Planned",
            "Supplier Factory, Vietnam",
            "ST25 rice packed and ready for container loading.",
        ),
        (
            "Container Loaded",
            (today + timedelta(days=5)).isoformat(),
            "Planned",
            "Cat Lai Port",
            "Container loading and seal verification.",
        ),
        (
            "Departed Origin",
            etd.isoformat(),
            "Planned",
            "Cat Lai Port",
            "Vessel departure for Melbourne.",
        ),
        (
            "Arrived Destination",
            eta.isoformat(),
            "Planned",
            "Port of Melbourne",
            "Planned arrival and import clearance.",
        ),
    ]

    for milestone_type, milestone_date, status, location, description in test_milestones:
        create_shipment_milestone(
            ShipmentMilestone(
                shipment_id=shipment_id,
                milestone_type=milestone_type,
                milestone_date=milestone_date,
                status=status,
                location=location,
                description=description,
                responsible_party="Dawlat Global Operations",
                reference_number=shipment_number,
                notes=None,
            )
        )

    return shipment_id, shipment_number


def _safe_index(options: list[str], value: str | None) -> int:
    return options.index(value) if value in options else 0


def _apply_enterprise_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }
        [data-testid="stMetric"] {
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 14px;
            padding: 14px 16px;
            background: rgba(128, 128, 128, 0.04);
        }
        [data-testid="stMetricLabel"] {
            font-weight: 600;
        }
        div[data-baseweb="tab-list"] {
            gap: 0.35rem;
        }
        div[data-baseweb="tab"] {
            border-radius: 10px 10px 0 0;
            padding-left: 0.9rem;
            padding-right: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )