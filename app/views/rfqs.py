from datetime import date, timedelta

import streamlit as st

from components.entity_selector import entity_selector
from models.market_opportunity import MarketOpportunity
from models.partner import Partner
from models.product import Product
from models.rfq import RFQ
from services.duplicate_service import find_duplicates
from services.market_opportunity_service import (
    create_opportunity,
    get_opportunities,
)
from services.partner_service import (
    create_partner,
    get_partners,
)
from services.product_service import (
    create_product,
    get_products,
)
from services.rfq_service import (
    create_rfq,
    delete_rfq,
    generate_rfq_number,
    get_rfq_supplier_names,
    get_rfqs,
    update_rfq,
)
from utils.validation import (
    is_valid_email,
    is_valid_website,
    required,
)


RFQ_STATUSES = [
    "Draft",
    "Ready",
    "Sent",
    "Partially Responded",
    "Fully Responded",
    "Under Review",
    "Awarded",
    "Closed",
    "Cancelled",
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

UNITS = [
    "kg",
    "tonne",
    "bag",
    "carton",
    "box",
    "piece",
    "pallet",
    "container",
    "shipment",
]

PRODUCT_CATEGORIES = [
    "Rice",
    "Food & Beverage",
    "Cricket Equipment",
    "Automotive Parts",
    "Medical Supplies",
    "Packaging",
    "Agriculture",
    "Construction",
    "Technology",
    "Other",
]

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


def show() -> None:
    st.title("📨 RFQ Management")
    st.caption(
        "Create and manage requests for quotations using existing "
        "records or create products, suppliers and opportunities inline."
    )

    create_tab, register_tab = st.tabs(
        [
            "➕ Create RFQ",
            "📋 RFQ Register",
        ]
    )

    with create_tab:
        show_create_rfq()

    with register_tab:
        show_rfq_register()


def show_create_rfq() -> None:
    st.subheader("Create Request for Quotation")

    products = get_products(status="Active")
    suppliers = get_partners(partner_type="Supplier")
    opportunities = get_opportunities()

    rfq_number = generate_rfq_number()

    st.text_input(
        "RFQ number",
        value=rfq_number,
        disabled=True,
    )

    title = st.text_input(
        "RFQ title *",
        placeholder="Example: RFQ for Vietnamese ST25 premium rice",
    )

    st.markdown("### Product")

    product_selection = entity_selector(
        label="Product",
        records=products,
        format_func=lambda product: (
            f"{product.name} — {product.sku}"
        ),
        key="rfq_product",
        allow_new=True,
        allow_none=False,
    )

    new_product_data = None

    if product_selection.is_new:
        with st.container(border=True):
            st.markdown("#### Create New Product")

            new_product_name = st.text_input(
                "Product name *",
                key="new_rfq_product_name",
            )

            new_product_category = st.selectbox(
                "Category",
                PRODUCT_CATEGORIES,
                key="new_rfq_product_category",
            )

            new_product_sku = st.text_input(
                "SKU *",
                key="new_rfq_product_sku",
            )

            new_product_unit = st.selectbox(
                "Default unit",
                UNITS,
                key="new_rfq_product_unit",
            )

            new_product_origin = st.text_input(
                "Country of origin",
                key="new_rfq_product_origin",
            )

            new_product_description = st.text_area(
                "Product description",
                key="new_rfq_product_description",
            )

            new_product_packaging = st.text_area(
                "Default packaging",
                key="new_rfq_product_packaging",
            )

            new_product_certificates = st.text_area(
                "Required certificates",
                key="new_rfq_product_certificates",
            )

            save_new_product = st.checkbox(
                "Save this product to the Product Catalogue",
                value=True,
                key="save_new_rfq_product",
            )

            new_product_data = {
                "name": new_product_name,
                "category": new_product_category,
                "sku": new_product_sku,
                "unit": new_product_unit,
                "origin": new_product_origin,
                "description": new_product_description,
                "packaging": new_product_packaging,
                "certificates": new_product_certificates,
                "save": save_new_product,
            }

    st.markdown("### Market Opportunity")

    opportunity_selection = entity_selector(
        label="Market opportunity",
        records=opportunities,
        format_func=lambda opportunity: opportunity.title,
        key="rfq_opportunity",
        allow_new=True,
        allow_none=True,
        none_label="No Opportunity",
    )

    new_opportunity_data = None

    if opportunity_selection.is_new:
        with st.container(border=True):
            st.markdown("#### Create New Market Opportunity")

            opportunity_title = st.text_input(
                "Opportunity title *",
                key="new_rfq_opportunity_title",
            )

            opportunity_buyer = st.text_input(
                "Buyer or company",
                key="new_rfq_opportunity_buyer",
            )

            opportunity_industry = st.text_input(
                "Industry *",
                key="new_rfq_opportunity_industry",
            )

            opportunity_country = st.text_input(
                "Country *",
                value="Australia",
                key="new_rfq_opportunity_country",
            )

            opportunity_city = st.text_input(
                "City",
                key="new_rfq_opportunity_city",
            )

            opportunity_type = st.selectbox(
                "Opportunity type",
                OPPORTUNITY_TYPES,
                key="new_rfq_opportunity_type",
            )

            opportunity_urgency = st.selectbox(
                "Urgency",
                [
                    "Low",
                    "Medium",
                    "High",
                    "Critical",
                ],
                index=1,
                key="new_rfq_opportunity_urgency",
            )

            save_new_opportunity = st.checkbox(
                "Save to Market Intelligence",
                value=True,
                key="save_new_rfq_opportunity",
            )

            new_opportunity_data = {
                "title": opportunity_title,
                "buyer": opportunity_buyer,
                "industry": opportunity_industry,
                "country": opportunity_country,
                "city": opportunity_city,
                "type": opportunity_type,
                "urgency": opportunity_urgency,
                "save": save_new_opportunity,
            }

    st.markdown("### Supplier")

    supplier_selection = entity_selector(
        label="Supplier",
        records=suppliers,
        format_func=lambda supplier: (
            f"{supplier.company_name} — {supplier.country}"
        ),
        key="rfq_supplier",
        allow_new=True,
        allow_none=True,
        none_label="Open RFQ",
    )

    new_supplier_data = None

    if supplier_selection.is_new:
        with st.container(border=True):
            st.markdown("#### Create New Supplier")

            supplier_company = st.text_input(
                "Company name *",
                key="new_rfq_supplier_company",
            )

            supplier_country = st.text_input(
                "Country *",
                key="new_rfq_supplier_country",
            )

            supplier_city = st.text_input(
                "City",
                key="new_rfq_supplier_city",
            )

            supplier_contact = st.text_input(
                "Contact person",
                key="new_rfq_supplier_contact",
            )

            supplier_email = st.text_input(
                "Email",
                key="new_rfq_supplier_email",
            )

            supplier_phone = st.text_input(
                "Phone",
                key="new_rfq_supplier_phone",
            )

            supplier_website = st.text_input(
                "Website",
                key="new_rfq_supplier_website",
            )

            save_new_supplier = st.checkbox(
                "Save to Global Partners",
                value=True,
                key="save_new_rfq_supplier",
            )

            new_supplier_data = {
                "company": supplier_company,
                "country": supplier_country,
                "city": supplier_city,
                "contact": supplier_contact,
                "email": supplier_email,
                "phone": supplier_phone,
                "website": supplier_website,
                "save": save_new_supplier,
            }

    st.markdown("### RFQ Requirements")

    col1, col2 = st.columns(2)

    with col1:
        quantity = st.text_input(
            "Required quantity *",
            placeholder="Example: 20",
        )

    with col2:
        unit = st.selectbox(
            "Unit",
            UNITS,
        )

    specifications = st.text_area(
        "Product specifications",
        height=150,
    )

    packaging_requirements = st.text_area(
        "Packaging and branding requirements",
    )

    certificate_requirements = st.text_area(
        "Certificates and compliance requirements",
    )

    destination = st.text_input(
        "Destination",
        value="Melbourne, Australia",
    )

    preferred_incoterm = st.selectbox(
        "Preferred Incoterm",
        INCOTERMS,
    )

    sample_requirements = st.text_area(
        "Sample requirements",
    )

    payment_requirements = st.text_area(
        "Payment requirements",
    )

    required_documents = st.text_area(
        "Required quotation and export documents",
        value=(
            "Commercial quotation, product specifications, packing details, "
            "certificate list, production lead time, payment terms, origin "
            "port, quotation validity and company profile."
        ),
    )

    response_deadline = st.date_input(
        "Response deadline",
        value=date.today() + timedelta(days=7),
    )

    status = st.selectbox(
        "RFQ status",
        RFQ_STATUSES,
    )

    notes = st.text_area("Internal notes")

    if not st.button(
        "Create RFQ",
        type="primary",
        width="stretch",
    ):
        return

    try:
        required(title, "RFQ title")
        required(quantity, "Required quantity")

        product_id = None
        product_name = ""
        selected_product_unit = unit

        if product_selection.is_existing:
            selected_product = product_selection.selected_record
            product_id = selected_product.id
            product_name = selected_product.name

        elif new_product_data:
            required(
                new_product_data["name"],
                "Product name",
            )
            required(
                new_product_data["sku"],
                "Product SKU",
            )

            product_name = new_product_data["name"].strip()
            selected_product_unit = new_product_data["unit"]

            duplicates = find_duplicates(
                "product",
                name=product_name,
                sku=new_product_data["sku"],
            )

            if duplicates:
                st.warning(
                    "Possible duplicate product found: "
                    + "; ".join(
                        f"{match.display_name} ({match.reason})"
                        for match in duplicates
                    )
                )
                st.stop()

            if new_product_data["save"]:
                product_id = create_product(
                    Product(
                        name=product_name,
                        category=new_product_data["category"],
                        sku=new_product_data["sku"],
                        unit=new_product_data["unit"],
                        country_of_origin=new_product_data["origin"],
                        description=new_product_data["description"],
                        packaging=new_product_data["packaging"],
                        required_certificates=(
                            new_product_data["certificates"]
                        ),
                        status="Active",
                    )
                )

        supplier_id = None
        supplier_name = None

        if supplier_selection.is_existing:
            selected_supplier = supplier_selection.selected_record
            supplier_id = selected_supplier.id
            supplier_name = selected_supplier.company_name

        elif new_supplier_data:
            required(
                new_supplier_data["company"],
                "Supplier company name",
            )
            required(
                new_supplier_data["country"],
                "Supplier country",
            )

            if not is_valid_email(new_supplier_data["email"]):
                raise ValueError(
                    "Enter a valid supplier email address."
                )

            if not is_valid_website(
                new_supplier_data["website"]
            ):
                raise ValueError(
                    "Website must begin with http://, https:// or www."
                )

            supplier_name = new_supplier_data["company"].strip()

            duplicates = find_duplicates(
                "supplier",
                name=supplier_name,
                email=new_supplier_data["email"],
                phone=new_supplier_data["phone"],
                website=new_supplier_data["website"],
            )

            if duplicates:
                st.warning(
                    "Possible duplicate supplier found: "
                    + "; ".join(
                        f"{match.display_name} ({match.reason})"
                        for match in duplicates
                    )
                )
                st.stop()

            if new_supplier_data["save"]:
                supplier_id = create_partner(
                    Partner(
                        company_name=supplier_name,
                        partner_type="Supplier",
                        country=new_supplier_data["country"],
                        city=new_supplier_data["city"],
                        contact_name=new_supplier_data["contact"],
                        email=new_supplier_data["email"],
                        phone=new_supplier_data["phone"],
                        website=new_supplier_data["website"],
                        products_services=product_name,
                        status="Prospect",
                        verification_status="Researching",
                        rating=0,
                        notes=(
                            f"Created from RFQ {rfq_number}."
                        ),
                    )
                )

        opportunity_id = None

        if opportunity_selection.is_existing:
            selected_opportunity = (
                opportunity_selection.selected_record
            )
            opportunity_id = selected_opportunity.id

        elif new_opportunity_data:
            required(
                new_opportunity_data["title"],
                "Opportunity title",
            )
            required(
                new_opportunity_data["industry"],
                "Opportunity industry",
            )
            required(
                new_opportunity_data["country"],
                "Opportunity country",
            )

            duplicates = find_duplicates(
                "opportunity",
                name=new_opportunity_data["title"],
            )

            if duplicates:
                st.warning(
                    "Possible duplicate opportunity found: "
                    + "; ".join(
                        f"{match.display_name} ({match.reason})"
                        for match in duplicates
                    )
                )
                st.stop()

            if new_opportunity_data["save"]:
                opportunity_id = create_opportunity(
                    MarketOpportunity(
                        title=new_opportunity_data["title"],
                        product=product_name,
                        industry=new_opportunity_data["industry"],
                        country=new_opportunity_data["country"],
                        city=new_opportunity_data["city"],
                        buyer_company=new_opportunity_data["buyer"],
                        opportunity_type=new_opportunity_data["type"],
                        estimated_quantity=(
                            f"{quantity} {selected_product_unit}"
                        ),
                        urgency=new_opportunity_data["urgency"],
                        demand_score=50,
                        competition_score=50,
                        confidence_score=50,
                        status="Research",
                        source=f"Created from RFQ {rfq_number}",
                        notes=specifications,
                    )
                )

        rfq_id = create_rfq(
            RFQ(
                rfq_number=rfq_number,
                title=title,
                product_id=product_id,
                product_name=product_name,
                opportunity_id=opportunity_id,
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                quantity=quantity,
                unit=selected_product_unit,
                specifications=specifications,
                packaging_requirements=packaging_requirements,
                certificate_requirements=certificate_requirements,
                destination=destination,
                preferred_incoterm=preferred_incoterm,
                sample_requirements=sample_requirements,
                payment_requirements=payment_requirements,
                required_documents=required_documents,
                response_deadline=response_deadline.isoformat(),
                status=status,
                notes=notes,
            )
        )

        st.success(
            f"RFQ created successfully. RFQ ID: {rfq_id}"
        )
        st.info(f"RFQ number: {rfq_number}")
        st.rerun()

    except ValueError as error:
        st.error(str(error))


def show_rfq_register() -> None:
    st.subheader("RFQ Register")

    search = st.text_input(
        "Search RFQs",
        placeholder=(
            "Search by RFQ number, title, product, supplier, "
            "destination, or specifications"
        ),
    )

    col1, col2 = st.columns(2)

    with col1:
        status = st.selectbox(
            "Filter by status",
            ["All"] + RFQ_STATUSES,
        )

    with col2:
        supplier_name = st.selectbox(
            "Filter by supplier",
            ["All"] + get_rfq_supplier_names(),
        )

    rfqs = get_rfqs(
        search=search,
        status=status,
        supplier_name=supplier_name,
    )

    st.caption(f"{len(rfqs)} RFQ record(s) found")

    if not rfqs:
        st.info("No RFQs found.")
        return

    st.dataframe(
        [
            {
                "ID": rfq.id,
                "RFQ Number": rfq.rfq_number,
                "Title": rfq.title,
                "Product": rfq.product_name,
                "Supplier": rfq.supplier_name or "Open RFQ",
                "Quantity": f"{rfq.quantity} {rfq.unit}",
                "Incoterm": rfq.preferred_incoterm or "",
                "Destination": rfq.destination or "",
                "Deadline": rfq.response_deadline or "",
                "Status": rfq.status,
            }
            for rfq in rfqs
        ],
        hide_index=True,
        width="stretch",
    )

    selected_rfq = st.selectbox(
        "Select RFQ",
        rfqs,
        format_func=lambda rfq: (
            f"{rfq.rfq_number} — {rfq.title}"
        ),
    )

    st.markdown("---")
    st.subheader("RFQ Details")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("RFQ Number", selected_rfq.rfq_number)
    col2.metric("Status", selected_rfq.status)
    col3.metric(
        "Quantity",
        f"{selected_rfq.quantity} {selected_rfq.unit}",
    )
    col4.metric(
        "Supplier",
        selected_rfq.supplier_name or "Open RFQ",
    )

    with st.expander("Specifications and requirements"):
        st.write(
            selected_rfq.specifications
            or "No specifications recorded."
        )
        st.write(
            selected_rfq.packaging_requirements
            or "No packaging requirements recorded."
        )
        st.write(
            selected_rfq.certificate_requirements
            or "No certificate requirements recorded."
        )
        st.write(
            selected_rfq.sample_requirements
            or "No sample requirements recorded."
        )
        st.write(
            selected_rfq.payment_requirements
            or "No payment requirements recorded."
        )
        st.write(
            selected_rfq.required_documents
            or "No required documents recorded."
        )

    st.info(
        "Full record editing remains available in the current RFQ "
        "register version. The next package will connect supplier "
        "quotations and side-by-side comparison."
    )

    confirm_delete = st.checkbox(
        f"Confirm deletion of {selected_rfq.rfq_number}"
    )

    if st.button(
        "Delete RFQ",
        disabled=not confirm_delete,
    ):
        delete_rfq(selected_rfq.id)
        st.success("RFQ deleted successfully.")
        st.rerun()