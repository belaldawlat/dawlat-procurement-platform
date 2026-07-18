"""
Enterprise Decision Engine for the Dawlat AI Procurement Intelligence Platform.

This engine is the governed decision brain used by every major module.

Responsibilities:
- combine buyer demand, supplier offers, landed cost, logistics and risk;
- enforce buyer-confirmation and cleared-funds controls;
- protect Dawlat Global margin;
- block unsafe supplier commitments and payment releases;
- produce explainable, auditable recommendations;
- remain read-only until a human approves an operational action.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from models.decision import (
    ApprovalRecord,
    ApprovalStatus,
    BuyerCommercialCommitment,
    BuyerReadinessStatus,
    DecisionOutcome,
    DecisionType,
    EnterpriseDecision,
    EvidenceReference,
    EvidenceType,
    MarginProtection,
    PaymentMilestone,
    PaymentStage,
    PaymentStatus,
    RecommendedAction,
    RiskFinding,
    RiskSeverity,
    SupplierCommercialOffer,
    SupplierCommitmentStatus,
    default_deal_control_gates,
)
from services.procurement_intelligence_engine import (
    ProcurementDecision,
    ProcurementRequirement,
    evaluate_procurement_case,
)


class EnterpriseDecisionEngine:
    """
    Governed orchestration layer for commercial decisions.

    The engine never sends quotations, commits to suppliers, releases money,
    or changes records automatically. It returns a decision object that can be
    reviewed and approved by authorised users.
    """

    def evaluate_deal(
        self,
        *,
        requirement: ProcurementRequirement,
        buyer_commitment: BuyerCommercialCommitment | None = None,
        supplier_offer: SupplierCommercialOffer | None = None,
        margin_protection: MarginProtection | None = None,
        payment_milestones: list[PaymentMilestone] | None = None,
        approvals: list[ApprovalRecord] | None = None,
        include_live_discovery: bool = False,
        created_by: str = "System",
    ) -> EnterpriseDecision:
        procurement = evaluate_procurement_case(
            requirement,
            include_live_discovery=include_live_discovery,
        )

        buyer_commitment = buyer_commitment or self._default_buyer_commitment(
            requirement
        )

        supplier_offer = supplier_offer or self._best_supplier_offer(
            requirement,
            procurement,
        )

        margin_protection = margin_protection or self._margin_protection(
            requirement,
            procurement,
            supplier_offer,
        )

        payment_milestones = payment_milestones or []
        approvals = approvals or self._default_approvals(created_by)

        gates = self._evaluate_control_gates(
            buyer=buyer_commitment,
            supplier=supplier_offer,
            margin=margin_protection,
            milestones=payment_milestones,
            approvals=approvals,
        )

        risks = self._convert_risks(procurement)
        risks.extend(
            self._control_risks(
                buyer=buyer_commitment,
                supplier=supplier_offer,
                margin=margin_protection,
                milestones=payment_milestones,
            )
        )

        evidence = self._convert_evidence(procurement)

        outcome = self._determine_outcome(
            gates=gates,
            risks=risks,
            approvals=approvals,
        )

        recommendations = self._recommendations(
            outcome=outcome,
            gates=gates,
            risks=risks,
            procurement=procurement,
        )

        decision = EnterpriseDecision(
            decision_id=self._decision_id(),
            decision_type=DecisionType.DEAL_APPROVAL,
            outcome=outcome,
            title=f"Enterprise Deal Decision: {requirement.product}",
            executive_summary=self._summary(
                requirement=requirement,
                outcome=outcome,
                procurement=procurement,
                buyer=buyer_commitment,
                supplier=supplier_offer,
                margin=margin_protection,
            ),
            confidence_score=procurement.confidence_score,
            created_by=created_by,
            buyer_commitment=buyer_commitment,
            supplier_offer=supplier_offer,
            margin_protection=margin_protection,
            control_gates=gates,
            payment_milestones=payment_milestones,
            risks=risks,
            approvals=approvals,
            evidence=evidence,
            recommendations=recommendations,
            assumptions=list(procurement.assumptions),
            data_gaps=list(procurement.data_gaps),
            metadata={
                "procurement_status": procurement.status.value,
                "live_supplier_count": len(
                    procurement.live_supplier_results
                ),
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            },
        )

        return decision

    def evaluate_supplier_commitment(
        self,
        decision: EnterpriseDecision,
    ) -> EnterpriseDecision:
        """
        Re-evaluate whether Dawlat may commit to the selected supplier.
        """

        allowed = decision.supplier_commitment_allowed()

        outcome = (
            DecisionOutcome.APPROVED
            if allowed
            else DecisionOutcome.BLOCKED
        )

        summary = (
            "Supplier commitment is allowed."
            if allowed
            else (
                "Supplier commitment is blocked until buyer acceptance, "
                "cleared funds, protected margin, supplier verification and "
                "required approvals are complete."
            )
        )

        return replace(
            decision,
            decision_type=DecisionType.DEAL_APPROVAL,
            outcome=outcome,
            executive_summary=summary,
        )

    def evaluate_supplier_payment_release(
        self,
        decision: EnterpriseDecision,
        *,
        stage: PaymentStage,
    ) -> EnterpriseDecision:
        """
        Re-evaluate whether one supplier payment milestone may be released.
        """

        allowed = decision.supplier_payment_release_allowed(stage)

        outcome = (
            DecisionOutcome.APPROVED
            if allowed
            else DecisionOutcome.BLOCKED
        )

        summary = (
            f"Supplier payment release for '{stage.value}' is allowed."
            if allowed
            else (
                f"Supplier payment release for '{stage.value}' is blocked. "
                "Required evidence, cleared buyer funds, milestone conditions "
                "and approvals are not all complete."
            )
        )

        return replace(
            decision,
            decision_type=DecisionType.PAYMENT_RELEASE,
            outcome=outcome,
            executive_summary=summary,
        )

    @staticmethod
    def _default_buyer_commitment(
        requirement: ProcurementRequirement,
    ) -> BuyerCommercialCommitment:
        return BuyerCommercialCommitment(
            buyer_id=None,
            buyer_name=requirement.buyer_name or "Unconfirmed Buyer",
            status=BuyerReadinessStatus.UNQUALIFIED,
            product=requirement.product,
            quantity=requirement.quantity,
            unit=requirement.unit,
            specifications=requirement.specifications,
            packaging=requirement.packaging,
            required_certificates=requirement.required_certificates,
            delivery_location=requirement.destination,
            required_delivery_date=requirement.required_delivery_date,
            accepted_currency=requirement.currency,
            accepted_unit_price=None,
            accepted_total_value=None,
            payment_terms=requirement.payment_terms,
            deposit_required=None,
            deposit_received=None,
            cleared_funds=None,
            accepted_in_writing=False,
            identity_verified=False,
            credit_checked=False,
            sanctions_checked=False,
        )

    @staticmethod
    def _best_supplier_offer(
        requirement: ProcurementRequirement,
        procurement: ProcurementDecision,
    ) -> SupplierCommercialOffer | None:
        quotes = procurement.matched_records.get(
            "supplier_quotes",
            [],
        )

        if not quotes:
            return None

        valid = [
            item
            for item in quotes
            if _number(item.get("unit_price")) > 0
        ]

        if not valid:
            return None

        best = min(
            valid,
            key=lambda item: (
                _number(item.get("unit_price")),
                _number(item.get("risk_score")),
                -_number(item.get("quality_score")),
            ),
        )

        unit_price = _number(best.get("unit_price"))
        quantity = _number(best.get("quantity")) or requirement.quantity

        return SupplierCommercialOffer(
            supplier_id=best.get("supplier_id"),
            supplier_name=best.get("supplier_name") or "Unknown Supplier",
            commitment_status=(
                SupplierCommitmentStatus.SELECTED_PENDING_APPROVAL
            ),
            product=requirement.product,
            quantity=quantity,
            unit=requirement.unit,
            currency=best.get("currency") or requirement.currency,
            unit_price=unit_price,
            total_goods_value=round(unit_price * quantity, 2),
            incoterm=best.get("incoterm") or "Not Recorded",
            origin=requirement.origin_country_preference or "Not Recorded",
            destination=requirement.destination,
            lead_time_days=int(
                _number(best.get("lead_time_days"))
            ),
            validity_date=best.get("quotation_valid_until"),
            payment_terms=best.get("payment_terms") or "",
            freight_included=False,
            insurance_included=False,
            customs_included=False,
            local_delivery_included=False,
            estimated_landed_cost=(
                procurement.commercial_summary.get(
                    "best_landed_cost_per_unit"
                )
            ),
            certificates=tuple(
                _split_values(best.get("certificates"))
            ),
            sample_approved=bool(best.get("sample_available")),
            supplier_verified=False,
            bank_details_verified=False,
            notes=best.get("notes") or "",
        )

    @staticmethod
    def _margin_protection(
        requirement: ProcurementRequirement,
        procurement: ProcurementDecision,
        supplier_offer: SupplierCommercialOffer | None,
    ) -> MarginProtection | None:
        if requirement.target_sell_price is None:
            return None

        landed_per_unit = procurement.commercial_summary.get(
            "best_landed_cost_per_unit"
        )

        if landed_per_unit in (None, 0):
            return None

        buyer_total = (
            requirement.target_sell_price
            * requirement.quantity
        )
        supplier_total = (
            supplier_offer.total_goods_value
            if supplier_offer
            else 0
        )
        gross_profit = (
            requirement.target_sell_price
            - float(landed_per_unit)
        ) * requirement.quantity

        margin_percent = (
            gross_profit / buyer_total * 100
            if buyer_total > 0
            else 0
        )

        minimum_margin = 15.0

        return MarginProtection(
            currency=requirement.currency,
            buyer_total_value=round(buyer_total, 2),
            supplier_total_cost=round(supplier_total, 2),
            freight_cost=0,
            customs_and_duties=0,
            warehouse_cost=0,
            local_delivery_cost=0,
            finance_cost=0,
            contingency=0,
            other_costs=0,
            minimum_margin_percent=minimum_margin,
            expected_margin_percent=round(margin_percent, 2),
            expected_gross_profit=round(gross_profit, 2),
            margin_protected=margin_percent >= minimum_margin,
            approval_required=True,
            reason=(
                "Margin meets the minimum threshold."
                if margin_percent >= minimum_margin
                else "Margin is below the approved minimum threshold."
            ),
        )

    @staticmethod
    def _default_approvals(
        created_by: str,
    ) -> list[ApprovalRecord]:
        now = datetime.now().isoformat(timespec="seconds")

        return [
            ApprovalRecord(
                approval_type="Commercial Approval",
                status=ApprovalStatus.PENDING,
                requested_by=created_by,
                requested_at=now,
                approver_role="Managing Director",
            ),
            ApprovalRecord(
                approval_type="Finance Approval",
                status=ApprovalStatus.PENDING,
                requested_by=created_by,
                requested_at=now,
                approver_role="Finance Approver",
            ),
        ]

    @staticmethod
    def _evaluate_control_gates(
        *,
        buyer: BuyerCommercialCommitment,
        supplier: SupplierCommercialOffer | None,
        margin: MarginProtection | None,
        milestones: list[PaymentMilestone],
        approvals: list[ApprovalRecord],
    ) -> list:
        gates = default_deal_control_gates()
        approvals_ok = all(
            approval.status in {
                ApprovalStatus.APPROVED,
                ApprovalStatus.NOT_REQUIRED,
            }
            for approval in approvals
        )

        state = {
            "Buyer identity verified": buyer.identity_verified,
            "Buyer requirement confirmed": bool(
                buyer.product
                and buyer.quantity > 0
                and buyer.delivery_location
            ),
            "Buyer quotation accepted": buyer.accepted_in_writing,
            "Buyer funds cleared": (
                buyer.status == BuyerReadinessStatus.FUNDS_CLEARED
                and (buyer.cleared_funds or 0) > 0
            ),
            "Supplier verified": bool(
                supplier
                and supplier.supplier_verified
                and supplier.bank_details_verified
            ),
            "Margin protected": bool(
                margin and margin.margin_protected
            ),
            "Contracts approved": approvals_ok,
            "Payment milestones approved": bool(
                milestones
                and all(
                    item.finance_approval
                    == ApprovalStatus.APPROVED
                    and item.management_approval
                    == ApprovalStatus.APPROVED
                    for item in milestones
                )
            ),
        }

        return [
            replace(gate, passed=state.get(gate.gate_name, False))
            for gate in gates
        ]

    @staticmethod
    def _convert_risks(
        procurement: ProcurementDecision,
    ) -> list[RiskFinding]:
        converted = []

        for item in procurement.risks:
            severity = RiskSeverity(
                item.severity
                if item.severity
                in {value.value for value in RiskSeverity}
                else RiskSeverity.MEDIUM.value
            )

            converted.append(
                RiskFinding(
                    category=item.category,
                    severity=severity,
                    description=item.description,
                    impact="May affect cost, timing, compliance or trust.",
                    mitigation=item.mitigation,
                    blocking=severity
                    in {
                        RiskSeverity.HIGH,
                        RiskSeverity.CRITICAL,
                    },
                    owner_role="Risk Manager",
                )
            )

        return converted

    @staticmethod
    def _control_risks(
        *,
        buyer: BuyerCommercialCommitment,
        supplier: SupplierCommercialOffer | None,
        margin: MarginProtection | None,
        milestones: list[PaymentMilestone],
    ) -> list[RiskFinding]:
        risks = []

        if not buyer.accepted_in_writing:
            risks.append(
                RiskFinding(
                    category="Buyer Commitment",
                    severity=RiskSeverity.CRITICAL,
                    description="Buyer has not accepted the final quotation in writing.",
                    impact="Dawlat may be exposed to cancellation or price dispute.",
                    mitigation="Obtain written acceptance of the exact quotation version.",
                    blocking=True,
                    owner_role="Sales Manager",
                )
            )

        if buyer.status != BuyerReadinessStatus.FUNDS_CLEARED:
            risks.append(
                RiskFinding(
                    category="Buyer Payment",
                    severity=RiskSeverity.CRITICAL,
                    description="Buyer funds are not confirmed as cleared.",
                    impact="Dawlat could pay the supplier without secured buyer funds.",
                    mitigation="Verify cleared funds before supplier commitment or payment.",
                    blocking=True,
                    owner_role="Finance Approver",
                )
            )

        if supplier and not supplier.bank_details_verified:
            risks.append(
                RiskFinding(
                    category="Supplier Bank Details",
                    severity=RiskSeverity.CRITICAL,
                    description="Supplier bank details are not independently verified.",
                    impact="Payment fraud or diversion risk.",
                    mitigation="Verify bank details using an independent contact channel.",
                    blocking=True,
                    owner_role="Finance Approver",
                )
            )

        if not margin or not margin.margin_protected:
            risks.append(
                RiskFinding(
                    category="Margin Protection",
                    severity=RiskSeverity.HIGH,
                    description="Approved Dawlat Global margin is not protected.",
                    impact="The transaction may produce insufficient or negative profit.",
                    mitigation="Reprice, renegotiate or stop the deal.",
                    blocking=True,
                    owner_role="Commercial Manager",
                )
            )

        if not milestones:
            risks.append(
                RiskFinding(
                    category="Payment Controls",
                    severity=RiskSeverity.HIGH,
                    description="Supplier payment milestones are not defined.",
                    impact="Payments may be released without evidence or performance.",
                    mitigation="Create milestone-based payment controls.",
                    blocking=True,
                    owner_role="Finance Approver",
                )
            )

        return risks

    @staticmethod
    def _convert_evidence(
        procurement: ProcurementDecision,
    ) -> list[EvidenceReference]:
        evidence = []

        for item in procurement.evidence:
            evidence.append(
                EvidenceReference(
                    evidence_type=(
                        EvidenceType.LIVE_SOURCE
                        if item.url
                        else EvidenceType.INTERNAL_RECORD
                    ),
                    source=item.source,
                    label=item.label,
                    details=item.details,
                    record_id=item.record_id,
                    url=item.url,
                )
            )

        return evidence

    @staticmethod
    def _determine_outcome(
        *,
        gates: list,
        risks: list[RiskFinding],
        approvals: list[ApprovalRecord],
    ) -> DecisionOutcome:
        if any(
            risk.severity == RiskSeverity.CRITICAL
            for risk in risks
        ):
            return DecisionOutcome.BLOCKED

        if any(
            gate.blocking and not gate.passed
            for gate in gates
        ):
            return DecisionOutcome.PENDING_INFORMATION

        if any(
            approval.status == ApprovalStatus.PENDING
            for approval in approvals
        ):
            return DecisionOutcome.PENDING_APPROVAL

        if any(
            risk.severity == RiskSeverity.HIGH
            for risk in risks
        ):
            return DecisionOutcome.CONDITIONALLY_APPROVED

        return DecisionOutcome.APPROVED

    @staticmethod
    def _recommendations(
        *,
        outcome: DecisionOutcome,
        gates: list,
        risks: list[RiskFinding],
        procurement: ProcurementDecision,
    ) -> list[RecommendedAction]:
        actions = []
        priority = 1

        for gate in gates:
            if gate.passed:
                continue

            actions.append(
                RecommendedAction(
                    priority=priority,
                    action=gate.required_actions[0]
                    if gate.required_actions
                    else gate.reason,
                    owner_role="Assigned Manager",
                    reason=gate.reason,
                    approval_required=gate.blocking,
                    blocking=gate.blocking,
                )
            )
            priority += 1

        for action in procurement.recommendations:
            actions.append(
                RecommendedAction(
                    priority=priority,
                    action=action.action,
                    owner_role=action.owner_role,
                    reason=action.reason,
                    approval_required=action.approval_required,
                    blocking=False,
                )
            )
            priority += 1

        if outcome == DecisionOutcome.APPROVED:
            actions.append(
                RecommendedAction(
                    priority=priority,
                    action="Prepare the controlled execution plan.",
                    owner_role="Executive Advisor",
                    reason="All mandatory controls have passed.",
                    approval_required=True,
                )
            )

        return actions

    @staticmethod
    def _summary(
        *,
        requirement: ProcurementRequirement,
        outcome: DecisionOutcome,
        procurement: ProcurementDecision,
        buyer: BuyerCommercialCommitment,
        supplier: SupplierCommercialOffer | None,
        margin: MarginProtection | None,
    ) -> str:
        return (
            f"Deal evaluation for {requirement.quantity:g} "
            f"{requirement.unit} of {requirement.product} to "
            f"{requirement.destination}. Outcome: {outcome.value}. "
            f"Buyer status: {buyer.status.value}. "
            f"Supplier: "
            f"{supplier.supplier_name if supplier else 'Not selected'}. "
            f"Margin protected: "
            f"{'Yes' if margin and margin.margin_protected else 'No'}. "
            f"Decision confidence: {procurement.confidence_score}/100."
        )

    @staticmethod
    def _decision_id() -> str:
        return f"DEC-{datetime.now().year}-{uuid4().hex[:10].upper()}"


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _split_values(value: Any) -> list[str]:
    if not value:
        return []

    return [
        item.strip()
        for item in str(value).replace(";", ",").split(",")
        if item.strip()
    ]


_engine = EnterpriseDecisionEngine()


def evaluate_enterprise_deal(
    *,
    requirement: ProcurementRequirement,
    buyer_commitment: BuyerCommercialCommitment | None = None,
    supplier_offer: SupplierCommercialOffer | None = None,
    margin_protection: MarginProtection | None = None,
    payment_milestones: list[PaymentMilestone] | None = None,
    approvals: list[ApprovalRecord] | None = None,
    include_live_discovery: bool = False,
    created_by: str = "System",
) -> EnterpriseDecision:
    return _engine.evaluate_deal(
        requirement=requirement,
        buyer_commitment=buyer_commitment,
        supplier_offer=supplier_offer,
        margin_protection=margin_protection,
        payment_milestones=payment_milestones,
        approvals=approvals,
        include_live_discovery=include_live_discovery,
        created_by=created_by,
    )


def evaluate_supplier_commitment(
    decision: EnterpriseDecision,
) -> EnterpriseDecision:
    return _engine.evaluate_supplier_commitment(decision)


def evaluate_supplier_payment_release(
    decision: EnterpriseDecision,
    *,
    stage: PaymentStage,
) -> EnterpriseDecision:
    return _engine.evaluate_supplier_payment_release(
        decision,
        stage=stage,
    )