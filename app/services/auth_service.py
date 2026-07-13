import os
from typing import Optional

import bcrypt
from dotenv import load_dotenv

from database.connection import get_connection
from models.user import User


load_dotenv()

VALID_ROLES = [
    "Admin",
    "Procurement Manager",
    "Sales Manager",
    "Finance Manager",
    "Viewer",
]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def row_to_user(row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        full_name=row["full_name"],
        password_hash=row["password_hash"],
        role=row["role"],
        is_active=bool(row["is_active"]),
    )


def get_user_by_username(username: str) -> Optional[User]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                username,
                full_name,
                password_hash,
                role,
                is_active
            FROM users
            WHERE LOWER(username) = LOWER(?)
            """,
            (username.strip(),),
        ).fetchone()

    return row_to_user(row) if row else None


def get_user_by_id(user_id: int) -> Optional[User]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                username,
                full_name,
                password_hash,
                role,
                is_active
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    return row_to_user(row) if row else None


def get_all_users() -> list[User]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                username,
                full_name,
                password_hash,
                role,
                is_active
            FROM users
            ORDER BY full_name ASC
            """
        ).fetchall()

    return [row_to_user(row) for row in rows]


def authenticate_user(username: str, password: str) -> Optional[User]:
    user = get_user_by_username(username)

    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def create_user(
    username: str,
    full_name: str,
    password: str,
    role: str,
) -> int:
    if not username.strip() or not full_name.strip():
        raise ValueError("Username and full name are required.")

    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters.")

    if role not in VALID_ROLES:
        raise ValueError("Invalid user role.")

    if get_user_by_username(username) is not None:
        raise ValueError("That username is already in use.")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO users (
                username,
                full_name,
                password_hash,
                role,
                is_active
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username.strip(),
                full_name.strip(),
                hash_password(password),
                role,
                1,
            ),
        )

        return int(cursor.lastrowid)


def update_profile(
    user_id: int,
    full_name: str,
    username: str,
) -> None:
    existing_user = get_user_by_username(username)

    if existing_user is not None and existing_user.id != user_id:
        raise ValueError("That username is already in use.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET full_name = ?,
                username = ?
            WHERE id = ?
            """,
            (
                full_name.strip(),
                username.strip(),
                user_id,
            ),
        )


def update_user_role(user_id: int, role: str) -> None:
    if role not in VALID_ROLES:
        raise ValueError("Invalid user role.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET role = ?
            WHERE id = ?
            """,
            (role, user_id),
        )


def set_user_active(user_id: int, is_active: bool) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET is_active = ?
            WHERE id = ?
            """,
            (1 if is_active else 0, user_id),
        )


def reset_user_password(user_id: int, new_password: str) -> None:
    if len(new_password) < 10:
        raise ValueError("Password must contain at least 10 characters.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
            """,
            (
                hash_password(new_password),
                user_id,
            ),
        )


def change_password(
    user_id: int,
    current_password: str,
    new_password: str,
) -> bool:
    user = get_user_by_id(user_id)

    if user is None:
        return False

    if not verify_password(current_password, user.password_hash):
        return False

    reset_user_password(user_id, new_password)
    return True


def delete_user(user_id: int, current_user_id: int) -> None:
    if user_id == current_user_id:
        raise ValueError("You cannot delete your own account.")

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM users
            WHERE id = ?
            """,
            (user_id,),
        )


def ensure_admin_user() -> None:
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    full_name = os.getenv("ADMIN_FULL_NAME", "Belal Dawlat").strip()

    if not username or not password:
        return

    if get_user_by_username(username) is not None:
        return

    create_user(
        username=username,
        full_name=full_name,
        password=password,
        role="Admin",
    )