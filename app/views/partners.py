import streamlit as st

from models.partner import Partner
from services.partner_service import (
    create_partner,
    delete_partner,
    get_partner_countries,
    get_partner_types,
    get_partners,
    update_partner,
)


PARTNER_TYPES = [
    "Supplier",
    "Manufacturer",
    "Exporter",
    "Distributor",
    "Freight Forwarder",
    "Customs Broker",
    "Port Operator",
    "Shipping Line",
    "Warehouse",
    "3PL Provider",
    "Local Transport Company",
    "Inspection Company",
    "Certification Company",
    "Insurance Provider",
    "Bank",
    "Foreign Exchange Provider",
    "Packaging Supplier",
    "Government Agency",
    "Customer",
    "Sales Agent",
    "Consultant",
]

STATUSES = [
    "Prospect",
    "Contacted",
    "Awaiting Reply",
    "Qualified",
    "Approved",
    "Preferred",
    "On Hold",
    "Inactive",
    "Rejected",
    "Blacklisted",
]

VERIFICATION_STATUSES = [
    "Unverified",
    "Researching",
    "Partially Verified",
    "Verified",
    "Rejected",
]


def show() -> None:
    st.title("🌐 Global Partner Directory")
    st.caption(
        "Manage suppliers, freight forwarders, customs brokers, "
        "warehouses, 3PL providers, shipping lines, and other trade partners."
    )

    add_tab, directory_tab = st.tabs(
        [
            "➕ Add Partner",
            "📋 Partner Directory",
        ]
    )

    with add_tab:
        show_add_partner()

    with directory_tab:
        show_partner_directory()


def show_add_partner() -> None:
    st.subheader("Add New Partner")

    with st.form("add_partner_form", clear_on_submit=True):
        company_name = st.text_input("Company name *")
        partner_type = st.selectbox("Partner type", PARTNER_TYPES)
        country = st.text_input("Country *")
        city = st.text_input("City")
        contact_name = st.text_input("Contact person")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        whatsapp = st.text_input("WhatsApp")
        website = st.text_input("Website")

        products_services = st.text_area(
            "Products or services",
            placeholder=(
                "Examples: ST25 rice, customs clearance, sea freight, "
                "container transport, pallet storage, biosecurity coordination."
            ),
        )

        status = st.selectbox("Status", STATUSES)
        verification_status = st.selectbox(
            "Verification status",
            VERIFICATION_STATUSES,
        )

        rating = st.slider(
            "Internal rating",
            min_value=0,
            max_value=5,
            value=0,
        )

        notes = st.text_area("Notes")

        submitted = st.form_submit_button(
            "Save Partner",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if not company_name.strip() or not country.strip():
        st.warning("Company name and country are required.")
        return

    partner_id = create_partner(
        Partner(
            company_name=company_name,
            partner_type=partner_type,
            country=country,
            city=city,
            contact_name=contact_name,
            email=email,
            phone=phone,
            whatsapp=whatsapp,
            website=website,
            products_services=products_services,
            status=status,
            verification_status=verification_status,
            rating=rating,
            notes=notes,
        )
    )

    st.success(
        f"Partner saved successfully. Partner ID: {partner_id}"
    )


def show_partner_directory() -> None:
    st.subheader("Partner Directory")

    search = st.text_input(
        "Search partners",
        placeholder=(
            "Search by company, contact, email, product, service, "
            "country, or city"
        ),
    )

    available_types = ["All"] + get_partner_types()
    available_countries = ["All"] + get_partner_countries()

    col1, col2 = st.columns(2)

    with col1:
        partner_type = st.selectbox(
            "Filter by partner type",
            available_types,
        )

    with col2:
        country = st.selectbox(
            "Filter by country",
            available_countries,
        )

    partners = get_partners(
        search=search,
        partner_type=partner_type,
        country=country,
    )

    st.caption(f"{len(partners)} partner(s) found")

    if not partners:
        st.info("No partners found.")
        return

    table_data = [
        {
            "ID": partner.id,
            "Company": partner.company_name,
            "Type": partner.partner_type,
            "Country": partner.country,
            "City": partner.city or "",
            "Contact": partner.contact_name or "",
            "Email": partner.email or "",
            "Phone": partner.phone or "",
            "Status": partner.status,
            "Verification": partner.verification_status,
            "Rating": partner.rating,
        }
        for partner in partners
    ]

    st.dataframe(
        table_data,
        hide_index=True,
        width="stretch",
    )

    st.markdown("---")
    st.subheader("Edit or Delete Partner")

    selected_partner = st.selectbox(
        "Select partner",
        options=partners,
        format_func=lambda partner: (
            f"{partner.company_name} — {partner.partner_type} — "
            f"{partner.country}"
        ),
    )

    with st.form(f"edit_partner_{selected_partner.id}"):
        company_name = st.text_input(
            "Company name",
            value=selected_partner.company_name,
        )

        partner_type = st.selectbox(
            "Partner type",
            PARTNER_TYPES,
            index=(
                PARTNER_TYPES.index(selected_partner.partner_type)
                if selected_partner.partner_type in PARTNER_TYPES
                else 0
            ),
        )

        country = st.text_input(
            "Country",
            value=selected_partner.country,
        )

        city = st.text_input(
            "City",
            value=selected_partner.city or "",
        )

        contact_name = st.text_input(
            "Contact person",
            value=selected_partner.contact_name or "",
        )

        email = st.text_input(
            "Email",
            value=selected_partner.email or "",
        )

        phone = st.text_input(
            "Phone",
            value=selected_partner.phone or "",
        )

        whatsapp = st.text_input(
            "WhatsApp",
            value=selected_partner.whatsapp or "",
        )

        website = st.text_input(
            "Website",
            value=selected_partner.website or "",
        )

        products_services = st.text_area(
            "Products or services",
            value=selected_partner.products_services or "",
        )

        status = st.selectbox(
            "Status",
            STATUSES,
            index=(
                STATUSES.index(selected_partner.status)
                if selected_partner.status in STATUSES
                else 0
            ),
        )

        verification_status = st.selectbox(
            "Verification status",
            VERIFICATION_STATUSES,
            index=(
                VERIFICATION_STATUSES.index(
                    selected_partner.verification_status
                )
                if selected_partner.verification_status
                in VERIFICATION_STATUSES
                else 0
            ),
        )

        rating = st.slider(
            "Internal rating",
            min_value=0,
            max_value=5,
            value=selected_partner.rating,
        )

        notes = st.text_area(
            "Notes",
            value=selected_partner.notes or "",
        )

        update_submitted = st.form_submit_button(
            "Update Partner",
            type="primary",
            width="stretch",
        )

    if update_submitted:
        if not company_name.strip() or not country.strip():
            st.warning("Company name and country are required.")
        else:
            update_partner(
                Partner(
                    id=selected_partner.id,
                    company_name=company_name,
                    partner_type=partner_type,
                    country=country,
                    city=city,
                    contact_name=contact_name,
                    email=email,
                    phone=phone,
                    whatsapp=whatsapp,
                    website=website,
                    products_services=products_services,
                    status=status,
                    verification_status=verification_status,
                    rating=rating,
                    notes=notes,
                )
            )

            st.success("Partner updated successfully.")
            st.rerun()

    confirm_delete = st.checkbox(
        f"Confirm deletion of {selected_partner.company_name}"
    )

    if st.button(
        "Delete Partner",
        disabled=not confirm_delete,
    ):
        delete_partner(selected_partner.id)
        st.success("Partner deleted successfully.")
        st.rerun()