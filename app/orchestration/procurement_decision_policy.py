"""Policy configuration for procurement decision evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.procurement_decision_models import (
    ProcurementDecision,
)


@dataclass(frozen=True)
class ProcurementDecisionPolicy:
    """Immutable thresholds and outcome rules."""

    policy_id: str
    name: str
    version: str = "1.0.0"
    proceed_score_threshold: float = 80.0
    manual_review_score_threshold: float = 60.0
    maximum_supplier_risk_score: float = 60.0
    maximum_external_risk_score: float = 70.0
    maximum_landed_cost_budget_ratio: float = 1.05
    require_buyer_commitment: bool = True
    require_supplier_qualification: bool = True
    require_compliant_quotation: bool = True
    require_approval: bool = True
    require_payment_clearance: bool = True
    require_documents_complete: bool = True
    require_shipment_readiness: bool = False
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate policy configuration."""

        policy_id = str(self.policy_id or "").strip()
        name = str(self.name or "").strip()
        version = str(self.version or "").strip()

        if not policy_id:
            raise ValueError(
                "Procurement decision policy ID is required."
            )

        if not name:
            raise ValueError(
                "Procurement decision policy name is required."
            )

        if not version:
            raise ValueError(
                "Procurement decision policy version is required."
            )

        for label, value in {
            "proceed_score_threshold": (
                self.proceed_score_threshold
            ),
            "manual_review_score_threshold": (
                self.manual_review_score_threshold
            ),
            "maximum_supplier_risk_score": (
                self.maximum_supplier_risk_score
            ),
            "maximum_external_risk_score": (
                self.maximum_external_risk_score
            ),
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(
                    f"{label} must be between 0 and 100."
                )

        if (
            self.manual_review_score_threshold
            > self.proceed_score_threshold
        ):
            raise ValueError(
                "Manual-review threshold cannot exceed "
                "the proceed threshold."
            )

        if self.maximum_landed_cost_budget_ratio <= 0:
            raise ValueError(
                "Maximum landed-cost budget ratio must be positive."
            )

        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)

    def resolve_decision(
        self,
        *,
        score: float,
        has_critical_blocker: bool,
        has_blocker: bool,
    ) -> ProcurementDecision:
        """Resolve final decision deterministically."""

        if not self.enabled:
            return ProcurementDecision.REJECT

        if has_critical_blocker:
            return ProcurementDecision.REJECT

        if has_blocker:
            return ProcurementDecision.HOLD

        if score >= self.proceed_score_threshold:
            return ProcurementDecision.PROCEED

        if score >= self.manual_review_score_threshold:
            return ProcurementDecision.MANUAL_REVIEW

        return ProcurementDecision.REJECT