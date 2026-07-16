"""
Dawlat AI Procurement Assistant interface.

This page connects the Streamlit UI to the grounded procurement
intelligence engine in services.ai_assistant_service.
"""

from __future__ import annotations

import streamlit as st

from services.ai_assistant_service import AIResponse, answer_question


EXAMPLE_QUESTIONS = [
    "What should Dawlat Global prioritise today?",
    "Which market opportunity should we pursue first?",
    "Show me suppliers for ST25 rice.",
    "Which customers need rice or food products?",
    "Compare the available supplier quotations.",
    "Are any shipments delayed or at risk?",
    "What inventory items need reorder attention?",
]


def show() -> None:
    st.title("🤖 Dawlat AI Procurement Assistant")
    st.caption(
        "Ask one business question across suppliers, customers, products, "
        "opportunities, quotations, shipments, inventory and procurement operations."
    )

    st.info(
        "Current mode: grounded internal intelligence. "
        "Answers use saved platform data only; live global web research "
        "will be added in the next integration stage."
    )

    st.markdown("### Example questions")

    columns = st.columns(2)

    for index, question in enumerate(EXAMPLE_QUESTIONS):
        target_column = columns[index % 2]

        with target_column:
            if st.button(
                question,
                key=f"ai_example_{index}",
                use_container_width=True,
            ):
                st.session_state["ai_question"] = question

    question = st.text_area(
        "Ask your question",
        value=st.session_state.get("ai_question", ""),
        placeholder=(
            "Example: Which opportunity should Dawlat Global pursue first, "
            "which supplier can fulfil it, and what should I do next?"
        ),
        height=150,
    )

    ask_clicked = st.button(
        "Ask Dawlat AI",
        type="primary",
        use_container_width=True,
    )

    if not ask_clicked:
        return

    if not question.strip():
        st.warning("Please enter a question.")
        return

    with st.spinner("Analysing the Dawlat Procurement Platform..."):
        response = answer_question(question)

    _render_response(response)


def _render_response(response: AIResponse) -> None:
    if not response.success:
        st.error(response.summary)
        return

    st.markdown("---")
    st.subheader(response.title)
    st.write(response.summary)

    if response.metrics:
        st.markdown("### Key Metrics")

        metric_items = list(response.metrics.items())
        columns = st.columns(min(4, max(1, len(metric_items))))

        for index, (label, value) in enumerate(metric_items):
            display_label = label.replace("_", " ").title()
            columns[index % len(columns)].metric(display_label, value)

    if response.warnings:
        st.markdown("### Data Gaps or Warnings")

        for warning in response.warnings:
            st.warning(warning)

    if response.recommendations:
        st.markdown("### Recommended Actions")

        for index, recommendation in enumerate(
            response.recommendations,
            start=1,
        ):
            st.write(f"**{index}.** {recommendation}")

    if response.evidence:
        st.markdown("### Evidence from Your Platform")

        for item in response.evidence:
            with st.expander(
                f"{item.source}: {item.label}",
                expanded=False,
            ):
                st.write(item.details)

                if item.record_id is not None:
                    st.caption(f"Record ID: {item.record_id}")

    if response.data:
        with st.expander("Technical response details"):
            st.json(response.data)