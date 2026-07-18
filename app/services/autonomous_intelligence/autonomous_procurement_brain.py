"""Central Autonomous Procurement Brain.

The brain coordinates intelligence and governance engines to produce a single
explainable recommendation. It may analyse, predict, rank, plan, draft, and
raise alerts. It may not commit suppliers, send binding quotations, issue
purchase orders, release payments, book shipments, or activate contracts
without explicit authorised approval and all mandatory safeguards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from services.autonomous_intelligence.approval_policy_engine import (
    ActionType,
    ApprovalRequest,
    ApprovalResult,
    get_approval_policy_engine,
)
from services.autonomous_intelligence.autonomous_action_planner import (
    ActionPlan,
    get_autonomous_action_planner,
)
from services.autonomous_intelligence.autonomous_brain_monitor import (
    BrainComponentStatus,
    BrainHealthReport,
    get_autonomous_brain_monitor,
)
from services.autonomous_intelligence.autonomous_priority_engine import (
    PriorityAssessment,
    PriorityItem,
    get_autonomous_priority_engine,
)
from services.autonomous_intelligence.landed_cost_forecasting_engine import (
    LandedCostForecast,
    LandedCostScenario,
    get_landed_cost_forecasting_engine,
)
from services.autonomous_intelligence.logistics_optimization_engine import (
    LogisticsOption,
    LogisticsRecommendation,
    get_logistics_optimization_engine,
)
from services.autonomous_intelligence.market_signal_engine import (
    MarketObservation,
    MarketSignal,
    get_market_signal_engine,
)
from services.autonomous_intelligence.opportunity_prediction_engine import (
    OpportunityInput,
    OpportunityPrediction,
    get_opportunity_prediction_engine,
)
from services.autonomous_intelligence.procurement_timing_engine import (
    ProcurementTimingInput,
    ProcurementTimingRecommendation,
    get_procurement_timing_engine,
)
from services.autonomous_intelligence.supply_disruption_engine import (
    DisruptionFactor,
    SupplyDisruptionAssessment,
    get_supply_disruption_engine,
)


@dataclass(frozen=True)
class AutonomousBrainCase:
    case_id: str
    market_observations: tuple[MarketObservation, ...]
    opportunity: OpportunityInput
    timing: ProcurementTimingInput
    landed_cost_scenarios: tuple[LandedCostScenario, ...]
    disruption_factors: tuple[DisruptionFactor, ...]
    logistics_options: tuple[LogisticsOption, ...]
    priority_item: PriorityItem
    approval_request: ApprovalRequest
    brain_components: tuple[BrainComponentStatus, ...]
    buyer_verified: bool
    supplier_verified: bool
    match_eligible: bool
    commercial_safeguards_passed: bool
    buyer_final_approval: bool
    funds_cleared: bool
    contract_ready: bool


@dataclass(frozen=True)
class AutonomousBrainDecision:
    case_id: str
    market_signals: tuple[MarketSignal, ...]
    opportunity_prediction: OpportunityPrediction
    timing_recommendation: ProcurementTimingRecommendation
    landed_cost_forecast: LandedCostForecast
    disruption_assessment: SupplyDisruptionAssessment
    logistics_ranking: tuple[LogisticsRecommendation, ...]
    priority_assessment: PriorityAssessment
    approval_result: ApprovalResult
    action_plan: ActionPlan
    brain_health: BrainHealthReport
    recommended_action: str
    permitted_actions: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    overall_confidence_score: int
    execution_allowed: bool
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


class AutonomousProcurementBrain:
    """Coordinate prediction, planning, approval, and monitoring."""

    def __init__(self) -> None:
        self._market = get_market_signal_engine()
        self._opportunity = get_opportunity_prediction_engine()
        self._timing = get_procurement_timing_engine()
        self._landed_cost = get_landed_cost_forecasting_engine()
        self._disruption = get_supply_disruption_engine()
        self._logistics = get_logistics_optimization_engine()
        self._priority = get_autonomous_priority_engine()
        self._approval = get_approval_policy_engine()
        self._planner = get_autonomous_action_planner()
        self._monitor = get_autonomous_brain_monitor()

    def evaluate(
        self,
        case: AutonomousBrainCase,
    ) -> AutonomousBrainDecision:
        market_signals = tuple(
            self._market.analyse(
                case.market_observations
            )
        )

        opportunity_input = OpportunityInput(
            **{
                **case.opportunity.__dict__,
                "market_signals": market_signals,
            }
        )

        opportunity = self._opportunity.predict(
            opportunity_input
        )
        timing = self._timing.evaluate(
            case.timing
        )
        landed_cost = self._landed_cost.forecast(
            case.landed_cost_scenarios
        )
        disruption = self._disruption.assess(
            case.disruption_factors
        )
        logistics = tuple(
            self._logistics.rank(
                case.logistics_options
            )
        )
        priority = self._priority.assess(
            case.priority_item
        )
        approval = self._approval.evaluate(
            case.approval_request
        )
        action_plan = self._planner.create_plan(
            plan_id=f"PLAN-{case.case_id}",
            case_id=case.case_id,
            buyer_verified=case.buyer_verified,
            supplier_verified=case.supplier_verified,
            match_eligible=case.match_eligible,
            commercial_safeguards_passed=(
                case.commercial_safeguards_passed
            ),
            buyer_final_approval=case.buyer_final_approval,
            funds_cleared=case.funds_cleared,
            contract_ready=case.contract_ready,
        )
        health = self._monitor.evaluate(
            case.brain_components
        )

        blockers = list(
            dict.fromkeys(
                [
                    *opportunity.blockers,
                    *timing.blockers,
                    *approval.blockers,
                    *action_plan.blockers,
                    *(
                        (
                            "Supply disruption risk is critical.",
                        )
                        if (
                            not disruption.sourcing_allowed
                        )
                        else ()
                    ),
                    *(
                        (
                            "Autonomous brain health is below threshold.",
                        )
                        if not health.healthy
                        else ()
                    ),
                ]
            )
        )

        warnings = list(
            dict.fromkeys(
                [
                    *opportunity.warnings,
                    *timing.warnings,
                    *landed_cost.warnings,
                    *(
                        alert.description
                        for alert in health.alerts
                        if not alert.blocking
                    ),
                ]
            )
        )

        permitted_actions = [
            "Analyse evidence",
            "Rank opportunities",
            "Prepare comparison",
            "Create review tasks",
            "Raise alerts",
            "Generate non-binding drafts",
        ]

        if approval.allowed:
            permitted_actions.append(
                f"Proceed with authorised action: "
                f"{approval.action_type.value}"
            )

        prohibited_actions = [
            "No unauthorised supplier commitment",
            "No binding buyer quotation without approval",
            "No purchase order without approval",
            "No payment release without cleared funds",
            "No shipment booking without approval",
            "No contract activation without signatures",
            "No disclosure of protected commercial relationships",
        ]

        execution_allowed = bool(
            approval.allowed
            and not blockers
            and health.healthy
            and disruption.sourcing_allowed
            and case.contract_ready
            and case.funds_cleared
            and case.buyer_final_approval
        )

        confidence_values = [
            opportunity.confidence_score,
            landed_cost.confidence_score,
            max(
                0,
                100 - disruption.overall_risk_score,
            ),
            health.health_score,
        ]
        confidence = round(
            sum(confidence_values)
            / len(confidence_values)
        )

        recommended_action = self._recommended_action(
            opportunity=opportunity,
            timing=timing,
            approval=approval,
            logistics=logistics,
            blockers=blockers,
        )

        explanation = (
            f"Case {case.case_id} received an autonomous confidence "
            f"score of {confidence}/100. The recommended action is: "
            f"{recommended_action} Execution is "
            f"{'allowed' if execution_allowed else 'not allowed'}."
        )

        return AutonomousBrainDecision(
            case_id=case.case_id,
            market_signals=market_signals,
            opportunity_prediction=opportunity,
            timing_recommendation=timing,
            landed_cost_forecast=landed_cost,
            disruption_assessment=disruption,
            logistics_ranking=logistics,
            priority_assessment=priority,
            approval_result=approval,
            action_plan=action_plan,
            brain_health=health,
            recommended_action=recommended_action,
            permitted_actions=tuple(permitted_actions),
            prohibited_actions=tuple(prohibited_actions),
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            overall_confidence_score=confidence,
            execution_allowed=execution_allowed,
            explanation=explanation,
        )

    @staticmethod
    def _recommended_action(
        *,
        opportunity: OpportunityPrediction,
        timing: ProcurementTimingRecommendation,
        approval: ApprovalResult,
        logistics: tuple[LogisticsRecommendation, ...],
        blockers: list[str],
    ) -> str:
        if blockers:
            return (
                "Resolve all blockers before progressing."
            )

        best_logistics = next(
            (
                option
                for option in logistics
                if option.recommended
            ),
            None,
        )

        if not approval.allowed:
            return (
                "Prepare the case for authorised human approval."
            )

        if best_logistics is None:
            return (
                "Identify a compliant logistics option before execution."
            )

        return (
            f"{opportunity.recommended_action} "
            f"Timing: {timing.decision.value}. "
            f"Preferred logistics option: {best_logistics.option_id}."
        )


_brain = AutonomousProcurementBrain()


def get_autonomous_procurement_brain() -> AutonomousProcurementBrain:
    return _brain