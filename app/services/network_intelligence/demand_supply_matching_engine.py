"""Demand-Supply Matching Engine for GPNI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class MatchCandidate:
    match_id: str
    demand_id: str
    supply_id: str
    buyer_name: str
    supplier_name: str
    product_name: str
    destination_country: str
    demand_quantity: float
    supply_capacity: float
    unit: str
    buyer_target_price: float | None
    supplier_unit_price: float | None
    estimated_landed_cost: float | None
    expected_sale_price: float | None
    currency: str
    demand_score: int
    supply_score: int
    buyer_qualification_score: int
    supplier_qualification_score: int
    risk_score: int
    trust_score: int
    demand_matching_allowed: bool
    supply_matching_allowed: bool
    buyer_approved_for_matching: bool
    supplier_approved_for_matching: bool
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatchAssessment:
    match_id: str
    overall_score: int
    commercial_score: int
    capability_score: int
    trust_component_score: int
    risk_adjusted_score: int
    estimated_margin_percent: float | None
    eligible: bool
    quotation_request_allowed: bool
    binding_action_allowed: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    reasons: tuple[str, ...]
    next_actions: tuple[str, ...]
    explanation: str
    assessed_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class DemandSupplyMatchingEngine:
    """Evaluate and rank protected buyer-supplier matches."""

    def assess(self, candidate: MatchCandidate) -> MatchAssessment:
        blockers: list[str] = []
        warnings: list[str] = []
        reasons: list[str] = []
        next_actions: list[str] = []

        if not candidate.demand_matching_allowed:
            blockers.append("Demand is not approved for matching.")
        if not candidate.supply_matching_allowed:
            blockers.append("Supply is not approved for matching.")
        if not candidate.buyer_approved_for_matching:
            blockers.append("Buyer qualification is incomplete.")
        if not candidate.supplier_approved_for_matching:
            blockers.append("Supplier qualification is incomplete.")
        if candidate.demand_quantity <= 0:
            blockers.append("Demand quantity is invalid.")
        if candidate.supply_capacity <= 0:
            blockers.append("Supply capacity is invalid.")
        if candidate.supply_capacity < candidate.demand_quantity:
            blockers.append("Supplier capacity is below buyer demand.")

        if candidate.risk_score >= 80:
            blockers.append("Risk score is critically high.")
        elif candidate.risk_score >= 60:
            warnings.append("Risk score requires enhanced review.")

        if candidate.trust_score < 50:
            blockers.append("Trust score is below the minimum threshold.")
        elif candidate.trust_score < 70:
            warnings.append("Trust score is moderate.")

        capability_score = round(
            min(
                100.0,
                (candidate.supply_capacity / max(candidate.demand_quantity, 1.0))
                * 70.0
                + (15.0 if candidate.unit else 0.0)
                + (15.0 if candidate.product_name else 0.0),
            )
        )

        estimated_margin_percent: float | None = None
        commercial_score = 40

        if (
            candidate.estimated_landed_cost is not None
            and candidate.expected_sale_price is not None
            and candidate.expected_sale_price > 0
        ):
            estimated_margin_percent = (
                (candidate.expected_sale_price - candidate.estimated_landed_cost)
                / candidate.expected_sale_price
                * 100.0
            )

            if estimated_margin_percent >= 25:
                commercial_score = 100
                reasons.append("Projected margin is strong.")
            elif estimated_margin_percent >= 15:
                commercial_score = 80
                reasons.append("Projected margin is commercially acceptable.")
            elif estimated_margin_percent >= 8:
                commercial_score = 60
                warnings.append("Projected margin is narrow.")
            else:
                commercial_score = 25
                blockers.append(
                    "Projected margin is below the protected threshold."
                )
        else:
            warnings.append("Landed cost or expected sale price is incomplete.")
            next_actions.append(
                "Complete landed-cost and sale-price validation."
            )

        trust_component_score = max(
            0,
            min(
                100,
                round(
                    candidate.trust_score * 0.50
                    + candidate.buyer_qualification_score * 0.25
                    + candidate.supplier_qualification_score * 0.25
                ),
            ),
        )

        overall_score = round(
            candidate.demand_score * 0.20
            + candidate.supply_score * 0.20
            + capability_score * 0.20
            + commercial_score * 0.20
            + trust_component_score * 0.20
        )

        risk_adjusted_score = max(
            0,
            min(
                100,
                round(overall_score - candidate.risk_score * 0.35),
            ),
        )

        critical_blockers = {
            "Demand is not approved for matching.",
            "Supply is not approved for matching.",
            "Buyer qualification is incomplete.",
            "Supplier qualification is incomplete.",
            "Supplier capacity is below buyer demand.",
            "Risk score is critically high.",
            "Trust score is below the minimum threshold.",
            "Projected margin is below the protected threshold.",
        }

        eligible = (
            risk_adjusted_score >= 65
            and not any(
                blocker in critical_blockers
                for blocker in blockers
            )
        )

        quotation_request_allowed = eligible
        binding_action_allowed = False

        if eligible:
            reasons.append(
                "Demand and supply are eligible for formal quotation comparison."
            )
            next_actions.extend(
                [
                    "Request a formal supplier quotation.",
                    "Validate landed cost, documents, lead time and Incoterms.",
                    "Present the final commercial offer to the buyer for approval.",
                ]
            )

        explanation = (
            f"Match scored {risk_adjusted_score}/100 after risk adjustment. "
            f"Quotation requests are "
            f"{'allowed' if quotation_request_allowed else 'not allowed'}. "
            "Binding action remains prohibited until buyer approval, cleared "
            "funds, contract readiness and commercial safeguards pass."
        )

        return MatchAssessment(
            match_id=candidate.match_id,
            overall_score=overall_score,
            commercial_score=commercial_score,
            capability_score=capability_score,
            trust_component_score=trust_component_score,
            risk_adjusted_score=risk_adjusted_score,
            estimated_margin_percent=(
                round(estimated_margin_percent, 2)
                if estimated_margin_percent is not None
                else None
            ),
            eligible=eligible,
            quotation_request_allowed=quotation_request_allowed,
            binding_action_allowed=binding_action_allowed,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            reasons=tuple(reasons),
            next_actions=tuple(dict.fromkeys(next_actions)),
            explanation=explanation,
        )

    def rank(
        self,
        candidates: Iterable[MatchCandidate],
    ) -> list[MatchAssessment]:
        results = [self.assess(candidate) for candidate in candidates]
        results.sort(
            key=lambda item: (
                not item.eligible,
                -item.risk_adjusted_score,
                -(
                    item.estimated_margin_percent
                    if item.estimated_margin_percent is not None
                    else -999.0
                ),
            )
        )
        return results


_engine = DemandSupplyMatchingEngine()


def get_demand_supply_matching_engine() -> DemandSupplyMatchingEngine:
    return _engine