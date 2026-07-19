"""Autonomous procurement brain integrating decision and intelligence."""

from __future__ import annotations

from app.orchestration.autonomous_procurement_models import (
    AutonomousAction,
    AutonomousProcurementAction,
    AutonomousProcurementContext,
    AutonomyMode,
    BrainConfidence,
)
from app.orchestration.autonomous_procurement_policy import (
    AutonomousProcurementPolicy,
)
from app.orchestration.autonomous_procurement_result import (
    AutonomousProcurementResult,
)
from app.orchestration.procurement_decision_models import ProcurementDecision
from app.orchestration.procurement_decision_result import (
    ProcurementDecisionResult,
)
from app.orchestration.procurement_intelligence_models import (
    RecommendationType,
)
from app.orchestration.procurement_intelligence_result import (
    ProcurementIntelligenceResult,
)


class AutonomousProcurementBrain:
    """Create a safe, prioritised procurement action plan."""

    def __init__(
        self,
        policy: AutonomousProcurementPolicy | None = None,
    ) -> None:
        self._policy = policy or AutonomousProcurementPolicy(
            policy_id="default-autonomous-procurement",
            name="Default Autonomous Procurement Policy",
        )

    @property
    def policy(self) -> AutonomousProcurementPolicy:
        return self._policy

    def plan(
        self,
        decision_result: ProcurementDecisionResult,
        intelligence_result: ProcurementIntelligenceResult,
        *,
        context: AutonomousProcurementContext | None = None,
    ) -> AutonomousProcurementResult:
        if decision_result.case_id != intelligence_result.case_id:
            raise ValueError(
                "Decision and intelligence results must belong "
                "to the same procurement case."
            )

        if not self._policy.enabled:
            raise ValueError(
                "Autonomous procurement policy is disabled."
            )

        active_context = context or AutonomousProcurementContext(
            autonomy_mode=self._policy.default_mode
        )

        actions = self._build_actions(
            decision_result,
            intelligence_result,
            active_context,
        )
        confidence_score = self._calculate_confidence(
            decision_result,
            intelligence_result,
            active_context,
        )
        confidence = self._confidence_band(confidence_score)

        safe_to_execute = (
            active_context.autonomy_mode
            is AutonomyMode.CONTROLLED_AUTOMATION
            and confidence_score
            >= self._policy.minimum_execution_confidence
            and all(
                not action.requires_human_approval
                for action in actions
                if action.executable
            )
            and not active_context.human_override_required
        )

        return AutonomousProcurementResult(
            case_id=decision_result.case_id,
            confidence_score=confidence_score,
            confidence=confidence,
            actions=actions,
            safe_to_execute=safe_to_execute,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "autonomy_mode": active_context.autonomy_mode.value,
                "decision": decision_result.decision.value,
            },
        )

    def _build_actions(
        self,
        decision_result: ProcurementDecisionResult,
        intelligence_result: ProcurementIntelligenceResult,
        context: AutonomousProcurementContext,
    ) -> tuple[AutonomousProcurementAction, ...]:
        actions: list[AutonomousProcurementAction] = []

        if (
            self._policy.fail_closed_on_missing_payment
            and not context.payment_cleared
        ):
            actions.append(
                self._action(
                    AutonomousAction.SECURE_PAYMENT,
                    "Secure buyer payment",
                    "Buyer funds are not confirmed as cleared.",
                    100,
                    decision_result.decision,
                )
            )

        if (
            self._policy.fail_closed_on_missing_documents
            and not context.documents_complete
        ):
            actions.append(
                self._action(
                    AutonomousAction.COMPLETE_DOCUMENTS,
                    "Complete required documents",
                    "Required procurement documents are incomplete.",
                    95,
                    decision_result.decision,
                )
            )

        if decision_result.decision is ProcurementDecision.REJECT:
            actions.append(
                self._action(
                    AutonomousAction.REJECT,
                    "Reject procurement execution",
                    "The decision engine identified critical blockers.",
                    100,
                    decision_result.decision,
                )
            )

            if context.compensation_available:
                actions.append(
                    self._action(
                        AutonomousAction.START_COMPENSATION,
                        "Prepare compensation workflow",
                        "Rollback may be required after rejection.",
                        90,
                        decision_result.decision,
                    )
                )

        elif decision_result.decision is ProcurementDecision.HOLD:
            actions.append(
                self._action(
                    AutonomousAction.HOLD,
                    "Hold procurement",
                    "Blocking conditions must be resolved first.",
                    90,
                    decision_result.decision,
                )
            )

        elif (
            decision_result.decision
            is ProcurementDecision.MANUAL_REVIEW
        ):
            actions.append(
                self._action(
                    AutonomousAction.MANUAL_REVIEW,
                    "Request manual review",
                    "Decision confidence requires human review.",
                    85,
                    decision_result.decision,
                )
            )

        else:
            actions.append(
                self._action(
                    AutonomousAction.PROCEED,
                    "Proceed with procurement",
                    "Decision controls permit procurement to continue.",
                    80,
                    decision_result.decision,
                )
            )

        for recommendation in intelligence_result.recommendations:
            mapped = self._map_recommendation(
                recommendation.recommendation_type
            )

            if mapped is None:
                continue

            actions.append(
                self._action(
                    mapped,
                    recommendation.title,
                    recommendation.rationale,
                    int(round(recommendation.expected_value_score)),
                    decision_result.decision,
                    source_recommendation=recommendation,
                )
            )

        if (
            not context.approval_satisfied
            and decision_result.decision
            is ProcurementDecision.PROCEED
        ):
            actions.append(
                self._action(
                    AutonomousAction.REQUEST_APPROVAL,
                    "Request commercial approval",
                    "Approval is required before controlled execution.",
                    95,
                    decision_result.decision,
                )
            )

        if (
            context.shipment_ready
            and decision_result.decision
            is ProcurementDecision.PROCEED
        ):
            actions.append(
                self._action(
                    AutonomousAction.HANDOFF_SHIPMENT,
                    "Handoff to shipment workflow",
                    "Procurement is ready for logistics execution.",
                    75,
                    decision_result.decision,
                )
            )

        unique: dict[
            tuple[AutonomousAction, str],
            AutonomousProcurementAction,
        ] = {}

        for action in actions:
            key = (action.action, action.title)
            existing = unique.get(key)

            if existing is None or action.priority > existing.priority:
                unique[key] = action

        return tuple(
            sorted(
                unique.values(),
                key=lambda item: (
                    -item.priority,
                    item.action.value,
                    item.title,
                ),
            )
        )

    def _action(
        self,
        action: AutonomousAction,
        title: str,
        rationale: str,
        priority: int,
        source_decision: ProcurementDecision,
        *,
        source_recommendation=None,
    ) -> AutonomousProcurementAction:
        requires_approval = (
            self._policy.requires_human_approval(action)
        )

        return AutonomousProcurementAction(
            action=action,
            title=title,
            rationale=rationale,
            priority=max(1, min(100, priority)),
            requires_human_approval=requires_approval,
            executable=(
                action not in {
                    AutonomousAction.HOLD,
                    AutonomousAction.REJECT,
                    AutonomousAction.MANUAL_REVIEW,
                }
            ),
            source_decision=source_decision,
            source_recommendation=source_recommendation,
        )

    @staticmethod
    def _map_recommendation(
        recommendation: RecommendationType,
    ) -> AutonomousAction | None:
        return {
            RecommendationType.SELECT_SUPPLIER: (
                AutonomousAction.SELECT_SUPPLIER
            ),
            RecommendationType.NEGOTIATE_PRICE: (
                AutonomousAction.NEGOTIATE
            ),
            RecommendationType.HOLD_PROCUREMENT: (
                AutonomousAction.HOLD
            ),
            RecommendationType.ESCALATE_RISK: (
                AutonomousAction.ESCALATE_RISK
            ),
            RecommendationType.COMPLETE_DOCUMENTS: (
                AutonomousAction.COMPLETE_DOCUMENTS
            ),
            RecommendationType.SECURE_PAYMENT: (
                AutonomousAction.SECURE_PAYMENT
            ),
            RecommendationType.EXPEDITE_SHIPMENT: (
                AutonomousAction.HANDOFF_SHIPMENT
            ),
            RecommendationType.REPLENISH_INVENTORY: None,
            RecommendationType.PRIORITISE_BUYER: None,
            RecommendationType.PURSUE_OPPORTUNITY: None,
            RecommendationType.NO_ACTION: None,
        }[recommendation]

    @staticmethod
    def _calculate_confidence(
        decision_result: ProcurementDecisionResult,
        intelligence_result: ProcurementIntelligenceResult,
        context: AutonomousProcurementContext,
    ) -> float:
        score = decision_result.score

        if intelligence_result.best_supplier is not None:
            score = (
                score * 0.70
                + intelligence_result.best_supplier.score * 0.30
            )

        if context.human_override_required:
            score -= 20
        if not context.documents_complete:
            score -= 10
        if not context.payment_cleared:
            score -= 20

        return round(max(0.0, min(100.0, score)), 2)

    @staticmethod
    def _confidence_band(score: float) -> BrainConfidence:
        if score >= 90:
            return BrainConfidence.VERY_HIGH
        if score >= 75:
            return BrainConfidence.HIGH
        if score >= 50:
            return BrainConfidence.MEDIUM
        return BrainConfidence.LOW


_default_autonomous_procurement_brain = AutonomousProcurementBrain()


def get_autonomous_procurement_brain(
) -> AutonomousProcurementBrain:
    return _default_autonomous_procurement_brain