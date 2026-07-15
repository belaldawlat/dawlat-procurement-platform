from datetime import date

import streamlit as st

from models.partner import Partner
from services.partner_service import create_partner


PARTNER_TYPES = [
    "Supplier",
    "Manufacturer",
    "Exporter",
    "Freight Forwarder",
    "Customs Broker",
    "Warehouse",
    "3PL Provider",
    "Shipping Line",
    "Inspection Company",
    "Certification Company",
]


def show() -> None:
    st.title("🌍 Global Supplier Discovery")
    st.caption(
        "Discover suppliers and international trade partners anywhere in the world."
    )

    search_tab, save_tab = st.tabs(
        [
            "🔍 Discovery Search",
            "💾 Save Candidate",
        ]
    )

    with search_tab:
        st.subheader("Search Requirements")

        partner_type = st.selectbox(
            "Partner Type",
            PARTNER_TYPES,
        )

        product = st.text_input(
            "Product or Service",
            placeholder="Example: ST25 Rice",
        )

        country = st.text_input(
            "Country",
            placeholder="Example: Vietnam",
        )

        destination = st.text_input(
            "Destination Market",
            placeholder="Example: Melbourne, Australia",
        )

        requirements = st.text_area(
            "Requirements",
            height=180,
            placeholder=(
                "MOQ, certificates, packaging, Incoterms, lead time, "
                "export experience, preferred port, and other requirements."
            ),
        )

        if st.button(
            "Prepare Discovery Search",
            type="primary",
            width="stretch",
        ):
            if not product.strip():
                st.warning("Enter a product or service.")
            else:
                st.success("Discovery request prepared.")

                st.markdown("### Search Summary")
                st.write(f"**Partner Type:** {partner_type}")
                st.write(f"**Product or Service:** {product}")
                st.write(f"**Country:** {country or 'Any'}")
                st.write(f"**Destination:** {destination or 'Not specified'}")
                st.write(f"**Requirements:** {requirements or 'None'}")

                st.info(
                    "Live web research will be connected through approved APIs "
                    "and trusted sources. Results will require review before saving."
                )

    with save_tab:
        st.subheader("Save Researched Candidate")

        with st.form(
            "save_candidate_form",
            clear_on_submit=True,
        ):
            company_name = st.text_input("Company Name *")

            partner_type = st.selectbox(
                "Partner Type",
                PARTNER_TYPES,
                key="candidate_partner_type",
            )

            country = st.text_input("Country *")
            city = st.text_input("City")
            contact_name = st.text_input("Contact Person")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            whatsapp = st.text_input("WhatsApp")
            website = st.text_input("Website")

            products_services = st.text_area(
                "Products or Services",
                placeholder=(
                    "Example: ST25 rice, Jasmine rice, customs clearance, "
                    "sea freight, container transport, warehouse storage."
                ),
            )

            source = st.text_input(
                "Research Source",
                placeholder=(
                    "Company website, government exporter directory, "
                    "trade association, or industry directory."
                ),
            )

            evidence_link = st.text_input(
                "Evidence Link",
                placeholder="Paste the source page or company website link",
            )

            confidence_score = st.slider(
                "Confidence Score",
                min_value=0,
                max_value=100,
                value=50,
            )

            verification_status = st.selectbox(
                "Verification Status",
                [
                    "Researching",
                    "Unverified",
                    "Partially Verified",
                    "Verified",
                    "Rejected",
                ],
            )

            discovered_date = st.date_input(
                "Discovered Date",
                value=date.today(),
            )

            notes = st.text_area(
                "Research Notes",
                placeholder=(
                    "Certificates, export markets, MOQ, Incoterms, lead time, "
                    "ports, risks, missing information, and follow-up actions."
                ),
                height=180,
            )

            submitted = st.form_submit_button(
                "Save to Global Partners",
                type="primary",
                width="stretch",
            )

        if submitted:
            if not company_name.strip() or not country.strip():
                st.warning("Company name and country are required.")
                return

            research_summary = (
                f"Research source: {source.strip() or 'Not provided'}\n"
                f"Evidence link: {evidence_link.strip() or 'Not provided'}\n"
                f"Confidence score: {confidence_score}/100\n"
                f"Discovered date: {discovered_date.isoformat()}\n\n"
                f"{notes.strip()}"
            ).strip()

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
                    status="Prospect",
                    verification_status=verification_status,
                    rating=0,
                    notes=research_summary,
                )
            )

            st.success(
                f"Candidate saved successfully. Partner ID: {partner_id}"
            )