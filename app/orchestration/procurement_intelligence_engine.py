"""Enterprise procurement intelligence and recommendation engine."""

from __future__ import annotations

from app.orchestration.procurement_intelligence_models import (
    IntelligenceCategory,
    IntelligencePriority,
    ProcurementIntelligenceContext,
    ProcurementRecommendation,
    RecommendationType,
    SupplierIntelligenceInput,
)
from app.orchestration.procurement_intelligence_policy import (
    ProcurementIntelligencePolicy,
)
from app.orchestration.procurement_intelligence_result import (
    ProcurementIntelligenceResult,
    SupplierRanking,
)


class ProcurementIntelligenceEngine:
    def __init__(
        self,
        policy: ProcurementIntelligencePolicy | None = None,
    ) -> None:
        self._policy = policy or ProcurementIntelligencePolicy(
            policy_id="default-procurement-intelligence",
            name="Default Procurement Intelligence Policy",
        )

    @property
    def policy(self) -> ProcurementIntelligencePolicy:
        return self._policy

    def evaluate(
        self,
        case_id: str,
        suppliers: tuple[SupplierIntelligenceInput, ...],
        *,
        context: ProcurementIntelligenceContext | None = None,
    ) -> ProcurementIntelligenceResult:
        cleaned_case_id = str(case_id or "").strip()

        if not cleaned_case_id:
            raise ValueError("Procurement case ID is required.")

        if not self._policy.enabled:
            raise ValueError("Procurement intelligence policy is disabled.")

        active_context = context or ProcurementIntelligenceContext()
        rankings = self._rank_suppliers(suppliers)
        recommendations = self._build_recommendations(
            rankings,
            active_context,
        )

        return ProcurementIntelligenceResult(
            case_id=cleaned_case_id,
            rankings=rankings,
            recommendations=recommendations,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            metadata={
                "supplier_count": len(suppliers),
                "recommendation_count": len(recommendations),
            },
        )

    def _rank_suppliers(
        self,
        suppliers: tuple[SupplierIntelligenceInput, ...],
    ) -> tuple[SupplierRanking, ...]:
        if not suppliers:
            return ()

        minimum_cost = min(s.landed_cost for s in suppliers)
        maximum_cost = max(s.landed_cost for s in suppliers)
        minimum_lead_time = min(s.lead_time_days for s in suppliers)
        maximum_lead_time = max(s.lead_time_days for s in suppliers)

        scored: list[tuple[SupplierIntelligenceInput, float]] = []

        for supplier in suppliers:
            cost_score = self._inverse_normalise(
                supplier.landed_cost,
                minimum_cost,
                maximum_cost,
            )
            lead_time_score = self._inverse_normalise(
                float(supplier.lead_time_days),
                float(minimum_lead_time),
                float(maximum_lead_time),
            )
            risk_adjustment = max(
                0.0,
                1.0 - supplier.risk_score / 100.0,
            )

            raw_score = (
                cost_score * self._policy.landed_cost_weight
                + supplier.quality_score / 100.0
                * self._policy.quality_weight
                + supplier.reliability_score / 100.0
                * self._policy.reliability_weight
                + supplier.compliance_score / 100.0
                * self._policy.compliance_weight
                + lead_time_score
                * self._policy.lead_time_weight
            )

            scored.append(
                (
                    supplier,
                    round(raw_score * risk_adjustment * 100.0, 2),
                )
            )

        ordered = sorted(
            scored,
            key=lambda item: (
                -item[1],
                item[0].landed_cost,
                item[0].supplier_id,
            ),
        )

        return tuple(
            SupplierRanking(
                rank=index,
                supplier_id=supplier.supplier_id,
                supplier_name=supplier.supplier_name,
                quotation_id=supplier.quotation_id,
                score=score,
                landed_cost=supplier.landed_cost,
                risk_score=supplier.risk_score,
            )
            for index, (supplier, score)
            in enumerate(ordered, start=1)
        )

    def _build_recommendations(
        self,
        rankings: tuple[SupplierRanking, ...],
        context: ProcurementIntelligenceContext,
    ) -> tuple[ProcurementRecommendation, ...]:
        recommendations: list[ProcurementRecommendation] = []

        if rankings:
            best = rankings[0]

            if best.risk_score >= self._policy.critical_risk_score:
                recommendations.append(
                    ProcurementRecommendation(
                        recommendation_type=RecommendationType.ESCALATE_RISK,
                        title="Escalate supplier risk",
                        rationale=(
                            "The highest-ranked supplier still has "
                            "critical risk exposure."
                        ),
                        priority=IntelligencePriority.CRITICAL,
                        category=IntelligenceCategory.RISK,
                        expected_value_score=95,
                        supplier_id=best.supplier_id,
                        quotation_id=best.quotation_id,
                    )
                )
            elif (
                best.risk_score
                > self._policy.maximum_acceptable_risk_score
            ):
                recommendations.append(
                    ProcurementRecommendation(
                        recommendation_type=RecommendationType.HOLD_PROCUREMENT,
                        title="Hold supplier selection",
                        rationale=(
                            "Supplier risk exceeds the approved "
                            "operating threshold."
                        ),
                        priority=IntelligencePriority.HIGH,
                        category=IntelligenceCategory.RISK,
                        expected_value_score=85,
                        supplier_id=best.supplier_id,
                        quotation_id=best.quotation_id,
                    )
                )
            else:
                recommendations.append(
                    ProcurementRecommendation(
                        recommendation_type=RecommendationType.SELECT_SUPPLIER,
                        title="Select highest-value supplier",
                        rationale=(
                            "This supplier provides the strongest "
                            "combined value across landed cost, quality, "
                            "reliability, compliance and lead time."
                        ),
                        priority=IntelligencePriority.HIGH,
                        category=IntelligenceCategory.SUPPLIER,
                        expected_value_score=best.score,
                        supplier_id=best.supplier_id,
                        quotation_id=best.quotation_id,
                    )
                )

            if len(rankings) > 1:
                spread = round(
                    rankings[1].landed_cost
                    - rankings[0].landed_cost,
                    2,
                )

                if spread > 0:
                    recommendations.append(
                        ProcurementRecommendation(
                            recommendation_type=RecommendationType.NEGOTIATE_PRICE,
                            title="Use competitive quote leverage",
                            rationale=(
                                "Supplier pricing differences can support "
                                "further commercial negotiation."
                            ),
                            priority=IntelligencePriority.MEDIUM,
                            category=IntelligenceCategory.LANDED_COST,
                            expected_value_score=min(100.0, 60.0 + spread),
                            supplier_id=best.supplier_id,
                            quotation_id=best.quotation_id,
                            metadata={"landed_cost_spread": spread},
                        )
                    )

        if not context.buyer_payment_cleared:
            recommendations.append(
                ProcurementRecommendation(
                    recommendation_type=RecommendationType.SECURE_PAYMENT,
                    title="Secure buyer payment",
                    rationale=(
                        "Buyer funds must clear before supplier "
                        "commitment or purchase-order release."
                    ),
                    priority=IntelligencePriority.CRITICAL,
                    category=IntelligenceCategory.CASH_FLOW,
                    expected_value_score=100,
                )
            )

        if not context.documents_complete:
            recommendations.append(
                ProcurementRecommendation(
                    recommendation_type=RecommendationType.COMPLETE_DOCUMENTS,
                    title="Complete procurement documents",
                    rationale=(
                        "Missing documents create compliance, customs "
                        "and execution risk."
                    ),
                    priority=IntelligencePriority.HIGH,
                    category=IntelligenceCategory.COMPLIANCE,
                    expected_value_score=90,
                )
            )

        if (
            context.shipment_delay_days
            >= self._policy.urgent_shipment_delay_days
        ):
            recommendations.append(
                ProcurementRecommendation(
                    recommendation_type=RecommendationType.EXPEDITE_SHIPMENT,
                    title="Escalate delayed shipment",
                    rationale=(
                        "Shipment delay exceeds the urgent "
                        "intervention threshold."
                    ),
                    priority=IntelligencePriority.HIGH,
                    category=IntelligenceCategory.SHIPMENT,
                    expected_value_score=85,
                    metadata={
                        "shipment_delay_days": context.shipment_delay_days,
                    },
                )
            )

        if (
            context.inventory_days_remaining is not None
            and context.inventory_days_remaining
            <= self._policy.low_inventory_days_threshold
        ):
            recommendations.append(
                ProcurementRecommendation(
                    recommendation_type=RecommendationType.REPLENISH_INVENTORY,
                    title="Prioritise inventory replenishment",
                    rationale=(
                        "Projected inventory coverage is below "
                        "the operating threshold."
                    ),
                    priority=IntelligencePriority.HIGH,
                    category=IntelligenceCategory.INVENTORY,
                    expected_value_score=88,
                    metadata={
                        "inventory_days_remaining": (
                            context.inventory_days_remaining
                        ),
                    },
                )
            )

        if (
            context.opportunity_score
            >= self._policy.high_opportunity_score
            and (
                context.margin_percentage is None
                or context.margin_percentage
                >= self._policy.minimum_margin_percentage
            )
        ):
            recommendations.append(
                ProcurementRecommendation(
                    recommendation_type=RecommendationType.PURSUE_OPPORTUNITY,
                    title="Prioritise high-value opportunity",
                    rationale=(
                        "Opportunity strength and expected margin "
                        "meet the strategic pursuit threshold."
                    ),
                    priority=IntelligencePriority.HIGH,
                    category=IntelligenceCategory.OPPORTUNITY,
                    expected_value_score=context.opportunity_score,
                    metadata={
                        "margin_percentage": context.margin_percentage,
                    },
                )
            )

        if context.buyer_priority_score >= 80:
            recommendations.append(
                ProcurementRecommendation(
                    recommendation_type=RecommendationType.PRIORITISE_BUYER,
                    title="Prioritise strategic buyer",
                    rationale=(
                        "Buyer priority exceeds the strategic "
                        "service threshold."
                    ),
                    priority=IntelligencePriority.MEDIUM,
                    category=IntelligenceCategory.BUYER,
                    expected_value_score=context.buyer_priority_score,
                )
            )

        if not recommendations:
            recommendations.append(
                ProcurementRecommendation(
                    recommendation_type=RecommendationType.NO_ACTION,
                    title="No immediate action required",
                    rationale=(
                        "No material procurement exception or "
                        "priority condition was detected."
                    ),
                    priority=IntelligencePriority.LOW,
                    category=IntelligenceCategory.RISK,
                    expected_value_score=50,
                    action_required=False,
                )
            )

        return tuple(
            sorted(
                recommendations,
                key=lambda recommendation: (
                    self._priority_rank(recommendation.priority),
                    -recommendation.expected_value_score,
                    recommendation.recommendation_type.value,
                ),
            )
        )

    @staticmethod
    def _inverse_normalise(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        if maximum == minimum:
            return 1.0

        return 1.0 - (
            (value - minimum) / (maximum - minimum)
        )

    @staticmethod
    def _priority_rank(priority: IntelligencePriority) -> int:
        return {
            IntelligencePriority.CRITICAL: 0,
            IntelligencePriority.HIGH: 1,
            IntelligencePriority.MEDIUM: 2,
            IntelligencePriority.LOW: 3,
        }[priority]


_default_procurement_intelligence_engine = ProcurementIntelligenceEngine()


def get_procurement_intelligence_engine() -> ProcurementIntelligenceEngine:
    return _default_procurement_intelligence_engine