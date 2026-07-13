import streamlit as st


def show() -> None:
    st.title("📄 Supplier Quotations")

    st.write(
        "Create RFQs, record supplier quotations, and compare offers."
    )

    rfq_tab, quotations_tab, comparison_tab = st.tabs(
        [
            "📨 Create RFQ",
            "📋 Quotations",
            "📊 Compare",
        ]
    )

    with rfq_tab:
        st.subheader("Create Request for Quotation")

        st.selectbox(
            "Product category",
            [
                "Rice",
                "Cricket Equipment",
                "Automotive Parts",
                "Medical Supplies",
                "Other",
            ],
        )

        st.text_input("Product name")
        st.text_input("Quantity")
        st.text_input("Preferred Incoterm")
        st.text_input("Destination")

        st.text_area(
            "Requirements",
            placeholder=(
                "Specifications, packaging, certificates, MOQ, samples, "
                "lead time, payment terms, shipping, and documents."
            ),
            height=180,
        )

        if st.button("Generate RFQ", type="primary"):
            st.success(
                "RFQ template is ready. Email automation will be connected later."
            )

    with quotations_tab:
        st.subheader("Supplier Quotations")
        st.info("Saved quotations will appear here.")

    with comparison_tab:
        st.subheader("Quotation Comparison")
        st.info(
            "This section will compare price, quality, MOQ, Incoterms, "
            "lead time, shipping, certificates, and landed cost."
        )