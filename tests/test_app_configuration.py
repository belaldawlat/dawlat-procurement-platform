"""Tests for Phase 20 Package A application configuration."""

from __future__ import annotations

import pytest

from app.config.environment import ApplicationEnvironment
from app.config.feature_flags import FeatureFlags
from app.config.settings import ApplicationSettings
from app.config.validation import (
    ConfigurationValidationError,
    enforce_valid_settings,
    validate_settings,
)


def test_default_environment_is_development() -> None:
    settings = ApplicationSettings.from_environment({})

    assert (
        settings.environment
        is ApplicationEnvironment.DEVELOPMENT
    )


def test_default_configuration_is_private() -> None:
    settings = ApplicationSettings.from_environment({})

    assert settings.require_authentication is True
    assert settings.require_mfa is True
    assert settings.allow_public_access is False
    assert settings.allow_public_registration is False


def test_high_risk_features_are_disabled_by_default() -> None:
    flags = FeatureFlags()

    assert flags.public_registration_enabled is False
    assert flags.public_platform_access_enabled is False
    assert flags.autonomous_supplier_payment_enabled is False
    assert flags.autonomous_contract_execution_enabled is False
    assert flags.external_api_access_enabled is False


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ValueError):
        ApplicationEnvironment.parse("unsafe-environment")


def test_invalid_boolean_is_rejected() -> None:
    with pytest.raises(ValueError):
        ApplicationSettings.from_environment(
            {
                "DAWLAT_DEBUG_ENABLED": "sometimes",
            }
        )


def test_invalid_integer_is_rejected() -> None:
    with pytest.raises(ValueError):
        ApplicationSettings.from_environment(
            {
                "DAWLAT_SESSION_TIMEOUT_MINUTES": "invalid",
            }
        )


def test_public_access_is_rejected() -> None:
    settings = ApplicationSettings(
        allow_public_access=True,
    )

    result = validate_settings(settings)

    assert result.is_valid is False
    assert "Public platform access is prohibited." in (
        result.errors
    )


def test_authentication_cannot_be_disabled() -> None:
    settings = ApplicationSettings(
        require_authentication=False,
    )

    result = validate_settings(settings)

    assert result.is_valid is False
    assert "Authentication cannot be disabled." in result.errors


def test_autonomous_supplier_payment_is_rejected() -> None:
    settings = ApplicationSettings(
        feature_flags=FeatureFlags(
            autonomous_supplier_payment_enabled=True,
        )
    )

    result = validate_settings(settings)

    assert result.is_valid is False


def test_safe_summary_does_not_expose_secrets() -> None:
    settings = ApplicationSettings(
        secret_key="secret-value",
        encryption_key="encryption-value",
        database_url="sqlite:///private.db",
        owner_email="owner@example.com",
    )

    summary = settings.safe_summary()

    assert "secret-value" not in summary.values()
    assert "encryption-value" not in summary.values()
    assert "sqlite:///private.db" not in summary.values()
    assert "owner@example.com" not in summary.values()


def test_production_requires_owner_identity() -> None:
    settings = ApplicationSettings(
        environment=ApplicationEnvironment.PRODUCTION,
        database_url="postgresql://private",
        secret_key="s" * 40,
        encryption_key="e" * 40,
    )

    result = validate_settings(settings)

    assert result.is_valid is False
    assert "Owner email must be configured." in result.errors


def test_production_rejects_debug_mode() -> None:
    settings = ApplicationSettings(
        environment=ApplicationEnvironment.PRODUCTION,
        debug_enabled=True,
        owner_email="owner@example.com",
        database_url="postgresql://private",
        secret_key="s" * 40,
        encryption_key="e" * 40,
    )

    result = validate_settings(settings)

    assert result.is_valid is False
    assert (
        "Debug mode must be disabled in staging "
        "and production."
    ) in result.errors


def test_secure_production_configuration_is_valid() -> None:
    settings = ApplicationSettings(
        environment=ApplicationEnvironment.PRODUCTION,
        owner_email="owner@example.com",
        database_url="postgresql://private",
        secret_key="s" * 40,
        encryption_key="e" * 40,
        debug_enabled=False,
        require_authentication=True,
        require_mfa=True,
        allow_public_access=False,
        allow_public_registration=False,
        secure_cookies_enabled=True,
        https_required=True,
        feature_flags=FeatureFlags(
            audit_logging_enabled=True,
        ),
    )

    result = validate_settings(settings)

    assert result.is_valid is True
    assert result.errors == ()


def test_enforcement_raises_for_unsafe_settings() -> None:
    settings = ApplicationSettings(
        allow_public_registration=True,
    )

    with pytest.raises(ConfigurationValidationError):
        enforce_valid_settings(settings)


def test_environment_values_are_loaded() -> None:
    settings = ApplicationSettings.from_environment(
        {
            "DAWLAT_ENVIRONMENT": "test",
            "DAWLAT_SESSION_TIMEOUT_MINUTES": "20",
            "DAWLAT_MAX_LOGIN_ATTEMPTS": "3",
            "DAWLAT_ACCOUNT_LOCKOUT_MINUTES": "45",
        }
    )

    assert settings.environment is ApplicationEnvironment.TEST
    assert settings.session_timeout_minutes == 20
    assert settings.max_login_attempts == 3
    assert settings.account_lockout_minutes == 45