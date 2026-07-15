from datetime import date, timedelta

import streamlit as st

from models.supplier_quote import SupplierQuote
from services.partner_service import get_partners
from services.rfq_service import get_rfqs
from services.supplier_quote_service import (
    create_supplier_quote,
    delete_supplier_quote,
    get_supplier_quotes,
)


CURRENCIES = [
    "USD",
    "AUD",
    "EUR",
    "GBP",
    "CNY",
    "VND",
    "PKR",
    "INR",
]

INCOTERMS = [
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

QUOTE_STATUSES = [
    "Received",
    "Under Review",
    "Clarification Required",
    "Shortlisted",
    "Rejected",
    "Selected",
    "Expired",
]


def show() -> None:
    st.title("📄 Supplier Quotations")
    st.caption(
        "Record supplier offers against RFQs and capture price, "
        "freight, lead time, compliance, quality and commercial terms."
    )

    add_tab, register_tab = st.tabs(
        [
            "➕ Record Quotation",
            "📋 Quotation Register",
        ]
    )

    with add_tab:
        show_add_quote()

    with register_tab:
        show_quote_register()


def show_add_quote() -> None:
    rfqs = get_rfqs()
    suppliers = get_partners(partner_type="Supplier")

    if not rfqs:
        st.warning("Create at least one RFQ first.")
        return

    with st.form(
        "add_supplier_quote_form",
        clear_on_submit=True,
    ):
        selected_rfq = st.selectbox(
            "RFQ *",
            rfqs,
            format_func=lambda rfq: (
                f"{rfq.rfq_number} — {rfq.title}"
            ),
        )

        supplier_mode = st.radio(
            "Supplier source",
            [
                "Existing Supplier",
                "Manual Supplier",
            ],
            horizontal=True,
        )

        selected_supplier = None
        manual_supplier_name = ""

        if supplier_mode == "Existing Supplier":
            if suppliers:
                selected_supplier = st.selectbox(
                    "Supplier",
                    suppliers,
                    format_func=lambda supplier: (
                        f"{supplier.company_name} — {supplier.country}"
                    ),
                )
            else:
                st.info(
                    "No supplier records exist. Select Manual Supplier."
                )

        else:
            manual_supplier_name = st.text_input(
                "Supplier company name *"
            )

        quote_reference = st.text_input(
            "Supplier quotation reference"
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            currency = st.selectbox(
                "Currency",
                CURRENCIES,
            )

        with col2:
            unit_price = st.number_input(
                "Unit price *",
                min_value=0.0,
                step=1.0,
            )

        with col3:
            quantity = st.number_input(
                "Quoted quantity *",
                min_value=0.0,
                step=1.0,
            )

        st.markdown("#### Additional Costs")

        col1, col2, col3 = st.columns(3)

        with col1:
            freight_cost = st.number_input(
                "Freight cost",
                min_value=0.0,
                step=1.0,
            )

        with col2:
            insurance_cost = st.number_input(
                "Insurance cost",
                min_value=0.0,
                step=1.0,
            )

        with col3:
            other_costs = st.number_input(
                "Other costs",
                min_value=0.0,
                step=1.0,
            )

        col1, col2 = st.columns(2)

        with col1:
            incoterm = st.selectbox(
                "Incoterm",
                INCOTERMS,
            )

            moq = st.text_input(
                "MOQ",
                placeholder="Example: One 20-foot container",
            )

        with col2:
            lead_time_days = st.number_input(
                "Lead time in days",
                min_value=0,
                step=1,
            )

            quotation_valid_until = st.date_input(
                "Quotation valid until",
                value=date.today() + timedelta(days=30),
            )

        payment_terms = st.text_area("Payment terms")
        packaging = st.text_area("Packaging and branding")
        certificates = st.text_area("Certificates available")

        sample_available = st.checkbox("Sample available")

        sample_cost = st.number_input(
            "Sample cost",
            min_value=0.0,
            step=1.0,
        )

        st.markdown("#### Internal Evaluation")

        quality_score = st.slider(
            "Quality score",
            0,
            100,
            50,
        )

        compliance_score = st.slider(
            "Compliance score",
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

        reliability_score = st.slider(
            "Reliability score",
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
            QUOTE_STATUSES,
        )

        notes = st.text_area("Internal notes")

        submitted = st.form_submit_button(
            "Save Supplier Quotation",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    supplier_id = None

    if supplier_mode == "Existing Supplier":
        if selected_supplier is None:
            st.warning("Select an existing supplier.")
            return

        supplier_id = selected_supplier.id
        supplier_name = selected_supplier.company_name

    else:
        supplier_name = manual_supplier_name.strip()

        if not supplier_name:
            st.warning("Enter the supplier company name.")
            return

    if unit_price <= 0 or quantity <= 0:
        st.warning(
            "Unit price and quoted quantity must be greater than zero."
        )
        return

    quote = SupplierQuote(
        rfq_id=selected_rfq.id,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        quote_reference=quote_reference,
        currency=currency,
        unit_price=unit_price,
        quantity=quantity,
        freight_cost=freight_cost,
        insurance_cost=insurance_cost,
        other_costs=other_costs,
        incoterm=incoterm,
        moq=moq,
        lead_time_days=int(lead_time_days),
        payment_terms=payment_terms,
        packaging=packaging,
        certificates=certificates,
        sample_available=sample_available,
        sample_cost=sample_cost,
        quotation_valid_until=(
            quotation_valid_until.isoformat()
        ),
        quality_score=quality_score,
        compliance_score=compliance_score,
        communication_score=communication_score,
        reliability_score=reliability_score,
        risk_score=risk_score,
        status=status,
        notes=notes,
    )

    quote_id = create_supplier_quote(quote)

    st.success(
        f"Supplier quotation saved successfully. ID: {quote_id}"
    )

    st.info(
        f"Quoted total: {currency} {quote.quoted_total:,.2f}"
    )


def show_quote_register() -> None:
    st.subheader("Supplier Quotation Register")

    search = st.text_input(
        "Search quotations",
        placeholder=(
            "Search supplier, reference, Incoterm, payment terms or notes"
        ),
    )

    status = st.selectbox(
        "Filter by status",
        ["All"] + QUOTE_STATUSES,
    )

    quotes = get_supplier_quotes(
        search=search,
        status=status,
    )

    st.caption(f"{len(quotes)} quotation(s) found")

    if not quotes:
        st.info("No supplier quotations found.")
        return

    st.dataframe(
        [
            {
                "ID": quote.id,
                "RFQ ID": quote.rfq_id,
                "Supplier": quote.supplier_name,
                "Reference": quote.quote_reference or "",
                "Currency": quote.currency,
                "Unit Price": quote.unit_price,
                "Quantity": quote.quantity,
                "Goods Total": quote.goods_total,
                "Quoted Total": quote.quoted_total,
                "Incoterm": quote.incoterm,
                "Lead Time": quote.lead_time_days,
                "Status": quote.status,
            }
            for quote in quotes
        ],
        hide_index=True,
        width="stretch",
    )

    selected_quote = st.selectbox(
        "Select quotation",
        quotes,
        format_func=lambda quote: (
            f"{quote.supplier_name} — "
            f"{quote.currency} {quote.quoted_total:,.2f}"
        ),
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Goods Total",
        f"{selected_quote.currency} "
        f"{selected_quote.goods_total:,.2f}",
    )

    col2.metric(
        "Quoted Total",
        f"{selected_quote.currency} "
        f"{selected_quote.quoted_total:,.2f}",
    )

    col3.metric(
        "Lead Time",
        f"{selected_quote.lead_time_days} days",
    )

    col4.metric(
        "Risk",
        f"{selected_quote.risk_score}/100",
    )

    confirm_delete = st.checkbox(
        f"Confirm deletion of quotation from "
        f"{selected_quote.supplier_name}"
    )

    if st.button(
        "Delete Quotation",
        disabled=not confirm_delete,
    ):
        delete_supplier_quote(selected_quote.id)
        st.success("Supplier quotation deleted.")
        st.rerun()