"""Contract Readiness Engine for GPNI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ContractReadinessDecision(str, Enum):
    NOT_READY = "Not Ready"
    READY_FOR_REVIEW = "Ready for Review"
    READY_FOR_SIGNATURE = "Ready for Signature"
    ACTIVE = "Active"


@dataclass(frozen=True)
class ContractReadinessResult:
    decision: ContractReadinessDecision
    score: int
    buyer_signature_allowed: bool
    supplier_signature_allowed: bool
    activation_allowed: bool
    missing_items: tuple[str, ...]
    blockers: tuple[str, ...]
    conditions: tuple[str, ...]
    explanation: str


class ContractReadinessEngine:
    """Verify every prerequisite before contract activation."""

    REQUIRED_ITEMS = (
        "buyer_legal_identity_verified",
        "supplier_legal_identity_verified",
        "product_specification_confirmed",
        "quantity_confirmed",
        "price_confirmed",
        "currency_confirmed",
        "incoterm_confirmed",
        "delivery_schedule_confirmed",
        "payment_terms_confirmed",
        "quality_terms_confirmed",
        "required_documents_confirmed",
        "dispute_resolution_confirmed",
        "governing_law_confirmed",
        "compliance_cleared",
        "buyer_final_approval",
        "supplier_final_approval",
    )

    def evaluate(
        self,
        contract_case: dict[str, Any],
    ) -> ContractReadinessResult:
        missing_items = [
            item
            for item in self.REQUIRED_ITEMS
            if not contract_case.get(item)
        ]

        blockers: list[str] = []
        conditions: list[str] = []

        if not contract_case.get(
            "commercial_safeguards_passed"
        ):
            blockers.append(
                "Commercial safeguards have not passed."
            )

        if not contract_case.get(
            "payment_protection_passed"
        ):
            blockers.append(
                "Payment protection has not passed."
            )

        if contract_case.get(
            "sanctions_or_compliance_hold"
        ):
            blockers.append(
                "A sanctions or compliance hold is active."
            )

        if contract_case.get(
            "unresolved_material_risk"
        ):
            blockers.append(
                "A material risk remains unresolved."
            )

        if contract_case.get(
            "relationship_conflict_detected"
        ):
            blockers.append(
                "A protected relationship conflict "
                "remains unresolved."
            )

        completion_count = (
            len(self.REQUIRED_ITEMS)
            - len(missing_items)
        )

        score = round(
            completion_count
            / len(self.REQUIRED_ITEMS)
            * 80
            + (
                10
                if contract_case.get(
                    "commercial_safeguards_passed"
                )
                else 0
            )
            + (
                10
                if contract_case.get(
                    "payment_protection_passed"
                )
                else 0
            )
        )

        score = max(
            0,
            min(100, score),
        )

        buyer_signature_allowed = (
            not blockers
            and not missing_items
            and bool(
                contract_case.get(
                    "authorised_buyer_signatory"
                )
            )
        )

        supplier_signature_allowed = (
            not blockers
            and not missing_items
            and bool(
                contract_case.get(
                    "authorised_supplier_signatory"
                )
            )
        )

        activation_allowed = (
            buyer_signature_allowed
            and supplier_signature_allowed
            and bool(
                contract_case.get("buyer_signed")
            )
            and bool(
                contract_case.get("supplier_signed")
            )
            and bool(
                contract_case.get(
                    "cleared_funds_or_approved_credit"
                )
            )
        )

        if activation_allowed:
            decision = ContractReadinessDecision.ACTIVE
        elif (
            buyer_signature_allowed
            and supplier_signature_allowed
        ):
            decision = (
                ContractReadinessDecision.READY_FOR_SIGNATURE
            )
        elif score >= 70 and not blockers:
            decision = (
                ContractReadinessDecision.READY_FOR_REVIEW
            )
        else:
            decision = ContractReadinessDecision.NOT_READY

        if missing_items:
            conditions.append(
                "Complete all required contract fields "
                "and approvals."
            )

        explanation = (
            f"Contract readiness score is {score}/100. "
            f"Decision: {decision.value}. Contract activation "
            "remains prohibited until both authorised parties "
            "sign and cleared funds or approved credit are confirmed."
        )

        return ContractReadinessResult(
            decision=decision,
            score=score,
            buyer_signature_allowed=buyer_signature_allowed,
            supplier_signature_allowed=supplier_signature_allowed,
            activation_allowed=activation_allowed,
            missing_items=tuple(missing_items),
            blockers=tuple(blockers),
            conditions=tuple(conditions),
            explanation=explanation,
        )


_engine = ContractReadinessEngine()


def get_contract_readiness_engine() -> ContractReadinessEngine:
    return _engine