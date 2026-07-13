import streamlit as st

from database.setup import create_database
from views import ai_assistant, dashboard, suppliers


create_database()

st.set_page_config(
    page_title="Dawlat Procurement Platform",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("🌍 Dawlat Procurement Platform")
st.sidebar.caption("Dawlat Global Imports & Trading")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navigation",
    [
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
    ],
)

if menu == "🏠 Dashboard":
    dashboard.show()

elif menu == "🤖 AI Assistant":
    ai_assistant.show()

elif menu == "🏢 Suppliers":
    suppliers.show()

else:
    st.title(menu)
    st.info("This module will be built in the next milestone.")