"""Policy controls for the autonomous procurement brain."""

from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.autonomous_procurement_models import (
    AutonomousAction,
    AutonomyMode,
)


@dataclass(frozen=True)
class AutonomousProcurementPolicy:
    policy_id: str
    name: str
    version: str = "1.0.0"
    default_mode: AutonomyMode = AutonomyMode.ADVISORY
    minimum_execution_confidence: float = 85.0
    require_human_approval_for_po: bool = True
    require_human_approval_for_supplier_selection: bool = True
    require_human_approval_for_compensation: bool = True
    fail_closed_on_missing_payment: bool = True
    fail_closed_on_missing_documents: bool = True
    fail_closed_on_high_risk: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError("Autonomous procurement policy ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Autonomous procurement policy name is required.")
        if not str(self.version or "").strip():
            raise ValueError("Autonomous procurement policy version is required.")
        if not 0 <= self.minimum_execution_confidence <= 100:
            raise ValueError(
                "Minimum execution confidence must be between 0 and 100."
            )

        object.__setattr__(self, "policy_id", str(self.policy_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "version", str(self.version).strip())

    def requires_human_approval(
        self,
        action: AutonomousAction,
    ) -> bool:
        if action is AutonomousAction.SELECT_SUPPLIER:
            return self.require_human_approval_for_supplier_selection
        if action is AutonomousAction.HANDOFF_SHIPMENT:
            return self.require_human_approval_for_po
        if action is AutonomousAction.START_COMPENSATION:
            return self.require_human_approval_for_compensation
        return action in {
            AutonomousAction.REQUEST_APPROVAL,
            AutonomousAction.MANUAL_REVIEW,
        }