import streamlit as st

from services.auth_service import authenticate_user


def show_login() -> None:
    st.title("🌍 Dawlat Procurement Platform")
    st.caption("Dawlat Global Imports & Trading")

    st.markdown("---")
    st.subheader("Secure Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        submitted = st.form_submit_button(
            "Sign In",
            type="primary",
            width="stretch",
        )

    if submitted:
        user = authenticate_user(username, password)

        if user is None:
            st.error("Incorrect username or password.")
            return

        st.session_state["authenticated"] = True
        st.session_state["user_id"] = user.id
        st.session_state["username"] = user.username
        st.session_state["full_name"] = user.full_name
        st.session_state["role"] = user.role

        st.rerun()