import streamlit as st

from models.supplier import Supplier
from services.supplier_service import (
    create_supplier,
    delete_supplier,
    get_suppliers,
    update_supplier,
)


CATEGORIES = [
    "Rice",
    "Cricket Equipment",
    "Automotive Parts",
    "Medical Supplies",
    "Other",
]


def show() -> None:
    st.title("🏢 Supplier CRM")

    st.write(
        "Add, search, update, and manage suppliers for Dawlat Global."
    )

    add_tab, directory_tab = st.tabs(
        ["➕ Add Supplier", "📋 Supplier Directory"]
    )

    with add_tab:
        show_add_supplier_form()

    with directory_tab:
        show_supplier_directory()


def show_add_supplier_form() -> None:
    st.subheader("Add New Supplier")

    with st.form("add_supplier_form", clear_on_submit=True):
        company_name = st.text_input("Company name *")
        category = st.selectbox("Product category", CATEGORIES)
        country = st.text_input("Country *")
        contact_name = st.text_input("Contact person")
        email = st.text_input("Email")
        phone = st.text_input("Phone / WhatsApp")
        website = st.text_input("Website")

        notes = st.text_area(
            "Notes",
            placeholder=(
                "Products, certifications, MOQ, pricing, packaging, "
                "Incoterms, shipping, quality, and risk notes."
            ),
        )

        submitted = st.form_submit_button(
            "Save Supplier",
            type="primary",
        )

    if submitted:
        if not company_name.strip() or not country.strip():
            st.warning("Company name and country are required.")
            return

        supplier = Supplier(
            company_name=company_name,
            category=category,
            country=country,
            contact_name=contact_name,
            email=email,
            phone=phone,
            website=website,
            notes=notes,
        )

        supplier_id = create_supplier(supplier)

        st.success(
            f"Supplier saved successfully. Supplier ID: {supplier_id}"
        )


def show_supplier_directory() -> None:
    st.subheader("Supplier Directory")

    search = st.text_input(
        "Search suppliers",
        placeholder="Search by company, category, country, contact, or email",
    )

    suppliers = get_suppliers(search)

    st.caption(f"{len(suppliers)} supplier(s) found")

    if not suppliers:
        st.info("No suppliers found.")
        return

    table_data = [
        {
            "ID": supplier.id,
            "Company": supplier.company_name,
            "Category": supplier.category,
            "Country": supplier.country,
            "Contact": supplier.contact_name or "",
            "Email": supplier.email or "",
            "Phone / WhatsApp": supplier.phone or "",
        }
        for supplier in suppliers
    ]

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.subheader("Edit or Delete Supplier")

    selected_supplier = st.selectbox(
        "Select supplier",
        options=suppliers,
        format_func=lambda supplier: (
            f"{supplier.company_name} — {supplier.country}"
        ),
    )

    with st.form(f"edit_supplier_{selected_supplier.id}"):
        company_name = st.text_input(
            "Company name",
            value=selected_supplier.company_name,
        )

        category_index = (
            CATEGORIES.index(selected_supplier.category)
            if selected_supplier.category in CATEGORIES
            else len(CATEGORIES) - 1
        )

        category = st.selectbox(
            "Product category",
            CATEGORIES,
            index=category_index,
        )

        country = st.text_input(
            "Country",
            value=selected_supplier.country,
        )

        contact_name = st.text_input(
            "Contact person",
            value=selected_supplier.contact_name or "",
        )

        email = st.text_input(
            "Email",
            value=selected_supplier.email or "",
        )

        phone = st.text_input(
            "Phone / WhatsApp",
            value=selected_supplier.phone or "",
        )

        website = st.text_input(
            "Website",
            value=selected_supplier.website or "",
        )

        notes = st.text_area(
            "Notes",
            value=selected_supplier.notes or "",
        )

        update_submitted = st.form_submit_button(
            "Update Supplier",
            type="primary",
        )

    if update_submitted:
        if not company_name.strip() or not country.strip():
            st.warning("Company name and country are required.")
        else:
            update_supplier(
                Supplier(
                    id=selected_supplier.id,
                    company_name=company_name,
                    category=category,
                    country=country,
                    contact_name=contact_name,
                    email=email,
                    phone=phone,
                    website=website,
                    notes=notes,
                )
            )

            st.success("Supplier updated successfully.")
            st.rerun()

    confirm_delete = st.checkbox(
        f"Confirm deletion of {selected_supplier.company_name}"
    )

    if st.button(
        "Delete Supplier",
        disabled=not confirm_delete,
    ):
        delete_supplier(selected_supplier.id)
        st.success("Supplier deleted successfully.")
        st.rerun()
