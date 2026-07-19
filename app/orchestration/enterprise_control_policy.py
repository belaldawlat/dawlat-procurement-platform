"""Policy configuration for the enterprise control tower."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseControlPolicy:
    """Immutable enterprise control thresholds."""

    policy_id: str
    name: str
    version: str = "1.0.0"
    minimum_decision_score: float = 70.0
    minimum_autonomous_confidence: float = 80.0
    maximum_supplier_risk_score: float = 65.0
    critical_supplier_risk_score: float = 85.0
    shipment_delay_warning_days: int = 3
    shipment_delay_critical_days: int = 10
    low_inventory_warning_days: float = 21.0
    low_inventory_critical_days: float = 7.0
    high_opportunity_score: float = 80.0
    minimum_margin_percentage: float = 10.0
    fail_closed_on_missing_payment: bool = True
    fail_closed_on_missing_documents: bool = True
    fail_closed_on_compensation_required: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError(
                "Enterprise control policy ID is required."
            )

        if not str(self.name or "").strip():
            raise ValueError(
                "Enterprise control policy name is required."
            )

        if not str(self.version or "").strip():
            raise ValueError(
                "Enterprise control policy version is required."
            )

        for name, value in {
            "minimum_decision_score": self.minimum_decision_score,
            "minimum_autonomous_confidence": (
                self.minimum_autonomous_confidence
            ),
            "maximum_supplier_risk_score": (
                self.maximum_supplier_risk_score
            ),
            "critical_supplier_risk_score": (
                self.critical_supplier_risk_score
            ),
            "high_opportunity_score": self.high_opportunity_score,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(
                    f"{name} must be between 0 and 100."
                )

        if (
            self.critical_supplier_risk_score
            < self.maximum_supplier_risk_score
        ):
            raise ValueError(
                "Critical supplier risk cannot be lower than "
                "maximum supplier risk."
            )

        if self.shipment_delay_warning_days < 0:
            raise ValueError(
                "Shipment warning delay cannot be negative."
            )

        if (
            self.shipment_delay_critical_days
            < self.shipment_delay_warning_days
        ):
            raise ValueError(
                "Critical shipment delay cannot be lower than "
                "warning shipment delay."
            )

        if self.low_inventory_critical_days < 0:
            raise ValueError(
                "Critical inventory days cannot be negative."
            )

        if (
            self.low_inventory_warning_days
            < self.low_inventory_critical_days
        ):
            raise ValueError(
                "Inventory warning threshold cannot be lower than "
                "the critical threshold."
            )

        object.__setattr__(
            self,
            "policy_id",
            str(self.policy_id).strip(),
        )
        object.__setattr__(
            self,
            "name",
            str(self.name).strip(),
        )
        object.__setattr__(
            self,
            "version",
            str(self.version).strip(),
        )