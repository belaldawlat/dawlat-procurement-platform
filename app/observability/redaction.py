"""Sensitive data redaction for enterprise logging."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


REDACTED_VALUE = "[REDACTED]"

SENSITIVE_KEYWORDS = frozenset(
    {
        "password",
        "passphrase",
        "secret",
        "secret_key",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "authorization",
        "cookie",
        "session",
        "session_id",
        "encryption_key",
        "private_key",
        "database_url",
        "connection_string",
        "credit_card",
        "card_number",
        "cvv",
        "pin",
    }
)


def is_sensitive_key(key: Any) -> bool:
    """Return whether a mapping key represents sensitive information."""

    normalised = str(key or "").strip().lower().replace("-", "_")

    return any(
        keyword == normalised or keyword in normalised
        for keyword in SENSITIVE_KEYWORDS
    )


def redact_value(value: Any) -> Any:
    """Recursively redact sensitive values from structured data."""

    if isinstance(value, Mapping):
        return {
            str(key): (
                REDACTED_VALUE
                if is_sensitive_key(key)
                else redact_value(item)
            )
            for key, item in value.items()
        }

    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)

    if isinstance(value, list):
        return [redact_value(item) for item in value]

    if isinstance(value, set):
        return sorted(
            (redact_value(item) for item in value),
            key=str,
        )

    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [redact_value(item) for item in value]

    return value


def redact_mapping(
    values: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a redacted dictionary suitable for safe logging."""

    if not values:
        return {}

    redacted = redact_value(values)

    if not isinstance(redacted, dict):
        return {}

    return redacted