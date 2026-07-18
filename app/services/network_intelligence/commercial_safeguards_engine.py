"""Commercial Safeguards Engine for GPNI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SafeguardDecision(str, Enum):
    BLOCK = "Block"
    REVIEW = "Review"
    PROCEED_WITH_CONDITIONS = "Proceed with Conditions"
    PROCEED = "Proceed"


@dataclass(frozen=True)
class CommercialSafeguardResult:
    decision: SafeguardDecision
    score: int
    margin_percent: float | None
    maximum_supplier_commitment: float
    buyer_funds_required: float
    blockers: tuple[str, ...]
    conditions: tuple[str, ...]
    warnings: tuple[str, ...]
    explanation: str


class CommercialSafeguardsEngine:
    """Protect margin, cleared funds and commercial relationships."""

    def evaluate(
        self,
        case: dict[str, Any],
    ) -> CommercialSafeguardResult:
        blockers: list[str] = []
        conditions: list[str] = []
        warnings: list[str] = []
        score = 100

        sale_value = _number(
            case.get("buyer_sale_value")
        )
        landed_cost = _number(
            case.get("landed_cost")
        )
        supplier_commitment = _number(
            case.get("supplier_commitment")
        )
        cleared_funds = _number(
            case.get("cleared_buyer_funds")
        )
        minimum_margin = _number(
            case.get("minimum_margin_percent") or 15.0
        )

        margin_percent: float | None = None

        if sale_value > 0 and landed_cost > 0:
            margin_percent = (
                (sale_value - landed_cost)
                / sale_value
                * 100.0
            )

            if margin_percent < minimum_margin:
                blockers.append(
                    "Protected minimum margin is not achieved."
                )
                score -= 40
            elif margin_percent < minimum_margin + 5:
                warnings.append(
                    "Margin buffer is narrow."
                )
                score -= 10
        else:
            blockers.append(
                "Sale value and landed cost must be confirmed."
            )
            score -= 35

        if not case.get(
            "buyer_final_quotation_approved"
        ):
            blockers.append(
                "Buyer has not approved the final quotation."
            )
            score -= 30

        if not case.get(
            "supplier_final_terms_confirmed"
        ):
            blockers.append(
                "Supplier final terms are not confirmed."
            )
            score -= 20

        if not case.get("compliance_cleared"):
            blockers.append(
                "Compliance clearance is incomplete."
            )
            score -= 30

        if not case.get(
            "required_documents_confirmed"
        ):
            blockers.append(
                "Required trade documents are not confirmed."
            )
            score -= 25

        if not case.get(
            "currency_risk_reviewed"
        ):
            warnings.append(
                "Currency exposure has not been reviewed."
            )
            score -= 5

        if not case.get("insurance_reviewed"):
            warnings.append(
                "Insurance protection has not been reviewed."
            )
            score -= 5

        maximum_supplier_commitment = max(
            0.0,
            min(
                cleared_funds,
                landed_cost,
            ),
        )

        buyer_funds_required = max(
            0.0,
            supplier_commitment
            + _number(
                case.get("protected_cost_buffer")
            )
            + _number(
                case.get("minimum_profit_amount")
            ),
        )

        if supplier_commitment > cleared_funds:
            blockers.append(
                "Supplier commitment exceeds cleared buyer funds."
            )
            score -= 40

        if cleared_funds < buyer_funds_required:
            conditions.append(
                "Obtain additional cleared buyer funds "
                "before supplier commitment."
            )

        if case.get(
            "relationship_conflict_detected"
        ):
            blockers.append(
                "Protected commercial relationship conflict detected."
            )
            score -= 25

        score = max(
            0,
            min(100, score),
        )

        if blockers:
            decision = SafeguardDecision.BLOCK
        elif conditions:
            decision = (
                SafeguardDecision.PROCEED_WITH_CONDITIONS
            )
        elif warnings:
            decision = SafeguardDecision.REVIEW
        else:
            decision = SafeguardDecision.PROCEED

        explanation = (
            f"Commercial safeguard score is {score}/100. "
            f"Decision: {decision.value}. Supplier commitment "
            f"may not exceed {maximum_supplier_commitment:.2f} "
            "until all controls remain satisfied."
        )

        return CommercialSafeguardResult(
            decision=decision,
            score=score,
            margin_percent=(
                round(margin_percent, 2)
                if margin_percent is not None
                else None
            ),
            maximum_supplier_commitment=round(
                maximum_supplier_commitment,
                2,
            ),
            buyer_funds_required=round(
                buyer_funds_required,
                2,
            ),
            blockers=tuple(blockers),
            conditions=tuple(conditions),
            warnings=tuple(warnings),
            explanation=explanation,
        )


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


_engine = CommercialSafeguardsEngine()


def get_commercial_safeguards_engine() -> CommercialSafeguardsEngine:
    return _engine