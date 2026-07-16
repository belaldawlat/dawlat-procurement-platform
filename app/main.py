import streamlit as st
from dotenv import load_dotenv

from database.setup import create_database
from services.auth_service import ensure_admin_user
from services.global_search_provider import (
    configure_global_search_provider,
)
from services.tavily_search_provider import (
    create_tavily_provider,
)
from views import (
    ai_assistant,
    customers,
    dashboard,
    freight_customs,
    inventory,
    landed_cost,
    login,
    market_opportunities,
    opportunity_dashboard,
    partners,
    products,
    quotation_comparison,
    rfqs,
    settings,
    shipments,
    supplier_discovery,
    supplier_quotations,
    suppliers,
    users,
    warehouses_3pl,
)


def configure_live_search() -> None:
    """
    Load environment variables and configure Tavily when available.

    If the API key is missing, the application continues safely with
    live global search disabled.
    """

    load_dotenv()

    provider = create_tavily_provider()

    if provider.is_configured:
        configure_global_search_provider(provider)


st.set_page_config(
    page_title="Dawlat Procurement Platform",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

configure_live_search()
create_database()
ensure_admin_user()

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login.show_login()
    st.stop()

st.sidebar.title(
    "🌍 Dawlat Procurement Platform"
)

st.sidebar.caption(
    "Dawlat Global Imports & Trading"
)

st.sidebar.markdown("---")

st.sidebar.write(
    f"Signed in as "
    f"**{st.session_state.get('full_name', '')}**"
)

st.sidebar.caption(
    f"Role: "
    f"{st.session_state.get('role', 'User')}"
)

if st.sidebar.button(
    "Log Out",
    width="stretch",
):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")

menu_items = [
    "🏠 Dashboard",
    "📊 Opportunity Dashboard",
    "🧠 Market Intelligence",
    "🌍 Global Discovery",
    "🌐 Global Partners",
    "🏢 Suppliers",
    "👥 Customers",
    "📦 Products",
    "📨 RFQs",
    "📄 Supplier Quotations",
    "⚖️ Quotation Comparison",
    "💰 Landed Cost",
    "🚢 Freight & Customs",
    "🏭 Warehouses & 3PL",
    "📦 Inventory",
    "🚚 Shipments",
    "📝 Sales Quotations",
    "🛒 Orders",
    "🧾 Invoices",
    "💳 Payments",
    "📁 Documents",
    "📧 Email Generator",
    "🤖 AI Assistant",
    "📈 Analytics",
    "⚙️ Settings",
]

if st.session_state.get("role") == "Admin":
    menu_items.append(
        "👥 User Management"
    )

menu = st.sidebar.radio(
    "Navigation",
    menu_items,
)

if menu == "🏠 Dashboard":
    dashboard.show()

elif menu == "📊 Opportunity Dashboard":
    opportunity_dashboard.show()

elif menu == "🧠 Market Intelligence":
    market_opportunities.show()

elif menu == "🌍 Global Discovery":
    supplier_discovery.show()

elif menu == "🌐 Global Partners":
    partners.show()

elif menu == "🏢 Suppliers":
    suppliers.show()

elif menu == "👥 Customers":
    customers.show()

elif menu == "📦 Products":
    products.show()

elif menu == "📨 RFQs":
    rfqs.show()

elif menu == "📄 Supplier Quotations":
    supplier_quotations.show()

elif menu == "⚖️ Quotation Comparison":
    quotation_comparison.show()

elif menu == "💰 Landed Cost":
    landed_cost.show()

elif menu == "🚢 Freight & Customs":
    freight_customs.show()

elif menu == "🏭 Warehouses & 3PL":
    warehouses_3pl.show()

elif menu == "📦 Inventory":
    inventory.show()

elif menu == "🚚 Shipments":
    shipments.show()

elif menu == "🤖 AI Assistant":
    ai_assistant.show()

elif menu == "⚙️ Settings":
    settings.show()

elif menu == "👥 User Management":
    users.show()

else:
    st.title(menu)

    st.info(
        "This module will be connected "
        "in a later phase."
    )