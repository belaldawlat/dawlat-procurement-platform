import streamlit as st

from services.auth_service import (
    VALID_ROLES,
    create_user,
    delete_user,
    get_all_users,
    reset_user_password,
    set_user_active,
    update_user_role,
)


def show() -> None:
    st.title("👥 User Management")
    st.caption("Create users, assign roles, manage access, and reset passwords.")

    current_role = st.session_state.get("role")

    if current_role != "Admin":
        st.error("Only administrators can access User Management.")
        return

    create_tab, manage_tab = st.tabs(
        [
            "➕ Create User",
            "📋 Manage Users",
        ]
    )

    with create_tab:
        show_create_user()

    with manage_tab:
        show_manage_users()


def show_create_user() -> None:
    st.subheader("Create New User")

    with st.form("create_user_form", clear_on_submit=True):
        full_name = st.text_input("Full Name")
        username = st.text_input("Username")
        role = st.selectbox("Role", VALID_ROLES)
        password = st.text_input("Temporary Password", type="password")
        confirm_password = st.text_input(
            "Confirm Temporary Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Create User",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if password != confirm_password:
        st.warning("The passwords do not match.")
        return

    try:
        user_id = create_user(
            username=username,
            full_name=full_name,
            password=password,
            role=role,
        )

        st.success(
            f"User created successfully. User ID: {user_id}"
        )

    except ValueError as error:
        st.error(str(error))


def show_manage_users() -> None:
    st.subheader("User Directory")

    users = get_all_users()

    if not users:
        st.info("No users found.")
        return

    table_data = [
        {
            "ID": user.id,
            "Full Name": user.full_name,
            "Username": user.username,
            "Role": user.role,
            "Status": "Active" if user.is_active else "Inactive",
        }
        for user in users
    ]

    st.dataframe(
        table_data,
        hide_index=True,
        use_container_width=True,
    )

    selected_user = st.selectbox(
        "Select user",
        options=users,
        format_func=lambda user: (
            f"{user.full_name} — {user.username}"
        ),
    )

    st.markdown("---")

    st.subheader("Role and Access")

    role = st.selectbox(
        "Role",
        VALID_ROLES,
        index=VALID_ROLES.index(selected_user.role),
        key=f"role_{selected_user.id}",
    )

    is_active = st.checkbox(
        "Active account",
        value=selected_user.is_active,
        key=f"active_{selected_user.id}",
    )

    if st.button(
        "Save Access Changes",
        type="primary",
        key=f"save_access_{selected_user.id}",
    ):
        update_user_role(selected_user.id, role)
        set_user_active(selected_user.id, is_active)
        st.success("User access updated successfully.")
        st.rerun()

    st.markdown("---")

    st.subheader("Reset Password")

    new_password = st.text_input(
        "New Password",
        type="password",
        key=f"reset_password_{selected_user.id}",
    )

    confirm_password = st.text_input(
        "Confirm New Password",
        type="password",
        key=f"confirm_reset_password_{selected_user.id}",
    )

    if st.button(
        "Reset Password",
        key=f"reset_button_{selected_user.id}",
    ):
        if new_password != confirm_password:
            st.warning("The passwords do not match.")

        else:
            try:
                reset_user_password(
                    selected_user.id,
                    new_password,
                )

                st.success("Password reset successfully.")

            except ValueError as error:
                st.error(str(error))

    st.markdown("---")

    st.subheader("Delete User")

    confirm_delete = st.checkbox(
        f"Confirm deletion of {selected_user.full_name}",
        key=f"delete_confirm_{selected_user.id}",
    )

    if st.button(
        "Delete User",
        disabled=not confirm_delete,
        key=f"delete_user_{selected_user.id}",
    ):
        try:
            delete_user(
                user_id=selected_user.id,
                current_user_id=st.session_state["user_id"],
            )

            st.success("User deleted successfully.")
            st.rerun()

        except ValueError as error:
            st.error(str(error))