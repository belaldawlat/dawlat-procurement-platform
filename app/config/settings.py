"""Central immutable settings for the Dawlat enterprise platform."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Mapping

from app.config.constants import (
    APPLICATION_NAME,
    COMPANY_NAME,
    DEFAULT_ACCOUNT_LOCKOUT_MINUTES,
    DEFAULT_CURRENCY,
    DEFAULT_MAX_LOGIN_ATTEMPTS,
    DEFAULT_SESSION_TIMEOUT_MINUTES,
    DEFAULT_TIMEZONE,
)
from app.config.environment import ApplicationEnvironment
from app.config.feature_flags import FeatureFlags


_TRUE_VALUES = frozenset({"1", "true", "yes", "on", "enabled"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", "disabled"})


def _read_boolean(
    value: str | None,
    *,
    default: bool,
) -> bool:
    """Parse a strict boolean environment value."""

    if value is None or not value.strip():
        return default

    normalised = value.strip().lower()

    if normalised in _TRUE_VALUES:
        return True

    if normalised in _FALSE_VALUES:
        return False

    raise ValueError(f"Invalid boolean value: {value!r}.")


def _read_integer(
    value: str | None,
    *,
    default: int,
    minimum: int,
) -> int:
    """Parse a bounded integer environment value."""

    if value is None or not value.strip():
        return default

    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid integer value: {value!r}."
        ) from exc

    if parsed < minimum:
        raise ValueError(
            f"Integer value must be at least {minimum}: {parsed}."
        )

    return parsed


@dataclass(frozen=True)
class ApplicationSettings:
    """Immutable, validated application settings."""

    application_name: str = APPLICATION_NAME
    company_name: str = COMPANY_NAME

    environment: ApplicationEnvironment = (
        ApplicationEnvironment.DEVELOPMENT
    )

    debug_enabled: bool = False

    owner_email: str = ""
    database_url: str = ""
    secret_key: str = ""
    encryption_key: str = ""

    default_currency: str = DEFAULT_CURRENCY
    default_timezone: str = DEFAULT_TIMEZONE

    require_authentication: bool = True
    require_mfa: bool = True
    allow_public_access: bool = False
    allow_public_registration: bool = False

    secure_cookies_enabled: bool = True
    https_required: bool = True

    session_timeout_minutes: int = (
        DEFAULT_SESSION_TIMEOUT_MINUTES
    )
    max_login_attempts: int = DEFAULT_MAX_LOGIN_ATTEMPTS
    account_lockout_minutes: int = (
        DEFAULT_ACCOUNT_LOCKOUT_MINUTES
    )

    feature_flags: FeatureFlags = field(
        default_factory=FeatureFlags
    )

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "ApplicationSettings":
        """Build settings from environment variables."""

        source = environ if environ is not None else os.environ

        environment = ApplicationEnvironment.parse(
            source.get("DAWLAT_ENVIRONMENT")
        )

        feature_flags = FeatureFlags(
            public_registration_enabled=_read_boolean(
                source.get(
                    "DAWLAT_PUBLIC_REGISTRATION_ENABLED"
                ),
                default=False,
            ),
            public_platform_access_enabled=_read_boolean(
                source.get(
                    "DAWLAT_PUBLIC_PLATFORM_ACCESS_ENABLED"
                ),
                default=False,
            ),
            autonomous_supplier_payment_enabled=_read_boolean(
                source.get(
                    "DAWLAT_AUTONOMOUS_SUPPLIER_PAYMENT_ENABLED"
                ),
                default=False,
            ),
            autonomous_contract_execution_enabled=_read_boolean(
                source.get(
                    "DAWLAT_AUTONOMOUS_CONTRACT_EXECUTION_ENABLED"
                ),
                default=False,
            ),
            external_api_access_enabled=_read_boolean(
                source.get(
                    "DAWLAT_EXTERNAL_API_ACCESS_ENABLED"
                ),
                default=False,
            ),
            experimental_ai_actions_enabled=_read_boolean(
                source.get(
                    "DAWLAT_EXPERIMENTAL_AI_ACTIONS_ENABLED"
                ),
                default=False,
            ),
            supplier_discovery_enabled=_read_boolean(
                source.get(
                    "DAWLAT_SUPPLIER_DISCOVERY_ENABLED"
                ),
                default=True,
            ),
            dashboard_intelligence_enabled=_read_boolean(
                source.get(
                    "DAWLAT_DASHBOARD_INTELLIGENCE_ENABLED"
                ),
                default=True,
            ),
            audit_logging_enabled=_read_boolean(
                source.get(
                    "DAWLAT_AUDIT_LOGGING_ENABLED"
                ),
                default=True,
            ),
            maintenance_mode_enabled=_read_boolean(
                source.get(
                    "DAWLAT_MAINTENANCE_MODE_ENABLED"
                ),
                default=False,
            ),
        )

        return cls(
            environment=environment,
            debug_enabled=_read_boolean(
                source.get("DAWLAT_DEBUG_ENABLED"),
                default=False,
            ),
            owner_email=str(
                source.get("DAWLAT_OWNER_EMAIL") or ""
            ).strip(),
            database_url=str(
                source.get("DAWLAT_DATABASE_URL") or ""
            ).strip(),
            secret_key=str(
                source.get("DAWLAT_SECRET_KEY") or ""
            ).strip(),
            encryption_key=str(
                source.get("DAWLAT_ENCRYPTION_KEY") or ""
            ).strip(),
            require_authentication=_read_boolean(
                source.get("DAWLAT_REQUIRE_AUTHENTICATION"),
                default=True,
            ),
            require_mfa=_read_boolean(
                source.get("DAWLAT_REQUIRE_MFA"),
                default=True,
            ),
            allow_public_access=_read_boolean(
                source.get("DAWLAT_ALLOW_PUBLIC_ACCESS"),
                default=False,
            ),
            allow_public_registration=_read_boolean(
                source.get(
                    "DAWLAT_ALLOW_PUBLIC_REGISTRATION"
                ),
                default=False,
            ),
            secure_cookies_enabled=_read_boolean(
                source.get(
                    "DAWLAT_SECURE_COOKIES_ENABLED"
                ),
                default=True,
            ),
            https_required=_read_boolean(
                source.get("DAWLAT_HTTPS_REQUIRED"),
                default=True,
            ),
            session_timeout_minutes=_read_integer(
                source.get(
                    "DAWLAT_SESSION_TIMEOUT_MINUTES"
                ),
                default=DEFAULT_SESSION_TIMEOUT_MINUTES,
                minimum=5,
            ),
            max_login_attempts=_read_integer(
                source.get("DAWLAT_MAX_LOGIN_ATTEMPTS"),
                default=DEFAULT_MAX_LOGIN_ATTEMPTS,
                minimum=1,
            ),
            account_lockout_minutes=_read_integer(
                source.get(
                    "DAWLAT_ACCOUNT_LOCKOUT_MINUTES"
                ),
                default=DEFAULT_ACCOUNT_LOCKOUT_MINUTES,
                minimum=1,
            ),
            feature_flags=feature_flags,
        )

    def safe_summary(self) -> dict[str, object]:
        """Return diagnostics without exposing secrets."""

        return {
            "application_name": self.application_name,
            "company_name": self.company_name,
            "environment": self.environment.value,
            "debug_enabled": self.debug_enabled,
            "owner_configured": bool(self.owner_email),
            "database_configured": bool(self.database_url),
            "secret_key_configured": bool(self.secret_key),
            "encryption_key_configured": bool(
                self.encryption_key
            ),
            "default_currency": self.default_currency,
            "default_timezone": self.default_timezone,
            "require_authentication": (
                self.require_authentication
            ),
            "require_mfa": self.require_mfa,
            "allow_public_access": self.allow_public_access,
            "allow_public_registration": (
                self.allow_public_registration
            ),
            "secure_cookies_enabled": (
                self.secure_cookies_enabled
            ),
            "https_required": self.https_required,
            "session_timeout_minutes": (
                self.session_timeout_minutes
            ),
            "max_login_attempts": self.max_login_attempts,
            "account_lockout_minutes": (
                self.account_lockout_minutes
            ),
            "feature_flags": self.feature_flags.as_dict(),
        }


@lru_cache(maxsize=1)
def get_settings() -> ApplicationSettings:
    """Return the shared application settings instance."""

    return ApplicationSettings.from_environment()


def clear_settings_cache() -> None:
    """Clear cached settings for tests and controlled reloads."""

    get_settings.cache_clear()