from datetime import date

import streamlit as st

from models.partner import Partner
from services.global_discovery_service import (
    DEFAULT_VERIFICATION_CHECKLIST,
    DiscoveryRequest,
    prepare_discovery_search,
)
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

CERTIFICATE_OPTIONS = [
    "HACCP",
    "ISO 9001",
    "ISO 22000",
    "BRCGS",
    "IFS",
    "Halal",
    "Kosher",
    "FDA",
    "CE",
    "GMP",
    "Phytosanitary Certificate",
    "Certificate of Origin",
    "Fumigation Certificate",
]

INCOTERM_OPTIONS = [
    "EXW",
    "FCA",
    "FOB",
    "CFR",
    "CIF",
    "CPT",
    "CIP",
    "DAP",
    "DPU",
    "DDP",
]


def show() -> None:
    st.title("🌍 Global Supplier Discovery")
    st.caption(
        "Prepare structured global searches, verify companies, "
        "capture quotations and certificates, and save approved candidates."
    )

    search_tab, save_tab = st.tabs(
        [
            "🔍 Discovery Search",
            "💾 Save Candidate",
        ]
    )

    with search_tab:
        _show_search_tab()

    with save_tab:
        _show_save_tab()


def _show_search_tab() -> None:
    st.subheader("Search Requirements")

    partner_type = st.selectbox(
        "Partner Type",
        PARTNER_TYPES,
    )

    product = st.text_input(
        "Product or Service",
        placeholder=(
            "Example: ST25 rice, cricket bats, brake pads, "
            "medical gloves"
        ),
    )

    country = st.text_input(
        "Preferred Country",
        placeholder="Example: Vietnam",
    )

    destination = st.text_input(
        "Destination Market",
        placeholder="Example: Melbourne, Australia",
    )

    col1, col2 = st.columns(2)

    with col1:
        required_certificates = st.multiselect(
            "Required Certificates",
            CERTIFICATE_OPTIONS,
        )

        preferred_incoterms = st.multiselect(
            "Preferred Incoterms",
            INCOTERM_OPTIONS,
        )

    with col2:
        maximum_lead_time_days = st.number_input(
            "Maximum Lead Time (days)",
            min_value=0,
            value=0,
            help="Use 0 when no maximum is required.",
        )

        minimum_confidence_score = st.slider(
            "Minimum Confidence Score",
            min_value=0,
            max_value=100,
            value=60,
        )

    requirements = st.text_area(
        "Full Requirements",
        height=180,
        placeholder=(
            "MOQ, specifications, packaging, private label, "
            "quotation, certificates, samples, export experience, "
            "production capacity, preferred port, payment terms, "
            "and any other requirements."
        ),
    )

    if not st.button(
        "Prepare Global Discovery Search",
        type="primary",
        width="stretch",
    ):
        return

    if not product.strip():
        st.warning("Enter a product or service.")
        return

    request = DiscoveryRequest(
        partner_type=partner_type,
        product=product.strip(),
        country=country.strip(),
        destination=destination.strip(),
        requirements=requirements.strip(),
        required_certificates=tuple(required_certificates),
        preferred_incoterms=tuple(preferred_incoterms),
        maximum_lead_time_days=(
            int(maximum_lead_time_days)
            if maximum_lead_time_days > 0
            else None
        ),
        minimum_confidence_score=int(
            minimum_confidence_score
        ),
    )

    result = prepare_discovery_search(request)

    st.success("Structured discovery request prepared.")

    st.markdown("### Search Summary")
    st.write(f"**Partner Type:** {request.partner_type}")
    st.write(f"**Product or Service:** {request.product}")
    st.write(
        f"**Country:** {request.country or 'Any country'}"
    )
    st.write(
        f"**Destination:** "
        f"{request.destination or 'Not specified'}"
    )
    st.write(
        f"**Required Certificates:** "
        f"{', '.join(request.required_certificates) or 'None specified'}"
    )
    st.write(
        f"**Preferred Incoterms:** "
        f"{', '.join(request.preferred_incoterms) or 'None specified'}"
    )
    st.write(
        f"**Maximum Lead Time:** "
        f"{request.maximum_lead_time_days or 'Not specified'}"
    )
    st.write(
        f"**Minimum Confidence:** "
        f"{request.minimum_confidence_score}/100"
    )

    st.markdown("### Prepared Search Queries")

    for query in result.search_queries:
        st.code(query)

    st.markdown("### Verification Checklist")

    checklist_rows = [
        {
            "Check": item,
            "Required": "Yes",
            "Status": "Pending",
        }
        for item in DEFAULT_VERIFICATION_CHECKLIST
    ]

    st.dataframe(
        checklist_rows,
        hide_index=True,
        width="stretch",
    )

    st.markdown("### Live Global Search Results")
    st.caption(f"Provider: {result.provider_name}")

    live_results = []

    for response in result.live_responses:
        if not response.success:
            continue

        for item in response.results:
            live_results.append(
                {
                    "Title": item.title,
                    "Source": item.source_name,
                    "URL": item.url,
                    "Summary": item.snippet,
                    "Published": item.published_at or "",
                    "Relevance": item.metadata.get(
                        "relevance_score",
                        "",
                    ),
                }
            )

    if live_results:
        st.success(
            f"{len(live_results)} live web result(s) found."
        )

        st.dataframe(
            live_results,
            hide_index=True,
            width="stretch",
            column_config={
                "URL": st.column_config.LinkColumn(
                    "URL",
                    display_text="Open source",
                ),
            },
        )

        selected_result = st.selectbox(
            "Review a live result",
            live_results,
            format_func=lambda item: (
                f"{item['Title']} — {item['Source']}"
            ),
        )

        st.write(f"**Title:** {selected_result['Title']}")
        st.write(f"**Source:** {selected_result['Source']}")
        st.write(
            f"**Summary:** "
            f"{selected_result['Summary'] or 'No summary available.'}"
        )
        st.link_button(
            "Open Source Website",
            selected_result["URL"],
            use_container_width=True,
        )

        st.warning(
            "These are live web results, not verified suppliers. "
            "Review company identity, official website, registration, "
            "certificates, contacts and quotation details before saving."
        )
    else:
        st.info(
            "No live results were returned. Check the Tavily API key, "
            "internet connection or search requirements."
        )

    for warning in result.warnings:
        st.info(warning)


def _show_save_tab() -> None:
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
        email = st.text_input("Business Email")
        phone = st.text_input("Phone")
        whatsapp = st.text_input("WhatsApp")
        website = st.text_input("Official Website")

        products_services = st.text_area(
            "Products or Services",
            placeholder=(
                "Example: ST25 rice, Jasmine rice, cricket bats, "
                "brake pads, medical gloves, freight, warehouse."
            ),
        )

        col1, col2 = st.columns(2)

        with col1:
            quotation_summary = st.text_area(
                "Quotation Summary",
                placeholder=(
                    "Currency, unit price, MOQ, Incoterm, "
                    "lead time and payment terms."
                ),
            )

            packaging_private_label = st.text_area(
                "Packaging and Private Label",
            )

            capacity_export_markets = st.text_area(
                "Capacity and Export Markets",
            )

        with col2:
            certificates = st.text_area(
                "Certificates and Licences",
                placeholder=(
                    "Certificate names, numbers, issuing bodies "
                    "and expiry dates."
                ),
            )

            samples = st.text_area(
                "Samples",
                placeholder="Availability, cost and shipping method.",
            )

            risk_flags = st.text_area(
                "Risk Flags or Missing Information",
            )

        source = st.text_input(
            "Research Source",
            placeholder=(
                "Official website, government exporter directory, "
                "trade association or industry directory."
            ),
        )

        evidence_link = st.text_input(
            "Evidence Link",
            placeholder="Paste source or company website URL",
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
            height=180,
        )

        submitted = st.form_submit_button(
            "Save to Global Partners",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if not company_name.strip() or not country.strip():
        st.warning("Company name and country are required.")
        return

    research_summary = (
        f"Research source: {source.strip() or 'Not provided'}\n"
        f"Evidence link: {evidence_link.strip() or 'Not provided'}\n"
        f"Confidence score: {confidence_score}/100\n"
        f"Discovered date: {discovered_date.isoformat()}\n\n"
        f"Quotation:\n{quotation_summary.strip() or 'Not recorded'}\n\n"
        f"Packaging/private label:\n"
        f"{packaging_private_label.strip() or 'Not recorded'}\n\n"
        f"Capacity/export markets:\n"
        f"{capacity_export_markets.strip() or 'Not recorded'}\n\n"
        f"Certificates/licences:\n"
        f"{certificates.strip() or 'Not recorded'}\n\n"
        f"Samples:\n{samples.strip() or 'Not recorded'}\n\n"
        f"Risk flags/missing information:\n"
        f"{risk_flags.strip() or 'None recorded'}\n\n"
        f"Notes:\n{notes.strip() or 'None'}"
    ).strip()

    partner_id = create_partner(
        Partner(
            company_name=company_name.strip(),
            partner_type=partner_type,
            country=country.strip(),
            city=city.strip(),
            contact_name=contact_name.strip(),
            email=email.strip(),
            phone=phone.strip(),
            whatsapp=whatsapp.strip(),
            website=website.strip(),
            products_services=products_services.strip(),
            status="Prospect",
            verification_status=verification_status,
            rating=0,
            notes=research_summary,
        )
    )

    st.success(
        f"Candidate saved successfully. Partner ID: {partner_id}"
    )