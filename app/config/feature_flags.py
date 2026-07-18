"""Secure feature-flag definitions for controlled platform capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class FeatureFlags:
    """Immutable platform feature flags.

    High-risk and externally accessible capabilities are disabled by default.
    """

    public_registration_enabled: bool = False
    public_platform_access_enabled: bool = False
    autonomous_supplier_payment_enabled: bool = False
    autonomous_contract_execution_enabled: bool = False
    external_api_access_enabled: bool = False
    experimental_ai_actions_enabled: bool = False
    supplier_discovery_enabled: bool = True
    dashboard_intelligence_enabled: bool = True
    audit_logging_enabled: bool = True
    maintenance_mode_enabled: bool = False

    def as_dict(self) -> dict[str, bool]:
        """Return a serialisable feature-flag mapping."""

        return {
            "public_registration_enabled": self.public_registration_enabled,
            "public_platform_access_enabled": (
                self.public_platform_access_enabled
            ),
            "autonomous_supplier_payment_enabled": (
                self.autonomous_supplier_payment_enabled
            ),
            "autonomous_contract_execution_enabled": (
                self.autonomous_contract_execution_enabled
            ),
            "external_api_access_enabled": (
                self.external_api_access_enabled
            ),
            "experimental_ai_actions_enabled": (
                self.experimental_ai_actions_enabled
            ),
            "supplier_discovery_enabled": (
                self.supplier_discovery_enabled
            ),
            "dashboard_intelligence_enabled": (
                self.dashboard_intelligence_enabled
            ),
            "audit_logging_enabled": self.audit_logging_enabled,
            "maintenance_mode_enabled": (
                self.maintenance_mode_enabled
            ),
        }

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, bool] | None,
    ) -> "FeatureFlags":
        """Create feature flags from a trusted mapping."""

        if not values:
            return cls()

        valid_fields = cls.__dataclass_fields__

        unexpected = sorted(
            key
            for key in values
            if key not in valid_fields
        )

        if unexpected:
            raise ValueError(
                "Unsupported feature flags: "
                + ", ".join(unexpected)
            )

        return cls(
            **{
                key: bool(value)
                for key, value in values.items()
            }
        )