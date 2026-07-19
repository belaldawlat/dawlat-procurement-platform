"""Enterprise procurement decision engine."""

from __future__ import annotations

from app.orchestration.procurement_decision_models import (
    DecisionCategory,
    DecisionFinding,
    DecisionSeverity,
    ProcurementDecisionContext,
)
from app.orchestration.procurement_decision_policy import (
    ProcurementDecisionPolicy,
)
from app.orchestration.procurement_decision_result import (
    ProcurementDecisionResult,
)
from app.orchestration.procurement_models import (
    BuyerReadiness,
    ProcurementCase,
    QuotationCompliance,
)


class ProcurementDecisionEngine:
    """Evaluate procurement readiness, risk and policy compliance."""

    def __init__(
        self,
        policy: ProcurementDecisionPolicy | None = None,
    ) -> None:
        self._policy = policy or ProcurementDecisionPolicy(
            policy_id="default-procurement-decision",
            name="Default Procurement Decision Policy",
        )

    @property
    def policy(self) -> ProcurementDecisionPolicy:
        """Return the active decision policy."""

        return self._policy

    def evaluate(
        self,
        case: ProcurementCase,
        *,
        context: ProcurementDecisionContext | None = None,
    ) -> ProcurementDecisionResult:
        """Evaluate a procurement case and return a final decision."""

        if not isinstance(case, ProcurementCase):
            raise TypeError(
                "Decision engine requires a ProcurementCase."
            )

        active_context = context or ProcurementDecisionContext()
        findings: list[DecisionFinding] = []
        score = 100.0

        score -= self._evaluate_buyer(case, findings)
        score -= self._evaluate_supplier(
            active_context,
            findings,
        )
        score -= self._evaluate_quotation(case, findings)
        score -= self._evaluate_financial(
            active_context,
            findings,
        )
        score -= self._evaluate_approval_payment(
            active_context,
            findings,
        )
        score -= self._evaluate_documents_shipment(
            active_context,
            findings,
        )
        score -= self._evaluate_risk(
            active_context,
            findings,
        )

        score = round(max(0.0, min(100.0, score)), 2)

        has_critical_blocker = any(
            finding.blocking
            and finding.severity is DecisionSeverity.CRITICAL
            for finding in findings
        )
        has_blocker = any(
            finding.blocking
            for finding in findings
        )

        decision = self._policy.resolve_decision(
            score=score,
            has_critical_blocker=has_critical_blocker,
            has_blocker=has_blocker,
        )

        ordered_findings = tuple(
            sorted(
                findings,
                key=lambda finding: (
                    not finding.blocking,
                    finding.severity.value,
                    finding.category.value,
                    finding.code,
                ),
            )
        )

        return ProcurementDecisionResult(
            case_id=case.case_id,
            decision=decision,
            score=score,
            findings=ordered_findings,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "procurement_status": case.status.value,
                "selected_quotation_id": (
                    case.selected_quotation_id
                ),
            },
        )

    def _evaluate_buyer(
        self,
        case: ProcurementCase,
        findings: list[DecisionFinding],
    ) -> float:
        penalty = 0.0

        if (
            self._policy.require_buyer_commitment
            and case.demand.readiness
            is not BuyerReadiness.COMMITTED
        ):
            findings.append(
                DecisionFinding(
                    code="BUYER_NOT_COMMITTED",
                    message=(
                        "Buyer commitment has not been confirmed."
                    ),
                    category=DecisionCategory.BUYER,
                    severity=DecisionSeverity.HIGH,
                    blocking=True,
                    recommendation=(
                        "Obtain documented buyer commitment "
                        "before proceeding."
                    ),
                )
            )
            penalty += 25.0

        return penalty

    def _evaluate_supplier(
        self,
        context: ProcurementDecisionContext,
        findings: list[DecisionFinding],
    ) -> float:
        if (
            self._policy.require_supplier_qualification
            and not context.supplier_qualified
        ):
            findings.append(
                DecisionFinding(
                    code="SUPPLIER_NOT_QUALIFIED",
                    message=(
                        "The selected supplier has not passed "
                        "qualification."
                    ),
                    category=DecisionCategory.SUPPLIER,
                    severity=DecisionSeverity.CRITICAL,
                    blocking=True,
                    recommendation=(
                        "Complete supplier qualification and "
                        "compliance checks."
                    ),
                )
            )
            return 30.0

        return 0.0

    def _evaluate_quotation(
        self,
        case: ProcurementCase,
        findings: list[DecisionFinding],
    ) -> float:
        selected = case.selected_quotation

        if selected is None:
            findings.append(
                DecisionFinding(
                    code="QUOTATION_NOT_SELECTED",
                    message=(
                        "No supplier quotation has been selected."
                    ),
                    category=DecisionCategory.QUOTATION,
                    severity=DecisionSeverity.HIGH,
                    blocking=True,
                    recommendation=(
                        "Select the best compliant quotation."
                    ),
                )
            )
            return 20.0

        if (
            self._policy.require_compliant_quotation
            and selected.compliance
            is not QuotationCompliance.COMPLIANT
        ):
            findings.append(
                DecisionFinding(
                    code="SELECTED_QUOTATION_NON_COMPLIANT",
                    message=(
                        "The selected quotation is not compliant."
                    ),
                    category=DecisionCategory.COMPLIANCE,
                    severity=DecisionSeverity.CRITICAL,
                    blocking=True,
                    recommendation=(
                        "Select a compliant quotation or resolve "
                        "the compliance deficiencies."
                    ),
                )
            )
            return 30.0

        return 0.0

    def _evaluate_financial(
        self,
        context: ProcurementDecisionContext,
        findings: list[DecisionFinding],
    ) -> float:
        ratio = context.landed_cost_budget_ratio

        if (
            ratio is not None
            and ratio
            > self._policy.maximum_landed_cost_budget_ratio
        ):
            findings.append(
                DecisionFinding(
                    code="LANDED_COST_EXCEEDS_BUDGET",
                    message=(
                        "Estimated landed cost exceeds the "
                        "approved budget tolerance."
                    ),
                    category=DecisionCategory.FINANCIAL,
                    severity=DecisionSeverity.HIGH,
                    blocking=True,
                    recommendation=(
                        "Renegotiate price, freight or buyer budget."
                    ),
                    metadata={
                        "ratio": ratio,
                        "maximum_ratio": (
                            self._policy
                            .maximum_landed_cost_budget_ratio
                        ),
                    },
                )
            )
            return 20.0

        return 0.0

    def _evaluate_approval_payment(
        self,
        context: ProcurementDecisionContext,
        findings: list[DecisionFinding],
    ) -> float:
        penalty = 0.0

        if self._policy.require_approval and not context.approval_satisfied:
            findings.append(
                DecisionFinding(
                    code="COMMERCIAL_APPROVAL_PENDING",
                    message=(
                        "Commercial approval has not been satisfied."
                    ),
                    category=DecisionCategory.APPROVAL,
                    severity=DecisionSeverity.HIGH,
                    blocking=True,
                    recommendation=(
                        "Complete the required approval chain."
                    ),
                )
            )
            penalty += 15.0

        if (
            self._policy.require_payment_clearance
            and not context.buyer_payment_cleared
        ):
            findings.append(
                DecisionFinding(
                    code="BUYER_PAYMENT_NOT_CLEARED",
                    message=(
                        "Buyer funds have not been confirmed as cleared."
                    ),
                    category=DecisionCategory.PAYMENT,
                    severity=DecisionSeverity.CRITICAL,
                    blocking=True,
                    recommendation=(
                        "Do not issue the supplier purchase order "
                        "until buyer funds are cleared."
                    ),
                )
            )
            penalty += 25.0

        return penalty

    def _evaluate_documents_shipment(
        self,
        context: ProcurementDecisionContext,
        findings: list[DecisionFinding],
    ) -> float:
        penalty = 0.0

        if (
            self._policy.require_documents_complete
            and not context.documents_complete
        ):
            findings.append(
                DecisionFinding(
                    code="DOCUMENTS_INCOMPLETE",
                    message=(
                        "Required procurement or compliance "
                        "documents are incomplete."
                    ),
                    category=DecisionCategory.DATA_QUALITY,
                    severity=DecisionSeverity.HIGH,
                    blocking=True,
                    recommendation=(
                        "Complete and verify all mandatory documents."
                    ),
                )
            )
            penalty += 15.0

        if (
            self._policy.require_shipment_readiness
            and not context.shipment_ready
        ):
            findings.append(
                DecisionFinding(
                    code="SHIPMENT_NOT_READY",
                    message=(
                        "Shipment handoff requirements are incomplete."
                    ),
                    category=DecisionCategory.SHIPMENT,
                    severity=DecisionSeverity.MEDIUM,
                    blocking=True,
                    recommendation=(
                        "Complete freight, booking and document setup."
                    ),
                )
            )
            penalty += 10.0

        return penalty

    def _evaluate_risk(
        self,
        context: ProcurementDecisionContext,
        findings: list[DecisionFinding],
    ) -> float:
        penalty = 0.0

        if (
            context.supplier_risk_score
            > self._policy.maximum_supplier_risk_score
        ):
            findings.append(
                DecisionFinding(
                    code="SUPPLIER_RISK_TOO_HIGH",
                    message=(
                        "Supplier risk exceeds the permitted threshold."
                    ),
                    category=DecisionCategory.RISK,
                    severity=DecisionSeverity.HIGH,
                    blocking=True,
                    recommendation=(
                        "Escalate for manual review or choose a "
                        "lower-risk supplier."
                    ),
                    metadata={
                        "risk_score": context.supplier_risk_score,
                        "maximum_score": (
                            self._policy
                            .maximum_supplier_risk_score
                        ),
                    },
                )
            )
            penalty += 20.0

        if (
            context.external_risk_score
            > self._policy.maximum_external_risk_score
        ):
            findings.append(
                DecisionFinding(
                    code="EXTERNAL_RISK_TOO_HIGH",
                    message=(
                        "External market or logistics risk exceeds "
                        "the permitted threshold."
                    ),
                    category=DecisionCategory.RISK,
                    severity=DecisionSeverity.HIGH,
                    blocking=True,
                    recommendation=(
                        "Review market, route, sanctions, insurance "
                        "and logistics risks."
                    ),
                    metadata={
                        "risk_score": context.external_risk_score,
                        "maximum_score": (
                            self._policy
                            .maximum_external_risk_score
                        ),
                    },
                )
            )
            penalty += 15.0

        return penalty


_default_procurement_decision_engine = (
    ProcurementDecisionEngine()
)


def get_procurement_decision_engine() -> ProcurementDecisionEngine:
    """Return the shared procurement decision engine."""

    return _default_procurement_decision_engine