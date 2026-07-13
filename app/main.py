import streamlit as st

from database.setup import create_database
from services.auth_service import ensure_admin_user
from views import (
    ai_assistant,
    dashboard,
    login,
    settings,
    supplier_quotations,
    suppliers,
    users,
)


st.set_page_config(
    page_title="Dawlat Procurement Platform",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

create_database()
ensure_admin_user()

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login.show_login()
    st.stop()

st.sidebar.title("🌍 Dawlat Procurement Platform")
st.sidebar.caption("Dawlat Global Imports & Trading")
st.sidebar.markdown("---")

st.sidebar.write(
    f"Signed in as **{st.session_state.get('full_name', '')}**"
)
st.sidebar.caption(
    f"Role: {st.session_state.get('role', 'User')}"
)

if st.sidebar.button("Log Out", width="stretch"):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")

menu_items = [
    "🏠 Dashboard",
    "🤖 AI Assistant",
    "🏢 Suppliers",
    "🌍 Supplier Discovery",
    "📄 Supplier Quotations",
    "💰 Landed Cost",
    "🚢 Freight & Customs",
    "🏭 Warehouses & 3PL",
    "📦 Inventory",
    "🚚 Shipments",
    "👥 Customers",
    "📝 Sales Quotations",
    "🛒 Orders",
    "🧾 Invoices",
    "💳 Payments",
    "📧 Email Generator",
    "📁 Documents",
    "📈 Analytics",
    "⚙️ Settings",
]

if st.session_state.get("role") == "Admin":
    menu_items.append("👥 User Management")

menu = st.sidebar.radio(
    "Navigation",
    menu_items,
)

if menu == "🏠 Dashboard":
    dashboard.show()

elif menu == "🤖 AI Assistant":
    ai_assistant.show()

elif menu == "🏢 Suppliers":
    suppliers.show()

elif menu == "📄 Supplier Quotations":
    supplier_quotations.show()

elif menu == "⚙️ Settings":
    settings.show()

elif menu == "👥 User Management":
    users.show()

else:
    st.title(menu)
    st.info("This module will be connected in a later milestone.")