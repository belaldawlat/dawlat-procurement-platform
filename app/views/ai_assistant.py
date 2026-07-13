import streamlit as st


def show():
    st.title("🤖 AI Assistant")

    st.write(
        "Ask questions about suppliers, quotations, imports, exports, shipping, or Dawlat Global."
    )

    user_prompt = st.text_area(
        "Ask your question",
        placeholder="Example: Compare rice suppliers from Vietnam and Pakistan.",
        height=150,
    )

    if st.button("Ask AI"):
        if user_prompt.strip():
            st.success("AI integration will be connected in the next steps.")
            st.write(f"**Your question:** {user_prompt}")
        else:
            st.warning("Please enter a question.")
