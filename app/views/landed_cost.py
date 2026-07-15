import streamlit as st

from models.landed_cost import LandedCost
from services.landed_cost_service import (
    create_landed_cost,
    delete_landed_cost,
    get_landed_costs,
)
from services.rfq_service import get_rfqs
from services.supplier_quote_service import get_supplier_quotes


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
    "Draft",
    "Estimated",
    "Verified",
    "Approved",
    "Rejected",
    "Completed",
]


def calculate_results(
    *,
    quantity: float,
    unit_price_source: float,
    exchange_rate: float,
    freight: float,
    insurance: float,
    origin_charges: float,
    destination_port_charges: float,
    customs_broker_fee: float,
    biosecurity_fee: float,
    inspection_fee: float,
    duty_rate: float,
    gst_rate: float,
    local_transport: float,
    warehouse_cost: float,
    packaging_cost: float,
    bank_fee: float,
    finance_cost: float,
    contingency: float,
    other_costs: float,
    selling_price_per_unit: float,
) -> dict:
    goods_value_source = unit_price_source * quantity
    goods_value_reporting = goods_value_source * exchange_rate

    customs_value = (
        goods_value_reporting
        + freight
        + insurance
    )

    duty_amount = customs_value * (duty_rate / 100)

    gst_base = (
        customs_value
        + duty_amount
    )

    gst_amount = gst_base * (gst_rate / 100)

    total_landed_cost = (
        goods_value_reporting
        + freight
        + insurance
        + origin_charges
        + destination_port_charges
        + customs_broker_fee
        + biosecurity_fee
        + inspection_fee
        + duty_amount
        + gst_amount
        + local_transport
        + warehouse_cost
        + packaging_cost
        + bank_fee
        + finance_cost
        + contingency
        + other_costs
    )

    landed_cost_per_unit = (
        total_landed_cost / quantity
        if quantity > 0
        else 0
    )

    expected_revenue = selling_price_per_unit * quantity
    gross_profit = expected_revenue - total_landed_cost

    gross_margin_percent = (
        (gross_profit / expected_revenue) * 100
        if expected_revenue > 0
        else 0
    )

    roi_percent = (
        (gross_profit / total_landed_cost) * 100
        if total_landed_cost > 0
        else 0
    )

    return {
        "goods_value_source": goods_value_source,
        "goods_value_reporting": goods_value_reporting,
        "duty_amount": duty_amount,
        "gst_amount": gst_amount,
        "total_landed_cost": total_landed_cost,
        "landed_cost_per_unit": landed_cost_per_unit,
        "expected_revenue": expected_revenue,
        "gross_profit": gross_profit,
        "gross_margin_percent": gross_margin_percent,
        "roi_percent": roi_percent,
    }


def show() -> None:
    st.title("💰 Landed Cost & Profit Engine")
    st.caption(
        "Calculate the complete cost of importing products, including "
        "supplier price, exchange rate, freight, customs, biosecurity, "
        "GST, warehousing, local delivery and expected profit."
    )

    calculator_tab, register_tab = st.tabs(
        [
            "🧮 New Calculation",
            "📋 Cost Register",
        ]
    )

    with calculator_tab:
        show_calculator()

    with register_tab:
        show_register()


def show_calculator() -> None:
    rfqs = get_rfqs()
    quotes = get_supplier_quotes()

    st.subheader("Calculation Source")

    source_mode = st.radio(
        "Start from",
        [
            "Supplier Quotation",
            "RFQ",
            "Manual Entry",
        ],
        horizontal=True,
    )

    selected_quote = None
    selected_rfq = None

    if source_mode == "Supplier Quotation":
        if not quotes:
            st.warning(
                "No supplier quotations exist. Use RFQ or Manual Entry."
            )
            return

        selected_quote = st.selectbox(
            "Supplier quotation",
            quotes,
            format_func=lambda quote: (
                f"{quote.supplier_name} — "
                f"{quote.currency} {quote.quoted_total:,.2f}"
            ),
        )

    elif source_mode == "RFQ":
        if not rfqs:
            st.warning("No RFQs exist. Use Manual Entry.")
            return

        selected_rfq = st.selectbox(
            "RFQ",
            rfqs,
            format_func=lambda rfq: (
                f"{rfq.rfq_number} — {rfq.title}"
            ),
        )

    default_product = ""
    default_supplier = ""
    default_currency = "USD"
    default_quantity = 1.0
    default_unit = "unit"
    default_unit_price = 0.0
    default_freight = 0.0
    default_insurance = 0.0
    default_destination = "Melbourne, Australia"
    default_rfq_id = None
    default_quote_id = None

    if selected_quote is not None:
        default_quote_id = selected_quote.id
        default_rfq_id = selected_quote.rfq_id
        default_supplier = selected_quote.supplier_name
        default_currency = selected_quote.currency
        default_quantity = selected_quote.quantity
        default_unit_price = selected_quote.unit_price
        default_freight = selected_quote.freight_cost
        default_insurance = selected_quote.insurance_cost

        matching_rfqs = [
            rfq
            for rfq in rfqs
            if rfq.id == selected_quote.rfq_id
        ]

        if matching_rfqs:
            matched_rfq = matching_rfqs[0]
            default_product = matched_rfq.product_name
            default_unit = matched_rfq.unit
            default_destination = (
                matched_rfq.destination
                or default_destination
            )

    elif selected_rfq is not None:
        default_rfq_id = selected_rfq.id
        default_product = selected_rfq.product_name
        default_supplier = selected_rfq.supplier_name or ""
        default_unit = selected_rfq.unit
        default_destination = (
            selected_rfq.destination
            or default_destination
        )

        try:
            default_quantity = float(selected_rfq.quantity)
        except ValueError:
            default_quantity = 1.0

    st.markdown("---")
    st.subheader("Shipment and Product")

    calculation_name = st.text_input(
        "Calculation name *",
        value=(
            f"{default_product} landed-cost calculation"
            if default_product
            else ""
        ),
    )

    product_name = st.text_input(
        "Product name *",
        value=default_product,
    )

    supplier_name = st.text_input(
        "Supplier",
        value=default_supplier,
    )

    origin_country = st.text_input(
        "Origin country",
    )

    destination = st.text_input(
        "Destination",
        value=default_destination,
    )

    col1, col2 = st.columns(2)

    with col1:
        quantity = st.number_input(
            "Quantity *",
            min_value=0.0,
            value=float(default_quantity),
            step=1.0,
        )

    with col2:
        unit = st.text_input(
            "Unit",
            value=default_unit,
        )

    st.markdown("---")
    st.subheader("Currency and Supplier Price")

    col1, col2, col3 = st.columns(3)

    with col1:
        source_currency = st.selectbox(
            "Supplier currency",
            CURRENCIES,
            index=(
                CURRENCIES.index(default_currency)
                if default_currency in CURRENCIES
                else 1
            ),
        )

    with col2:
        reporting_currency = st.selectbox(
            "Reporting currency",
            CURRENCIES,
            index=0,
        )

    with col3:
        exchange_rate = st.number_input(
            "Exchange rate",
            min_value=0.000001,
            value=1.0,
            step=0.01,
            help=(
                "Enter how many reporting-currency units equal "
                "one source-currency unit."
            ),
        )

    unit_price_source = st.number_input(
        f"Unit price in {source_currency}",
        min_value=0.0,
        value=float(default_unit_price),
        step=1.0,
    )

    st.markdown("---")
    st.subheader("International and Import Costs")

    col1, col2, col3 = st.columns(3)

    with col1:
        international_freight = st.number_input(
            "International freight",
            min_value=0.0,
            value=float(default_freight),
        )

        origin_charges = st.number_input(
            "Origin charges",
            min_value=0.0,
        )

        customs_broker_fee = st.number_input(
            "Customs broker fee",
            min_value=0.0,
        )

        inspection_fee = st.number_input(
            "Inspection fee",
            min_value=0.0,
        )

    with col2:
        international_insurance = st.number_input(
            "International insurance",
            min_value=0.0,
            value=float(default_insurance),
        )

        destination_port_charges = st.number_input(
            "Destination port charges",
            min_value=0.0,
        )

        biosecurity_fee = st.number_input(
            "Biosecurity and quarantine",
            min_value=0.0,
        )

        local_transport = st.number_input(
            "Local transport",
            min_value=0.0,
        )

    with col3:
        warehouse_cost = st.number_input(
            "Warehouse and storage",
            min_value=0.0,
        )

        packaging_cost = st.number_input(
            "Local packaging or relabelling",
            min_value=0.0,
        )

        bank_fee = st.number_input(
            "Bank and transfer fees",
            min_value=0.0,
        )

        finance_cost = st.number_input(
            "Finance cost",
            min_value=0.0,
        )

    col1, col2 = st.columns(2)

    with col1:
        contingency = st.number_input(
            "Contingency",
            min_value=0.0,
        )

    with col2:
        other_costs = st.number_input(
            "Other costs",
            min_value=0.0,
        )

    st.markdown("---")
    st.subheader("Duty and GST")

    col1, col2 = st.columns(2)

    with col1:
        duty_rate = st.number_input(
            "Duty rate %",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
        )

    with col2:
        gst_rate = st.number_input(
            "GST rate %",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
        )

    st.markdown("---")
    st.subheader("Sales and Profit")

    selling_price_per_unit = st.number_input(
        f"Expected selling price per {unit}",
        min_value=0.0,
    )

    results = calculate_results(
        quantity=quantity,
        unit_price_source=unit_price_source,
        exchange_rate=exchange_rate,
        freight=international_freight,
        insurance=international_insurance,
        origin_charges=origin_charges,
        destination_port_charges=destination_port_charges,
        customs_broker_fee=customs_broker_fee,
        biosecurity_fee=biosecurity_fee,
        inspection_fee=inspection_fee,
        duty_rate=duty_rate,
        gst_rate=gst_rate,
        local_transport=local_transport,
        warehouse_cost=warehouse_cost,
        packaging_cost=packaging_cost,
        bank_fee=bank_fee,
        finance_cost=finance_cost,
        contingency=contingency,
        other_costs=other_costs,
        selling_price_per_unit=selling_price_per_unit,
    )

    st.markdown("---")
    st.subheader("Calculation Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Goods Value",
        f"{reporting_currency} "
        f"{results['goods_value_reporting']:,.2f}",
    )

    col2.metric(
        "Total Landed Cost",
        f"{reporting_currency} "
        f"{results['total_landed_cost']:,.2f}",
    )

    col3.metric(
        "Cost Per Unit",
        f"{reporting_currency} "
        f"{results['landed_cost_per_unit']:,.2f}",
    )

    col4.metric(
        "Gross Profit",
        f"{reporting_currency} "
        f"{results['gross_profit']:,.2f}",
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Duty",
        f"{reporting_currency} "
        f"{results['duty_amount']:,.2f}",
    )

    col2.metric(
        "GST",
        f"{reporting_currency} "
        f"{results['gst_amount']:,.2f}",
    )

    col3.metric(
        "Gross Margin",
        f"{results['gross_margin_percent']:.2f}%",
    )

    col4.metric(
        "ROI",
        f"{results['roi_percent']:.2f}%",
    )

    status = st.selectbox(
        "Calculation status",
        STATUSES,
    )

    notes = st.text_area(
        "Assumptions and notes",
        placeholder=(
            "Record quotation dates, exchange-rate source, estimated "
            "charges, exclusions, broker advice and unresolved risks."
        ),
    )

    if st.button(
        "Save Landed Cost Calculation",
        type="primary",
        width="stretch",
    ):
        if not calculation_name.strip():
            st.warning("Calculation name is required.")
            return

        if not product_name.strip():
            st.warning("Product name is required.")
            return

        if quantity <= 0:
            st.warning("Quantity must be greater than zero.")
            return

        record_id = create_landed_cost(
            LandedCost(
                name=calculation_name,
                rfq_id=default_rfq_id,
                supplier_quote_id=default_quote_id,
                product_name=product_name,
                supplier_name=supplier_name,
                origin_country=origin_country,
                destination=destination,
                source_currency=source_currency,
                reporting_currency=reporting_currency,
                exchange_rate=exchange_rate,
                quantity=quantity,
                unit=unit,
                unit_price_source=unit_price_source,
                goods_value_source=results["goods_value_source"],
                goods_value_reporting=results[
                    "goods_value_reporting"
                ],
                international_freight=international_freight,
                international_insurance=international_insurance,
                origin_charges=origin_charges,
                destination_port_charges=(
                    destination_port_charges
                ),
                customs_broker_fee=customs_broker_fee,
                biosecurity_fee=biosecurity_fee,
                inspection_fee=inspection_fee,
                duty_rate=duty_rate,
                duty_amount=results["duty_amount"],
                gst_rate=gst_rate,
                gst_amount=results["gst_amount"],
                local_transport=local_transport,
                warehouse_cost=warehouse_cost,
                packaging_cost=packaging_cost,
                bank_fee=bank_fee,
                finance_cost=finance_cost,
                contingency=contingency,
                other_costs=other_costs,
                total_landed_cost=results[
                    "total_landed_cost"
                ],
                landed_cost_per_unit=results[
                    "landed_cost_per_unit"
                ],
                selling_price_per_unit=selling_price_per_unit,
                expected_revenue=results["expected_revenue"],
                gross_profit=results["gross_profit"],
                gross_margin_percent=results[
                    "gross_margin_percent"
                ],
                roi_percent=results["roi_percent"],
                status=status,
                notes=notes,
            )
        )

        st.success(
            f"Landed-cost calculation saved. ID: {record_id}"
        )


def show_register() -> None:
    st.subheader("Landed Cost Register")

    search = st.text_input(
        "Search calculations",
        placeholder=(
            "Search name, product, supplier, origin or destination"
        ),
    )

    status = st.selectbox(
        "Filter by status",
        ["All"] + STATUSES,
    )

    records = get_landed_costs(
        search=search,
        status=status,
    )

    st.caption(f"{len(records)} calculation(s) found")

    if not records:
        st.info("No landed-cost calculations found.")
        return

    st.dataframe(
        [
            {
                "ID": record.id,
                "Name": record.name,
                "Product": record.product_name,
                "Supplier": record.supplier_name or "",
                "Origin": record.origin_country or "",
                "Destination": record.destination,
                "Quantity": f"{record.quantity:g} {record.unit}",
                "Currency": record.reporting_currency,
                "Landed Cost": record.total_landed_cost,
                "Cost Per Unit": record.landed_cost_per_unit,
                "Revenue": record.expected_revenue,
                "Gross Profit": record.gross_profit,
                "Margin %": record.gross_margin_percent,
                "ROI %": record.roi_percent,
                "Status": record.status,
            }
            for record in records
        ],
        hide_index=True,
        width="stretch",
    )

    selected_record = st.selectbox(
        "Select calculation",
        records,
        format_func=lambda record: (
            f"{record.name} — "
            f"{record.reporting_currency} "
            f"{record.total_landed_cost:,.2f}"
        ),
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Landed Cost",
        f"{selected_record.reporting_currency} "
        f"{selected_record.total_landed_cost:,.2f}",
    )

    col2.metric(
        "Cost Per Unit",
        f"{selected_record.reporting_currency} "
        f"{selected_record.landed_cost_per_unit:,.2f}",
    )

    col3.metric(
        "Gross Profit",
        f"{selected_record.reporting_currency} "
        f"{selected_record.gross_profit:,.2f}",
    )

    col4.metric(
        "ROI",
        f"{selected_record.roi_percent:.2f}%",
    )

    confirm_delete = st.checkbox(
        f"Confirm deletion of {selected_record.name}"
    )

    if st.button(
        "Delete Calculation",
        disabled=not confirm_delete,
    ):
        delete_landed_cost(selected_record.id)
        st.success("Calculation deleted.")
        st.rerun()