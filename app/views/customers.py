import streamlit as st

from models.customer import Customer
from services.customer_service import (
    create_customer,
    delete_customer,
    get_customers,
    update_customer,
)


CUSTOMER_TYPES = [
    "Importer",
    "Wholesaler",
    "Distributor",
    "Retail Chain",
    "Supermarket",
    "Grocery Store",
    "Restaurant",
    "Hotel",
    "Hospital",
    "Pharmacy",
    "Automotive Dealer",
    "Auto Parts Store",
    "Cricket Shop",
    "Sports Store",
    "Government Buyer",
    "NGO",
    "School",
    "University",
    "Food Processor",
    "Manufacturer",
    "Online Retailer",
    "Amazon Seller",
    "eBay Seller",
    "Corporate Buyer",
    "Procurement Department",
    "Sales Agent",
    "Reseller",
    "Other",
]

LEAD_STATUSES = [
    "Prospect",
    "Researching",
    "Contacted",
    "Qualified",
    "Quotation Requested",
    "Quotation Sent",
    "Negotiating",
    "Customer",
    "Inactive",
    "Rejected",
]

CREDIT_STATUSES = [
    "Not Assessed",
    "Prepaid Only",
    "Low Risk",
    "Medium Risk",
    "High Risk",
    "Credit Approved",
    "Credit Suspended",
]


def show() -> None:
    st.title("👥 Customer CRM")
    st.caption(
        "Manage importers, wholesalers, distributors, retailers, "
        "institutions, and other potential buyers."
    )

    add_tab, directory_tab = st.tabs(
        [
            "➕ Add Customer",
            "📋 Customer Directory",
        ]
    )

    with add_tab:
        show_add_customer()

    with directory_tab:
        show_customer_directory()


def show_add_customer() -> None:
    st.subheader("Add New Customer")

    with st.form("add_customer_form", clear_on_submit=True):
        company_name = st.text_input("Company name *")
        customer_type = st.selectbox("Customer type", CUSTOMER_TYPES)
        country = st.text_input("Country *")
        city = st.text_input("City")
        contact_name = st.text_input("Contact person")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        whatsapp = st.text_input("WhatsApp")
        website = st.text_input("Website")

        products_of_interest = st.text_area(
            "Products of interest",
            placeholder=(
                "Example: ST25 rice, Basmati rice, cricket equipment, "
                "automotive parts, medical supplies."
            ),
        )

        estimated_demand = st.text_input(
            "Estimated demand",
            placeholder="Example: 20 tonnes per month",
        )

        preferred_packaging = st.text_input(
            "Preferred packaging",
            placeholder="Example: 5 kg retail bags and 25 kg wholesale bags",
        )

        payment_terms = st.text_input(
            "Preferred payment terms",
        )

        credit_status = st.selectbox(
            "Credit status",
            CREDIT_STATUSES,
        )

        lead_status = st.selectbox(
            "Lead status",
            LEAD_STATUSES,
        )

        source = st.text_input(
            "Lead source",
            placeholder=(
                "Google Maps, company website, trade directory, "
                "referral, exhibition, or internal research"
            ),
        )

        notes = st.text_area("Notes")

        submitted = st.form_submit_button(
            "Save Customer",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if not company_name.strip() or not country.strip():
        st.warning("Company name and country are required.")
        return

    customer_id = create_customer(
        Customer(
            company_name=company_name,
            customer_type=customer_type,
            country=country,
            city=city,
            contact_name=contact_name,
            email=email,
            phone=phone,
            whatsapp=whatsapp,
            website=website,
            products_of_interest=products_of_interest,
            estimated_demand=estimated_demand,
            preferred_packaging=preferred_packaging,
            payment_terms=payment_terms,
            credit_status=credit_status,
            lead_status=lead_status,
            source=source,
            notes=notes,
        )
    )

    st.success(
        f"Customer saved successfully. Customer ID: {customer_id}"
    )


def show_customer_directory() -> None:
    st.subheader("Customer Directory")

    search = st.text_input(
        "Search customers",
        placeholder=(
            "Search by company, contact, email, country, city, or product"
        ),
    )

    col1, col2 = st.columns(2)

    with col1:
        customer_type = st.selectbox(
            "Filter by customer type",
            ["All"] + CUSTOMER_TYPES,
        )

    with col2:
        lead_status = st.selectbox(
            "Filter by lead status",
            ["All"] + LEAD_STATUSES,
        )

    customers = get_customers(
        search=search,
        customer_type=customer_type,
        lead_status=lead_status,
    )

    st.caption(f"{len(customers)} customer(s) found")

    if not customers:
        st.info("No customers found.")
        return

    table_data = [
        {
            "ID": customer.id,
            "Company": customer.company_name,
            "Type": customer.customer_type,
            "Country": customer.country,
            "City": customer.city or "",
            "Contact": customer.contact_name or "",
            "Email": customer.email or "",
            "Demand": customer.estimated_demand or "",
            "Lead Status": customer.lead_status,
            "Credit": customer.credit_status,
        }
        for customer in customers
    ]

    st.dataframe(
        table_data,
        hide_index=True,
        width="stretch",
    )

    st.markdown("---")
    st.subheader("Edit or Delete Customer")

    selected_customer = st.selectbox(
        "Select customer",
        options=customers,
        format_func=lambda customer: (
            f"{customer.company_name} — {customer.customer_type}"
        ),
    )

    with st.form(f"edit_customer_{selected_customer.id}"):
        company_name = st.text_input(
            "Company name",
            value=selected_customer.company_name,
        )

        customer_type = st.selectbox(
            "Customer type",
            CUSTOMER_TYPES,
            index=(
                CUSTOMER_TYPES.index(selected_customer.customer_type)
                if selected_customer.customer_type in CUSTOMER_TYPES
                else len(CUSTOMER_TYPES) - 1
            ),
        )

        country = st.text_input(
            "Country",
            value=selected_customer.country,
        )

        city = st.text_input(
            "City",
            value=selected_customer.city or "",
        )

        contact_name = st.text_input(
            "Contact person",
            value=selected_customer.contact_name or "",
        )

        email = st.text_input(
            "Email",
            value=selected_customer.email or "",
        )

        phone = st.text_input(
            "Phone",
            value=selected_customer.phone or "",
        )

        whatsapp = st.text_input(
            "WhatsApp",
            value=selected_customer.whatsapp or "",
        )

        website = st.text_input(
            "Website",
            value=selected_customer.website or "",
        )

        products_of_interest = st.text_area(
            "Products of interest",
            value=selected_customer.products_of_interest or "",
        )

        estimated_demand = st.text_input(
            "Estimated demand",
            value=selected_customer.estimated_demand or "",
        )

        preferred_packaging = st.text_input(
            "Preferred packaging",
            value=selected_customer.preferred_packaging or "",
        )

        payment_terms = st.text_input(
            "Payment terms",
            value=selected_customer.payment_terms or "",
        )

        credit_status = st.selectbox(
            "Credit status",
            CREDIT_STATUSES,
            index=(
                CREDIT_STATUSES.index(selected_customer.credit_status)
                if selected_customer.credit_status in CREDIT_STATUSES
                else 0
            ),
        )

        lead_status = st.selectbox(
            "Lead status",
            LEAD_STATUSES,
            index=(
                LEAD_STATUSES.index(selected_customer.lead_status)
                if selected_customer.lead_status in LEAD_STATUSES
                else 0
            ),
        )

        source = st.text_input(
            "Lead source",
            value=selected_customer.source or "",
        )

        notes = st.text_area(
            "Notes",
            value=selected_customer.notes or "",
        )

        update_submitted = st.form_submit_button(
            "Update Customer",
            type="primary",
            width="stretch",
        )

    if update_submitted:
        if not company_name.strip() or not country.strip():
            st.warning("Company name and country are required.")
        else:
            update_customer(
                Customer(
                    id=selected_customer.id,
                    company_name=company_name,
                    customer_type=customer_type,
                    country=country,
                    city=city,
                    contact_name=contact_name,
                    email=email,
                    phone=phone,
                    whatsapp=whatsapp,
                    website=website,
                    products_of_interest=products_of_interest,
                    estimated_demand=estimated_demand,
                    preferred_packaging=preferred_packaging,
                    payment_terms=payment_terms,
                    credit_status=credit_status,
                    lead_status=lead_status,
                    source=source,
                    notes=notes,
                )
            )

            st.success("Customer updated successfully.")
            st.rerun()

    confirm_delete = st.checkbox(
        f"Confirm deletion of {selected_customer.company_name}"
    )

    if st.button(
        "Delete Customer",
        disabled=not confirm_delete,
    ):
        delete_customer(selected_customer.id)
        st.success("Customer deleted successfully.")
        st.rerun()