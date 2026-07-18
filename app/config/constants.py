"""Application-wide constants for the Dawlat enterprise platform."""

from __future__ import annotations

from typing import Final


APPLICATION_NAME: Final[str] = "Dawlat Procurement Platform"
COMPANY_NAME: Final[str] = "Dawlat Global Imports & Trading"

DEFAULT_CURRENCY: Final[str] = "AUD"
DEFAULT_TIMEZONE: Final[str] = "Australia/Melbourne"

DEFAULT_SESSION_TIMEOUT_MINUTES: Final[int] = 30
DEFAULT_MAX_LOGIN_ATTEMPTS: Final[int] = 5
DEFAULT_ACCOUNT_LOCKOUT_MINUTES: Final[int] = 30

MINIMUM_SECRET_LENGTH: Final[int] = 32
MINIMUM_PASSWORD_LENGTH: Final[int] = 14

SUPPORTED_ENVIRONMENTS: Final[tuple[str, ...]] = (
    "development",
    "test",
    "staging",
    "production",
)

SENSITIVE_SETTING_NAMES: Final[frozenset[str]] = frozenset(
    {
        "database_url",
        "secret_key",
        "encryption_key",
        "owner_email",
    }
)