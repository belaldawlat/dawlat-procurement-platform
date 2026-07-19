"""Policy configuration for procurement intelligence scoring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcurementIntelligencePolicy:
    policy_id: str
    name: str
    version: str = "1.0.0"
    landed_cost_weight: float = 0.30
    quality_weight: float = 0.20
    reliability_weight: float = 0.20
    compliance_weight: float = 0.20
    lead_time_weight: float = 0.10
    maximum_acceptable_risk_score: float = 65.0
    critical_risk_score: float = 85.0
    urgent_shipment_delay_days: int = 7
    low_inventory_days_threshold: float = 21.0
    high_opportunity_score: float = 75.0
    minimum_margin_percentage: float = 10.0
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Procurement intelligence policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Procurement intelligence policy name is required.")
        if not str(self.version or "").strip():
            raise ValueError("Procurement intelligence policy version is required.")

        weights = (
            self.landed_cost_weight,
            self.quality_weight,
            self.reliability_weight,
            self.compliance_weight,
            self.lead_time_weight,
        )

        if any(weight < 0 for weight in weights):
            raise ValueError("Procurement intelligence weights cannot be negative.")

        if abs(sum(weights) - 1.0) > 0.000001:
            raise ValueError("Procurement intelligence weights must total 1.0.")

        for name, score in {
            "maximum_acceptable_risk_score": self.maximum_acceptable_risk_score,
            "critical_risk_score": self.critical_risk_score,
            "high_opportunity_score": self.high_opportunity_score,
        }.items():
            if not 0 <= score <= 100:
                raise ValueError(f"{name} must be between 0 and 100.")

        if self.critical_risk_score < self.maximum_acceptable_risk_score:
            raise ValueError(
                "Critical risk score cannot be lower than maximum acceptable risk."
            )

        if self.urgent_shipment_delay_days < 1:
            raise ValueError("Urgent shipment delay must be at least one day.")

        if self.low_inventory_days_threshold < 0:
            raise ValueError("Low inventory threshold cannot be negative.")

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version).strip())