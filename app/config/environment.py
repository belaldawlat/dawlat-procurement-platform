"""Runtime environment definitions and environment parsing."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ApplicationEnvironment(str, Enum):
    """Supported application runtime environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def parse(cls, value: Any) -> "ApplicationEnvironment":
        """Return a validated application environment."""

        normalised = str(value or "").strip().lower()

        if not normalised:
            return cls.DEVELOPMENT

        try:
            return cls(normalised)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(
                f"Unsupported application environment: {value!r}. "
                f"Allowed values: {allowed}."
            ) from exc

    @property
    def is_development(self) -> bool:
        """Return whether this is the development environment."""

        return self is ApplicationEnvironment.DEVELOPMENT

    @property
    def is_test(self) -> bool:
        """Return whether this is the test environment."""

        return self is ApplicationEnvironment.TEST

    @property
    def is_staging(self) -> bool:
        """Return whether this is the staging environment."""

        return self is ApplicationEnvironment.STAGING

    @property
    def is_production(self) -> bool:
        """Return whether this is the production environment."""

        return self is ApplicationEnvironment.PRODUCTION

    @property
    def requires_strict_security(self) -> bool:
        """Return whether strict production controls are required."""

        return self in {
            ApplicationEnvironment.STAGING,
            ApplicationEnvironment.PRODUCTION,
        }