import streamlit as st

from services.supplier_service import count_suppliers


def show() -> None:
    st.title("🏠 Dashboard")

    st.write(
        "Welcome to the Dawlat Procurement Platform for "
        "Dawlat Global Imports & Trading."
    )

    st.markdown("---")

    supplier_total = count_suppliers()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Suppliers", supplier_total)

    with col2:
        st.metric("Quotations", 0)

    with col3:
        st.metric("Products", 0)

    st.markdown("---")

    st.info(
        "The Supplier CRM is connected to the database and ready to use."
    )
