"""Policy configuration for the enterprise command center."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseCommandPolicy:
    """Immutable executive thresholds."""

    policy_id: str
    name: str
    version: str = "1.0.0"
    minimum_decision_score: float = 75.0
    minimum_autonomous_confidence: float = 80.0
    minimum_payment_clearance_rate: float = 95.0
    minimum_document_completeness_rate: float = 95.0
    minimum_on_time_shipment_rate: float = 90.0
    blocked_procurement_warning_count: int = 1
    blocked_procurement_critical_count: int = 5
    pending_approval_warning_count: int = 3
    delayed_shipment_warning_count: int = 2
    critical_risk_threshold: int = 1
    compensation_case_threshold: int = 1
    maximum_financial_exposure_ratio: float = 0.50
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Enterprise command policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise command policy name is required.")
        if not str(self.version or "").strip():
            raise ValueError("Enterprise command policy version is required.")

        for name, value in {
            "minimum_decision_score": self.minimum_decision_score,
            "minimum_autonomous_confidence": self.minimum_autonomous_confidence,
            "minimum_payment_clearance_rate": self.minimum_payment_clearance_rate,
            "minimum_document_completeness_rate": (
                self.minimum_document_completeness_rate
            ),
            "minimum_on_time_shipment_rate": self.minimum_on_time_shipment_rate,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100.")

        for name, value in {
            "blocked_procurement_warning_count": (
                self.blocked_procurement_warning_count
            ),
            "blocked_procurement_critical_count": (
                self.blocked_procurement_critical_count
            ),
            "pending_approval_warning_count": self.pending_approval_warning_count,
            "delayed_shipment_warning_count": (
                self.delayed_shipment_warning_count
            ),
            "critical_risk_threshold": self.critical_risk_threshold,
            "compensation_case_threshold": self.compensation_case_threshold,
        }.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative.")

        if (
            self.blocked_procurement_critical_count
            < self.blocked_procurement_warning_count
        ):
            raise ValueError(
                "Critical blocked-procurement threshold cannot be lower "
                "than the warning threshold."
            )

        if not 0 <= self.maximum_financial_exposure_ratio <= 1:
            raise ValueError(
                "Maximum financial exposure ratio must be between 0 and 1."
            )

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version).strip())