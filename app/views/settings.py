import streamlit as st

from services.auth_service import (
    change_password,
    get_user_by_id,
    update_profile,
)


def show() -> None:
    st.title("⚙️ Platform Settings")
    st.caption("Manage your account and platform settings.")

    user_id = st.session_state.get("user_id")

    if user_id is None:
        st.error("Your session is invalid. Please log in again.")
        return

    user = get_user_by_id(user_id)

    if user is None:
        st.error("User account not found.")
        return

    profile_tab, security_tab, company_tab = st.tabs(
        [
            "👤 Profile",
            "🔐 Security",
            "🏢 Company",
        ]
    )

    with profile_tab:
        st.subheader("Administrator Profile")

        with st.form("profile_form"):
            full_name = st.text_input(
                "Full Name",
                value=user.full_name,
            )

            username = st.text_input(
                "Username",
                value=user.username,
            )

            submitted = st.form_submit_button(
                "Save Profile",
                type="primary",
                width="stretch",
            )

        if submitted:
            if not full_name.strip() or not username.strip():
                st.warning("Full name and username are required.")
            else:
                try:
                    update_profile(
                        user_id=user.id,
                        full_name=full_name,
                        username=username,
                    )

                    st.session_state["full_name"] = full_name.strip()
                    st.session_state["username"] = username.strip()

                    st.success("Profile updated successfully.")
                    st.rerun()

                except ValueError as error:
                    st.error(str(error))

    with security_tab:
        st.subheader("Change Password")

        with st.form("password_form", clear_on_submit=True):
            current_password = st.text_input(
                "Current Password",
                type="password",
            )

            new_password = st.text_input(
                "New Password",
                type="password",
            )

            confirm_password = st.text_input(
                "Confirm New Password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Update Password",
                type="primary",
                width="stretch",
            )

        if submitted:
            if not current_password:
                st.warning("Enter your current password.")

            elif len(new_password) < 10:
                st.warning(
                    "Your new password must contain at least 10 characters."
                )

            elif new_password != confirm_password:
                st.warning("The new passwords do not match.")

            elif current_password == new_password:
                st.warning(
                    "Your new password must be different from the current password."
                )

            else:
                updated = change_password(
                    user_id=user.id,
                    current_password=current_password,
                    new_password=new_password,
                )

                if updated:
                    st.success(
                        "Password updated successfully. "
                        "Use the new password next time you sign in."
                    )
                else:
                    st.error("The current password is incorrect.")

    with company_tab:
        st.subheader("Company Information")

        st.info(
            "Company profile storage will be connected in the next business milestone."
        )

        st.text_input(
            "Company Name",
            value="Dawlat Global Imports & Trading",
            disabled=True,
        )

        st.text_input(
            "Platform Name",
            value="Dawlat Procurement Platform",
            disabled=True,
        )