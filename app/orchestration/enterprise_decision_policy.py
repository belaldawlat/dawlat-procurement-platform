"""Policy controls for the enterprise decision brain."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseDecisionPolicy:
    policy_id: str
    name: str
    version: str = "1.0.0"
    proceed_threshold: float = 80.0
    hold_threshold: float = 55.0
    reject_threshold: float = 30.0
    minimum_confidence: float = 75.0
    maximum_blocking_factors: int = 0
    escalate_on_critical_finding: bool = True
    require_human_approval_below_confidence: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Decision policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Decision policy name is required.")
        if not str(self.version or "").strip():
            raise ValueError("Decision policy version is required.")

        for name, value in {
            "proceed_threshold": self.proceed_threshold,
            "hold_threshold": self.hold_threshold,
            "reject_threshold": self.reject_threshold,
            "minimum_confidence": self.minimum_confidence,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100.")

        if not (
            self.reject_threshold
            <= self.hold_threshold
            <= self.proceed_threshold
        ):
            raise ValueError(
                "Thresholds must satisfy reject <= hold <= proceed."
            )

        if self.maximum_blocking_factors < 0:
            raise ValueError("Maximum blocking factors cannot be negative.")

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version).strip())