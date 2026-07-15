import streamlit as st

from models.product import Product
from services.product_service import (
    create_product,
    delete_product,
    get_product_categories,
    get_products,
    update_product,
)


CATEGORIES = [
    "Rice",
    "Cricket Equipment",
    "Automotive Parts",
    "Medical Supplies",
    "Packaging",
    "Other",
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
]

STATUSES = [
    "Active",
    "Inactive",
    "Discontinued",
]


def show() -> None:
    st.title("📦 Product Catalogue")
    st.caption(
        "Manage products, specifications, packaging, certificates, and storage requirements."
    )

    add_tab, directory_tab = st.tabs(
        [
            "➕ Add Product",
            "📋 Product Directory",
        ]
    )

    with add_tab:
        show_add_product()

    with directory_tab:
        show_product_directory()


def show_add_product() -> None:
    st.subheader("Add New Product")

    with st.form("add_product_form", clear_on_submit=True):
        name = st.text_input("Product name *")
        category = st.selectbox("Category", CATEGORIES)
        sku = st.text_input("SKU *")
        unit = st.selectbox("Unit", UNITS)
        country_of_origin = st.text_input("Country of origin")
        description = st.text_area("Description")
        specifications = st.text_area("Specifications")
        packaging = st.text_area("Packaging")
        required_certificates = st.text_area("Required certificates")
        storage_requirements = st.text_area("Storage requirements")
        status = st.selectbox("Status", STATUSES)

        submitted = st.form_submit_button(
            "Save Product",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if not name.strip() or not sku.strip():
        st.warning("Product name and SKU are required.")
        return

    try:
        product_id = create_product(
            Product(
                name=name,
                category=category,
                sku=sku,
                unit=unit,
                country_of_origin=country_of_origin,
                description=description,
                specifications=specifications,
                packaging=packaging,
                required_certificates=required_certificates,
                storage_requirements=storage_requirements,
                status=status,
            )
        )

        st.success(
            f"Product saved successfully. Product ID: {product_id}"
        )

    except ValueError as error:
        st.error(str(error))


def show_product_directory() -> None:
    st.subheader("Product Directory")

    search = st.text_input(
        "Search products",
        placeholder="Search by name, SKU, category, origin, or description",
    )

    available_categories = ["All"] + get_product_categories()

    col1, col2 = st.columns(2)

    with col1:
        category = st.selectbox(
            "Filter by category",
            available_categories,
        )

    with col2:
        status = st.selectbox(
            "Filter by status",
            ["All"] + STATUSES,
        )

    products = get_products(
        search=search,
        category=category,
        status=status,
    )

    st.caption(f"{len(products)} product(s) found")

    if not products:
        st.info("No products found.")
        return

    table_data = [
        {
            "ID": product.id,
            "Name": product.name,
            "SKU": product.sku,
            "Category": product.category,
            "Unit": product.unit,
            "Country of Origin": product.country_of_origin or "",
            "Status": product.status,
        }
        for product in products
    ]

    st.dataframe(
        table_data,
        hide_index=True,
        width="stretch",
    )

    st.markdown("---")
    st.subheader("Edit or Delete Product")

    selected_product = st.selectbox(
        "Select product",
        options=products,
        format_func=lambda product: (
            f"{product.name} — {product.sku}"
        ),
    )

    with st.form(f"edit_product_{selected_product.id}"):
        name = st.text_input(
            "Product name",
            value=selected_product.name,
        )

        category = st.selectbox(
            "Category",
            CATEGORIES,
            index=(
                CATEGORIES.index(selected_product.category)
                if selected_product.category in CATEGORIES
                else len(CATEGORIES) - 1
            ),
        )

        sku = st.text_input(
            "SKU",
            value=selected_product.sku,
        )

        unit = st.selectbox(
            "Unit",
            UNITS,
            index=(
                UNITS.index(selected_product.unit)
                if selected_product.unit in UNITS
                else 0
            ),
        )

        country_of_origin = st.text_input(
            "Country of origin",
            value=selected_product.country_of_origin or "",
        )

        description = st.text_area(
            "Description",
            value=selected_product.description or "",
        )

        specifications = st.text_area(
            "Specifications",
            value=selected_product.specifications or "",
        )

        packaging = st.text_area(
            "Packaging",
            value=selected_product.packaging or "",
        )

        required_certificates = st.text_area(
            "Required certificates",
            value=selected_product.required_certificates or "",
        )

        storage_requirements = st.text_area(
            "Storage requirements",
            value=selected_product.storage_requirements or "",
        )

        status = st.selectbox(
            "Status",
            STATUSES,
            index=(
                STATUSES.index(selected_product.status)
                if selected_product.status in STATUSES
                else 0
            ),
        )

        update_submitted = st.form_submit_button(
            "Update Product",
            type="primary",
            width="stretch",
        )

    if update_submitted:
        if not name.strip() or not sku.strip():
            st.warning("Product name and SKU are required.")
        else:
            try:
                update_product(
                    Product(
                        id=selected_product.id,
                        name=name,
                        category=category,
                        sku=sku,
                        unit=unit,
                        country_of_origin=country_of_origin,
                        description=description,
                        specifications=specifications,
                        packaging=packaging,
                        required_certificates=required_certificates,
                        storage_requirements=storage_requirements,
                        status=status,
                    )
                )

                st.success("Product updated successfully.")
                st.rerun()

            except ValueError as error:
                st.error(str(error))

    confirm_delete = st.checkbox(
        f"Confirm deletion of {selected_product.name}"
    )

    if st.button(
        "Delete Product",
        disabled=not confirm_delete,
    ):
        delete_product(selected_product.id)
        st.success("Product deleted successfully.")
        st.rerun()