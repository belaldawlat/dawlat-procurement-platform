"""Safety policy for the enterprise procurement orchestrator."""

from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.enterprise_models import EnterpriseCommand
from app.orchestration.procurement_decision_models import ProcurementDecision


@dataclass(frozen=True)
class EnterpriseOrchestrationPolicy:
    """Immutable enterprise coordination policy."""

    policy_id: str
    name: str
    version: str = "1.0.0"
    require_approval_before_execution: bool = True
    allow_execution_in_dry_run: bool = False
    allow_compensation: bool = True
    fail_closed_on_hold: bool = True
    fail_closed_on_manual_review: bool = True
    minimum_autonomous_confidence: float = 85.0
    enabled: bool = True

    def __post_init__(self) -> None:
        if not str(self.policy_id or "").strip():
            raise ValueError(
                "Enterprise orchestration policy ID is required."
            )

        if not str(self.name or "").strip():
            raise ValueError(
                "Enterprise orchestration policy name is required."
            )

        if not str(self.version or "").strip():
            raise ValueError(
                "Enterprise orchestration policy version is required."
            )

        if not 0 <= self.minimum_autonomous_confidence <= 100:
            raise ValueError(
                "Minimum autonomous confidence must be between 0 and 100."
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

    def command_for_decision(
        self,
        decision: ProcurementDecision,
    ) -> EnterpriseCommand:
        """Map a procurement decision to an enterprise command."""

        if decision is ProcurementDecision.PROCEED:
            return EnterpriseCommand.PROCEED

        if decision is ProcurementDecision.HOLD:
            return EnterpriseCommand.HOLD

        if decision is ProcurementDecision.REJECT:
            return EnterpriseCommand.REJECT

        return EnterpriseCommand.MANUAL_REVIEW