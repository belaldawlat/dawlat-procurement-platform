"""Security-focused validation for application configuration."""

from __future__ import annotations

from dataclasses import dataclass

from app.config.constants import MINIMUM_SECRET_LENGTH
from app.config.settings import ApplicationSettings


@dataclass(frozen=True)
class ConfigurationValidationResult:
    """Immutable configuration validation result."""

    is_valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


class ConfigurationValidationError(RuntimeError):
    """Raised when application configuration is unsafe."""

    def __init__(self, errors: tuple[str, ...]) -> None:
        message = "Unsafe application configuration:\n"
        message += "\n".join(f"- {error}" for error in errors)
        super().__init__(message)
        self.errors = errors


def validate_settings(
    settings: ApplicationSettings,
) -> ConfigurationValidationResult:
    """Validate configuration against security requirements."""

    errors: list[str] = []
    warnings: list[str] = []

    if not settings.require_authentication:
        errors.append(
            "Authentication cannot be disabled."
        )

    if settings.allow_public_access:
        errors.append(
            "Public platform access is prohibited."
        )

    if settings.allow_public_registration:
        errors.append(
            "Public user registration is prohibited."
        )

    if (
        settings.feature_flags.public_platform_access_enabled
    ):
        errors.append(
            "The public platform access feature must remain disabled."
        )

    if (
        settings.feature_flags.public_registration_enabled
    ):
        errors.append(
            "The public registration feature must remain disabled."
        )

    if (
        settings.feature_flags
        .autonomous_supplier_payment_enabled
    ):
        errors.append(
            "Autonomous supplier payments are prohibited."
        )

    if (
        settings.feature_flags
        .autonomous_contract_execution_enabled
    ):
        errors.append(
            "Autonomous contract execution is prohibited."
        )

    if settings.session_timeout_minutes > 60:
        warnings.append(
            "Session timeout exceeds the recommended maximum "
            "of 60 minutes."
        )

    if settings.max_login_attempts > 5:
        warnings.append(
            "Maximum login attempts exceed the recommended "
            "security threshold."
        )

    if settings.environment.requires_strict_security:
        if settings.debug_enabled:
            errors.append(
                "Debug mode must be disabled in staging "
                "and production."
            )

        if not settings.owner_email:
            errors.append(
                "Owner email must be configured."
            )

        if not settings.database_url:
            errors.append(
                "A production database URL must be configured."
            )

        if len(settings.secret_key) < MINIMUM_SECRET_LENGTH:
            errors.append(
                "Secret key does not meet the minimum length."
            )

        if (
            len(settings.encryption_key)
            < MINIMUM_SECRET_LENGTH
        ):
            errors.append(
                "Encryption key does not meet the minimum length."
            )

        if not settings.require_mfa:
            errors.append(
                "MFA must be required in staging and production."
            )

        if not settings.secure_cookies_enabled:
            errors.append(
                "Secure cookies must be enabled."
            )

        if not settings.https_required:
            errors.append(
                "HTTPS must be required."
            )

        if not settings.feature_flags.audit_logging_enabled:
            errors.append(
                "Audit logging must be enabled."
            )

    return ConfigurationValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def enforce_valid_settings(
    settings: ApplicationSettings,
) -> None:
    """Stop application startup when settings are unsafe."""

    result = validate_settings(settings)

    if not result.is_valid:
        raise ConfigurationValidationError(result.errors)