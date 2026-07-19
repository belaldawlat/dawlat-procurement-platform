"""Policy configuration for the enterprise AI decision network."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnterpriseAIDecisionPolicy:
    policy_id: str
    name: str
    version: str = "1.0.0"
    proceed_threshold: float = 80.0
    manual_review_threshold: float = 60.0
    reject_threshold: float = 35.0
    minimum_confidence: float = 75.0
    maximum_blocking_signals: int = 0
    require_human_approval_below_confidence: bool = True
    allow_replay: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Enterprise AI decision policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Enterprise AI decision policy name is required.")
        if not str(self.version or "").strip():
            raise ValueError("Enterprise AI decision policy version is required.")

        for name, value in {
            "proceed_threshold": self.proceed_threshold,
            "manual_review_threshold": self.manual_review_threshold,
            "reject_threshold": self.reject_threshold,
            "minimum_confidence": self.minimum_confidence,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100.")

        if not (
            self.reject_threshold
            <= self.manual_review_threshold
            <= self.proceed_threshold
        ):
            raise ValueError(
                "Decision thresholds must satisfy reject <= manual review <= proceed."
            )

        if self.maximum_blocking_signals < 0:
            raise ValueError("Maximum blocking signals cannot be negative.")

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version).strip())