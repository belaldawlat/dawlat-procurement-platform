"""
Autonomous Procurement Orchestrator.

Coordinates the governed procurement and global-trade lifecycle for the
Dawlat AI Procurement & Global Trade Intelligence Platform.

This orchestrator:
- starts from verified buyer demand or a market opportunity;
- evaluates local and international supply;
- builds the enterprise deal decision;
- runs risk, recommendation, trust and explainability engines;
- determines the safest next stage;
- produces a controlled action plan;
- never sends binding communications, issues purchase orders, releases funds,
  instructs shipment, or commits suppliers automatically.

All commercial, legal and financial execution remains human-approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from models.decision import (
    ApprovalRecord,
    BuyerCommercialCommitment,
    EnterpriseDecision,
    MarginProtection,
    PaymentMilestone,
    PaymentStage,
    SupplierCommercialOffer,
)
from services.enterprise_decision_engine import (
    evaluate_enterprise_deal,
    evaluate_supplier_commitment,
    evaluate_supplier_payment_release,
)
from services.intelligence.explainable_ai_engine import (
    ExplainableDecision,
    explain_enterprise_decision,
)
from services.intelligence.opportunity_intelligence_engine import (
    OpportunityAssessment,
    assess_trade_opportunity,
)
from services.intelligence.recommendation_intelligence_engine import (
    RecommendationReport,
    generate_enterprise_recommendations,
)
from services.intelligence.risk_intelligence_engine import (
    RiskAssessment,
    assess_enterprise_risk,
)
from services.intelligence.trust_intelligence_engine import (
    TrustAssessment,
    TrustDecision,
    assess_enterprise_trust,
)
from services.procurement_intelligence_engine import ProcurementRequirement


class WorkflowStage(str, Enum):
    DEMAND_IDENTIFIED = "Demand Identified"
    BUYER_QUALIFICATION = "Buyer Qualification"
    BUYER_VERIFIED = "Buyer Verified"
    OPPORTUNITY_ASSESSMENT = "Opportunity Assessment"
    SUPPLIER_DISCOVERY = "Supplier Discovery"
    SUPPLIER_VERIFICATION = "Supplier Verification"
    QUOTATION_COLLECTION = "Quotation Collection"
    COMMERCIAL_EVALUATION = "Commercial Evaluation"
    RISK_REVIEW = "Risk Review"
    TRUST_VALIDATION = "Trust Validation"
    MANAGEMENT_APPROVAL = "Management Approval"
    BUYER_CONFIRMATION = "Buyer Confirmation"
    FUNDS_SECURED = "Funds Secured"
    SUPPLIER_COMMITMENT = "Supplier Commitment"
    PURCHASE_ORDER_RELEASE = "Purchase Order Release"
    PRODUCTION = "Production"
    PRE_SHIPMENT_CONTROL = "Pre-Shipment Control"
    SHIPMENT = "Shipment"
    CUSTOMS_AND_BIOSECURITY = "Customs & Biosecurity"
    DELIVERY = "Delivery"
    SUPPLIER_PAYMENT_RELEASE = "Supplier Payment Release"
    FINAL_RECONCILIATION = "Final Reconciliation"
    DEAL_CLOSED = "Deal Closed"
    PERFORMANCE_REVIEW = "Performance Review"
    BLOCKED = "Blocked"
    CANCELLED = "Cancelled"


class WorkflowStatus(str, Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    WAITING_FOR_INFORMATION = "Waiting for Information"
    WAITING_FOR_APPROVAL = "Waiting for Approval"
    READY_FOR_NEXT_STAGE = "Ready for Next Stage"
    BLOCKED = "Blocked"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class ActionType(str, Enum):
    RESEARCH = "Research"
    VERIFY = "Verify"
    CONTACT_DRAFT = "Prepare Contact Draft"
    REQUEST_APPROVAL = "Request Approval"
    REQUEST_QUOTATION = "Request Quotation"
    CALCULATE = "Calculate"
    REVIEW = "Review"
    HOLD = "Hold"
    EXECUTE_AFTER_APPROVAL = "Execute After Approval"
    MONITOR = "Monitor"


@dataclass(frozen=True)
class WorkflowEvent:
    event_id: str
    workflow_id: str
    stage: WorkflowStage
    event_type: str
    message: str
    actor: str
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrchestratedAction:
    priority: int
    action_type: ActionType
    title: str
    instructions: str
    owner_role: str
    stage: WorkflowStage
    blocking: bool
    approval_required: bool
    can_auto_execute: bool = False
    reason: str = ""
    expected_value: float | None = None
    currency: str = "AUD"


@dataclass(frozen=True)
class StageGate:
    stage: WorkflowStage
    passed: bool
    blocking: bool
    reason: str
    required_actions: tuple[str, ...] = ()


@dataclass
class ProcurementWorkflow:
    workflow_id: str
    title: str
    current_stage: WorkflowStage
    status: WorkflowStatus
    requirement: ProcurementRequirement

    opportunity: OpportunityAssessment | None = None
    enterprise_decision: EnterpriseDecision | None = None
    risk_assessment: RiskAssessment | None = None
    recommendation_report: RecommendationReport | None = None
    trust_assessment: TrustAssessment | None = None
    explanation: ExplainableDecision | None = None

    stage_gates: list[StageGate] = field(default_factory=list)
    action_plan: list[OrchestratedAction] = field(default_factory=list)
    events: list[WorkflowEvent] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    completed_stages: list[WorkflowStage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def is_blocked(self) -> bool:
        return self.status == WorkflowStatus.BLOCKED or bool(self.blockers)

    def may_commit_supplier(self) -> bool:
        return bool(
            self.trust_assessment
            and self.trust_assessment.supplier_commitment_allowed()
            and self.enterprise_decision
            and self.enterprise_decision.supplier_commitment_allowed()
        )

    def may_release_supplier_payment(
        self,
        stage: PaymentStage,
    ) -> bool:
        return bool(
            self.trust_assessment
            and self.enterprise_decision
            and self.trust_assessment.supplier_payment_allowed(
                self.enterprise_decision,
                stage=stage,
            )
        )


class AutonomousProcurementOrchestrator:
    """
    Coordinates intelligence engines and controlled lifecycle progression.

    The orchestrator is intentionally conservative:
    - it may prepare recommendations and drafts;
    - it may identify the next safe stage;
    - it may never perform binding external execution automatically.
    """

    def start_workflow(
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
    ) -> ProcurementWorkflow:
        workflow_id = self._workflow_id()

        opportunity = assess_trade_opportunity(
            product=requirement.product,
            destination=requirement.destination,
            origin_country_preference=requirement.origin_country_preference,
            buyer_name=requirement.buyer_name,
            include_live_discovery=include_live_discovery,
            required_certificates=requirement.required_certificates,
            preferred_incoterms=requirement.preferred_incoterms,
            maximum_lead_time_days=requirement.maximum_lead_time_days,
        )

        enterprise_decision = evaluate_enterprise_deal(
            requirement=requirement,
            buyer_commitment=buyer_commitment,
            supplier_offer=supplier_offer,
            margin_protection=margin_protection,
            payment_milestones=payment_milestones,
            approvals=approvals,
            include_live_discovery=include_live_discovery,
            created_by=created_by,
        )

        risk = assess_enterprise_risk(enterprise_decision)
        recommendation = generate_enterprise_recommendations(
            enterprise_decision,
            risk_assessment=risk,
        )
        trust = assess_enterprise_trust(
            enterprise_decision,
            risk_assessment=risk,
        )
        explanation = explain_enterprise_decision(
            enterprise_decision,
            risk_assessment=risk,
            recommendation_report=recommendation,
            trust_assessment=trust,
        )

        gates = self._evaluate_stage_gates(
            requirement=requirement,
            opportunity=opportunity,
            decision=enterprise_decision,
            risk=risk,
            trust=trust,
        )

        stage, status = self._next_stage(
            gates=gates,
            trust=trust,
            opportunity=opportunity,
        )

        blockers = self._blockers(
            gates=gates,
            trust=trust,
            risk=risk,
        )

        action_plan = self._action_plan(
            workflow_id=workflow_id,
            stage=stage,
            opportunity=opportunity,
            decision=enterprise_decision,
            risk=risk,
            recommendation=recommendation,
            trust=trust,
        )

        events = [
            WorkflowEvent(
                event_id=self._event_id(),
                workflow_id=workflow_id,
                stage=WorkflowStage.DEMAND_IDENTIFIED,
                event_type="Workflow Started",
                message=(
                    f"Workflow started for {requirement.quantity:g} "
                    f"{requirement.unit} of {requirement.product}."
                ),
                actor=created_by,
            ),
            WorkflowEvent(
                event_id=self._event_id(),
                workflow_id=workflow_id,
                stage=stage,
                event_type="Stage Evaluated",
                message=(
                    f"Current controlled stage: {stage.value}; "
                    f"status: {status.value}."
                ),
                actor="Autonomous Procurement Orchestrator",
            ),
        ]

        return ProcurementWorkflow(
            workflow_id=workflow_id,
            title=f"Procurement Workflow: {requirement.product}",
            current_stage=stage,
            status=status,
            requirement=requirement,
            opportunity=opportunity,
            enterprise_decision=enterprise_decision,
            risk_assessment=risk,
            recommendation_report=recommendation,
            trust_assessment=trust,
            explanation=explanation,
            stage_gates=gates,
            action_plan=action_plan,
            events=events,
            blockers=blockers,
            completed_stages=self._completed_stages(gates),
            metadata={
                "created_by": created_by,
                "include_live_discovery": include_live_discovery,
                "opportunity_score": opportunity.opportunity_score,
                "trust_score": trust.overall_score,
                "risk_score": risk.overall_score,
                "decision_id": enterprise_decision.decision_id,
            },
        )

    def refresh_workflow(
        self,
        workflow: ProcurementWorkflow,
        *,
        buyer_commitment: BuyerCommercialCommitment | None = None,
        supplier_offer: SupplierCommercialOffer | None = None,
        margin_protection: MarginProtection | None = None,
        payment_milestones: list[PaymentMilestone] | None = None,
        approvals: list[ApprovalRecord] | None = None,
        include_live_discovery: bool | None = None,
        actor: str = "System",
    ) -> ProcurementWorkflow:
        """
        Re-run the workflow after new evidence, approval or milestone changes.
        """

        include_live = (
            bool(workflow.metadata.get("include_live_discovery"))
            if include_live_discovery is None
            else include_live_discovery
        )

        refreshed = self.start_workflow(
            requirement=workflow.requirement,
            buyer_commitment=(
                buyer_commitment
                or (
                    workflow.enterprise_decision.buyer_commitment
                    if workflow.enterprise_decision
                    else None
                )
            ),
            supplier_offer=(
                supplier_offer
                or (
                    workflow.enterprise_decision.supplier_offer
                    if workflow.enterprise_decision
                    else None
                )
            ),
            margin_protection=(
                margin_protection
                or (
                    workflow.enterprise_decision.margin_protection
                    if workflow.enterprise_decision
                    else None
                )
            ),
            payment_milestones=(
                payment_milestones
                if payment_milestones is not None
                else (
                    workflow.enterprise_decision.payment_milestones
                    if workflow.enterprise_decision
                    else []
                )
            ),
            approvals=(
                approvals
                if approvals is not None
                else (
                    workflow.enterprise_decision.approvals
                    if workflow.enterprise_decision
                    else []
                )
            ),
            include_live_discovery=include_live,
            created_by=actor,
        )

        refreshed.workflow_id = workflow.workflow_id
        refreshed.created_at = workflow.created_at
        refreshed.events = list(workflow.events) + [
            WorkflowEvent(
                event_id=self._event_id(),
                workflow_id=workflow.workflow_id,
                stage=refreshed.current_stage,
                event_type="Workflow Refreshed",
                message=(
                    f"Workflow re-evaluated. New stage: "
                    f"{refreshed.current_stage.value}."
                ),
                actor=actor,
            )
        ]
        refreshed.updated_at = datetime.now().isoformat(
            timespec="seconds"
        )

        return refreshed

    def evaluate_supplier_commitment_gate(
        self,
        workflow: ProcurementWorkflow,
        *,
        actor: str = "System",
    ) -> ProcurementWorkflow:
        if not workflow.enterprise_decision:
            return self._block_workflow(
                workflow,
                "Enterprise decision is missing.",
                actor=actor,
            )

        evaluated = evaluate_supplier_commitment(
            workflow.enterprise_decision
        )

        workflow.enterprise_decision = evaluated

        if not workflow.may_commit_supplier():
            return self._block_workflow(
                workflow,
                evaluated.executive_summary,
                actor=actor,
            )

        workflow.current_stage = WorkflowStage.SUPPLIER_COMMITMENT
        workflow.status = WorkflowStatus.WAITING_FOR_APPROVAL
        workflow.events.append(
            WorkflowEvent(
                event_id=self._event_id(),
                workflow_id=workflow.workflow_id,
                stage=WorkflowStage.SUPPLIER_COMMITMENT,
                event_type="Supplier Commitment Gate Passed",
                message=(
                    "All automated controls passed. Human approval is still required."
                ),
                actor=actor,
            )
        )
        workflow.updated_at = datetime.now().isoformat(
            timespec="seconds"
        )
        return workflow

    def evaluate_payment_release_gate(
        self,
        workflow: ProcurementWorkflow,
        *,
        payment_stage: PaymentStage,
        actor: str = "System",
    ) -> ProcurementWorkflow:
        if not workflow.enterprise_decision:
            return self._block_workflow(
                workflow,
                "Enterprise decision is missing.",
                actor=actor,
            )

        evaluated = evaluate_supplier_payment_release(
            workflow.enterprise_decision,
            stage=payment_stage,
        )

        workflow.enterprise_decision = evaluated

        if not workflow.may_release_supplier_payment(payment_stage):
            return self._block_workflow(
                workflow,
                evaluated.executive_summary,
                actor=actor,
            )

        workflow.current_stage = WorkflowStage.SUPPLIER_PAYMENT_RELEASE
        workflow.status = WorkflowStatus.WAITING_FOR_APPROVAL
        workflow.events.append(
            WorkflowEvent(
                event_id=self._event_id(),
                workflow_id=workflow.workflow_id,
                stage=WorkflowStage.SUPPLIER_PAYMENT_RELEASE,
                event_type="Payment Release Gate Passed",
                message=(
                    f"{payment_stage.value} passed automated controls. "
                    "Finance and management must still authorise execution."
                ),
                actor=actor,
            )
        )
        workflow.updated_at = datetime.now().isoformat(
            timespec="seconds"
        )
        return workflow

    @staticmethod
    def _evaluate_stage_gates(
        *,
        requirement: ProcurementRequirement,
        opportunity: OpportunityAssessment,
        decision: EnterpriseDecision,
        risk: RiskAssessment,
        trust: TrustAssessment,
    ) -> list[StageGate]:
        buyer = decision.buyer_commitment
        supplier = decision.supplier_offer
        margin = decision.margin_protection

        return [
            StageGate(
                WorkflowStage.DEMAND_IDENTIFIED,
                passed=bool(requirement.product and requirement.quantity > 0),
                blocking=True,
                reason="A valid product and quantity are required.",
                required_actions=("Record the buyer or market requirement.",),
            ),
            StageGate(
                WorkflowStage.BUYER_QUALIFICATION,
                passed=bool(buyer),
                blocking=True,
                reason="A buyer commitment record is required.",
                required_actions=("Create and qualify the buyer commitment.",),
            ),
            StageGate(
                WorkflowStage.BUYER_VERIFIED,
                passed=bool(
                    buyer
                    and buyer.identity_verified
                    and buyer.credit_checked
                    and buyer.sanctions_checked
                ),
                blocking=True,
                reason="Buyer identity, credit and compliance checks must pass.",
                required_actions=(
                    "Verify buyer identity.",
                    "Complete credit and sanctions checks.",
                ),
            ),
            StageGate(
                WorkflowStage.OPPORTUNITY_ASSESSMENT,
                passed=opportunity.opportunity_score > 0,
                blocking=False,
                reason="Opportunity evidence must be assessed.",
                required_actions=("Complete opportunity assessment.",),
            ),
            StageGate(
                WorkflowStage.SUPPLIER_DISCOVERY,
                passed=bool(
                    opportunity.local_supply_options
                    or opportunity.international_supply_options
                    or supplier
                ),
                blocking=True,
                reason="At least one supply option is required.",
                required_actions=("Run local and global supplier discovery.",),
            ),
            StageGate(
                WorkflowStage.SUPPLIER_VERIFICATION,
                passed=bool(
                    supplier
                    and supplier.supplier_verified
                    and supplier.bank_details_verified
                ),
                blocking=True,
                reason="Supplier identity, capability and bank details must pass.",
                required_actions=(
                    "Verify supplier legal identity and capability.",
                    "Verify supplier bank details independently.",
                ),
            ),
            StageGate(
                WorkflowStage.QUOTATION_COLLECTION,
                passed=bool(supplier and supplier.unit_price > 0),
                blocking=True,
                reason="A valid supplier quotation is required.",
                required_actions=("Obtain a valid supplier quotation.",),
            ),
            StageGate(
                WorkflowStage.COMMERCIAL_EVALUATION,
                passed=bool(margin and margin.margin_protected),
                blocking=True,
                reason="Approved landed cost and minimum margin are required.",
                required_actions=(
                    "Complete landed-cost analysis.",
                    "Protect the minimum commercial margin.",
                ),
            ),
            StageGate(
                WorkflowStage.RISK_REVIEW,
                passed=not risk.is_blocked,
                blocking=True,
                reason="Blocking risk findings must be resolved.",
                required_actions=tuple(risk.mitigations[:5]),
            ),
            StageGate(
                WorkflowStage.TRUST_VALIDATION,
                passed=not trust.is_blocked,
                blocking=True,
                reason="All mandatory trust controls must pass.",
                required_actions=tuple(
                    item.action
                    for item in trust.outstanding_actions[:5]
                ),
            ),
            StageGate(
                WorkflowStage.MANAGEMENT_APPROVAL,
                passed=all(
                    item.status.value in {"Approved", "Not Required"}
                    for item in decision.approvals
                )
                if decision.approvals
                else False,
                blocking=True,
                reason="Required management and finance approvals must pass.",
                required_actions=("Obtain all authorised approvals.",),
            ),
            StageGate(
                WorkflowStage.BUYER_CONFIRMATION,
                passed=bool(buyer and buyer.accepted_in_writing),
                blocking=True,
                reason="Buyer must accept the final quotation in writing.",
                required_actions=("Capture written buyer acceptance.",),
            ),
            StageGate(
                WorkflowStage.FUNDS_SECURED,
                passed=decision.buyer_funds_cleared(),
                blocking=True,
                reason="Buyer funds must be cleared before supplier commitment.",
                required_actions=("Verify cleared buyer funds.",),
            ),
            StageGate(
                WorkflowStage.SUPPLIER_COMMITMENT,
                passed=decision.supplier_commitment_allowed(),
                blocking=True,
                reason="Supplier commitment gate is not yet satisfied.",
                required_actions=("Pass all supplier commitment controls.",),
            ),
        ]

    @staticmethod
    def _next_stage(
        *,
        gates: list[StageGate],
        trust: TrustAssessment,
        opportunity: OpportunityAssessment,
    ) -> tuple[WorkflowStage, WorkflowStatus]:
        for gate in gates:
            if not gate.passed:
                if gate.blocking:
                    return (
                        gate.stage,
                        WorkflowStatus.WAITING_FOR_INFORMATION,
                    )
                return (
                    gate.stage,
                    WorkflowStatus.IN_PROGRESS,
                )

        if trust.trust_decision == TrustDecision.APPROVE:
            return (
                WorkflowStage.PURCHASE_ORDER_RELEASE,
                WorkflowStatus.WAITING_FOR_APPROVAL,
            )

        if trust.trust_decision == TrustDecision.APPROVE_WITH_CONDITIONS:
            return (
                WorkflowStage.MANAGEMENT_APPROVAL,
                WorkflowStatus.WAITING_FOR_APPROVAL,
            )

        if opportunity.opportunity_score < 40:
            return (
                WorkflowStage.OPPORTUNITY_ASSESSMENT,
                WorkflowStatus.IN_PROGRESS,
            )

        return (
            WorkflowStage.TRUST_VALIDATION,
            WorkflowStatus.WAITING_FOR_INFORMATION,
        )

    @staticmethod
    def _blockers(
        *,
        gates: list[StageGate],
        trust: TrustAssessment,
        risk: RiskAssessment,
    ) -> list[str]:
        blockers = [
            gate.reason
            for gate in gates
            if gate.blocking and not gate.passed
        ]
        blockers.extend(trust.blocking_reasons)
        blockers.extend(risk.blocking_reasons)
        return list(dict.fromkeys(blockers))

    @staticmethod
    def _completed_stages(
        gates: list[StageGate],
    ) -> list[WorkflowStage]:
        return [
            gate.stage
            for gate in gates
            if gate.passed
        ]

    @staticmethod
    def _action_plan(
        *,
        workflow_id: str,
        stage: WorkflowStage,
        opportunity: OpportunityAssessment,
        decision: EnterpriseDecision,
        risk: RiskAssessment,
        recommendation: RecommendationReport,
        trust: TrustAssessment,
    ) -> list[OrchestratedAction]:
        actions: list[OrchestratedAction] = []
        priority = 1

        for item in trust.outstanding_actions:
            actions.append(
                OrchestratedAction(
                    priority=priority,
                    action_type=(
                        ActionType.REQUEST_APPROVAL
                        if item.approval_required
                        else ActionType.VERIFY
                    ),
                    title=item.action,
                    instructions=item.action,
                    owner_role=item.owner_role,
                    stage=stage,
                    blocking=item.blocking,
                    approval_required=item.approval_required,
                    can_auto_execute=False,
                    reason=item.reason,
                )
            )
            priority += 1

        for item in recommendation.ranked_recommendations:
            if any(
                existing.title == item.action
                for existing in actions
            ):
                continue

            actions.append(
                OrchestratedAction(
                    priority=priority,
                    action_type=(
                        ActionType.HOLD
                        if item.blocking
                        else ActionType.REVIEW
                    ),
                    title=item.title,
                    instructions=item.action,
                    owner_role=item.owner_role,
                    stage=stage,
                    blocking=item.blocking,
                    approval_required=item.approval_required,
                    can_auto_execute=False,
                    reason="; ".join(item.rationale),
                )
            )
            priority += 1

        for item in opportunity.recommendations:
            if any(
                existing.instructions == item.action
                for existing in actions
            ):
                continue

            actions.append(
                OrchestratedAction(
                    priority=priority,
                    action_type=(
                        ActionType.REQUEST_APPROVAL
                        if item.approval_required
                        else ActionType.RESEARCH
                    ),
                    title=item.action[:80],
                    instructions=item.action,
                    owner_role=item.owner_role,
                    stage=stage,
                    blocking=False,
                    approval_required=item.approval_required,
                    can_auto_execute=False,
                    reason=item.reason,
                    expected_value=item.expected_value,
                    currency=item.currency,
                )
            )
            priority += 1

        if not actions:
            actions.append(
                OrchestratedAction(
                    priority=1,
                    action_type=ActionType.MONITOR,
                    title="Monitor approved workflow",
                    instructions=(
                        "Continue monitoring buyer, supplier, payment, "
                        "shipment, compliance and margin changes."
                    ),
                    owner_role="Operations Manager",
                    stage=stage,
                    blocking=False,
                    approval_required=False,
                    can_auto_execute=False,
                    reason="No immediate exception requires action.",
                )
            )

        actions.sort(
            key=lambda item: (
                not item.blocking,
                not item.approval_required,
                item.priority,
            )
        )

        return [
            replace(item, priority=index)
            for index, item in enumerate(actions[:30], start=1)
        ]

    @staticmethod
    def _block_workflow(
        workflow: ProcurementWorkflow,
        reason: str,
        *,
        actor: str,
    ) -> ProcurementWorkflow:
        workflow.current_stage = WorkflowStage.BLOCKED
        workflow.status = WorkflowStatus.BLOCKED

        if reason not in workflow.blockers:
            workflow.blockers.append(reason)

        workflow.events.append(
            WorkflowEvent(
                event_id=AutonomousProcurementOrchestrator._event_id(),
                workflow_id=workflow.workflow_id,
                stage=WorkflowStage.BLOCKED,
                event_type="Workflow Blocked",
                message=reason,
                actor=actor,
            )
        )
        workflow.updated_at = datetime.now().isoformat(
            timespec="seconds"
        )
        return workflow

    @staticmethod
    def _workflow_id() -> str:
        return (
            f"WF-{datetime.now().year}-"
            f"{uuid4().hex[:10].upper()}"
        )

    @staticmethod
    def _event_id() -> str:
        return f"EVT-{uuid4().hex[:12].upper()}"


_orchestrator = AutonomousProcurementOrchestrator()


def start_autonomous_procurement_workflow(
    *,
    requirement: ProcurementRequirement,
    buyer_commitment: BuyerCommercialCommitment | None = None,
    supplier_offer: SupplierCommercialOffer | None = None,
    margin_protection: MarginProtection | None = None,
    payment_milestones: list[PaymentMilestone] | None = None,
    approvals: list[ApprovalRecord] | None = None,
    include_live_discovery: bool = False,
    created_by: str = "System",
) -> ProcurementWorkflow:
    """Public workflow creation entry point."""

    return _orchestrator.start_workflow(
        requirement=requirement,
        buyer_commitment=buyer_commitment,
        supplier_offer=supplier_offer,
        margin_protection=margin_protection,
        payment_milestones=payment_milestones,
        approvals=approvals,
        include_live_discovery=include_live_discovery,
        created_by=created_by,
    )


def refresh_autonomous_procurement_workflow(
    workflow: ProcurementWorkflow,
    *,
    buyer_commitment: BuyerCommercialCommitment | None = None,
    supplier_offer: SupplierCommercialOffer | None = None,
    margin_protection: MarginProtection | None = None,
    payment_milestones: list[PaymentMilestone] | None = None,
    approvals: list[ApprovalRecord] | None = None,
    include_live_discovery: bool | None = None,
    actor: str = "System",
) -> ProcurementWorkflow:
    """Public workflow refresh entry point."""

    return _orchestrator.refresh_workflow(
        workflow,
        buyer_commitment=buyer_commitment,
        supplier_offer=supplier_offer,
        margin_protection=margin_protection,
        payment_milestones=payment_milestones,
        approvals=approvals,
        include_live_discovery=include_live_discovery,
        actor=actor,
    )


def evaluate_workflow_supplier_commitment(
    workflow: ProcurementWorkflow,
    *,
    actor: str = "System",
) -> ProcurementWorkflow:
    """Public supplier-commitment gate entry point."""

    return _orchestrator.evaluate_supplier_commitment_gate(
        workflow,
        actor=actor,
    )


def evaluate_workflow_payment_release(
    workflow: ProcurementWorkflow,
    *,
    payment_stage: PaymentStage,
    actor: str = "System",
) -> ProcurementWorkflow:
    """Public supplier-payment gate entry point."""

    return _orchestrator.evaluate_payment_release_gate(
        workflow,
        payment_stage=payment_stage,
        actor=actor,
    )