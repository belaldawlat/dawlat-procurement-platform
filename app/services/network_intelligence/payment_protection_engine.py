"""Payment Protection Engine for GPNI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class PaymentDecision(str, Enum):
    BLOCKED = "Blocked"
    HOLD = "Hold"
    PARTIAL_RELEASE = "Partial Release"
    RELEASE_APPROVED = "Release Approved"


@dataclass(frozen=True)
class PaymentProtectionResult:
    decision: PaymentDecision
    releasable_amount: float
    retained_amount: float
    buyer_funds_cleared: bool
    milestone_satisfied: bool
    blockers: tuple[str, ...]
    conditions: tuple[str, ...]
    audit_message: str


class PaymentProtectionEngine:
    """Protect buyer funds, margin and payment milestones."""

    def evaluate(
        self,
        payment_case: dict[str, Any],
    ) -> PaymentProtectionResult:
        buyer_funds = _number(
            payment_case.get("buyer_funds_cleared")
        )
        requested_release = _number(
            payment_case.get(
                "requested_supplier_release"
            )
        )
        protected_profit = _number(
            payment_case.get("protected_profit")
        )
        protected_cost_buffer = _number(
            payment_case.get(
                "protected_cost_buffer"
            )
        )
        total_obligation = _number(
            payment_case.get(
                "total_supplier_obligation"
            )
        )

        blockers: list[str] = []
        conditions: list[str] = []

        buyer_funds_cleared = (
            buyer_funds > 0
            and bool(
                payment_case.get(
                    "bank_clearance_confirmed"
                )
            )
        )

        milestone_satisfied = all(
            [
                bool(
                    payment_case.get(
                        "buyer_final_approval"
                    )
                ),
                bool(
                    payment_case.get(
                        "supplier_milestone_confirmed"
                    )
                ),
                bool(
                    payment_case.get(
                        "documents_verified"
                    )
                ),
                bool(
                    payment_case.get(
                        "compliance_cleared"
                    )
                ),
                bool(
                    payment_case.get(
                        "authorised_payment_approval"
                    )
                ),
            ]
        )

        if not buyer_funds_cleared:
            blockers.append(
                "Buyer funds are not cleared and verified."
            )

        if not payment_case.get(
            "buyer_final_approval"
        ):
            blockers.append(
                "Buyer final approval is missing."
            )

        if not payment_case.get(
            "supplier_milestone_confirmed"
        ):
            blockers.append(
                "Supplier milestone is not confirmed."
            )

        if not payment_case.get(
            "documents_verified"
        ):
            blockers.append(
                "Required documents are not verified."
            )

        if not payment_case.get(
            "compliance_cleared"
        ):
            blockers.append(
                "Compliance clearance is incomplete."
            )

        if not payment_case.get(
            "authorised_payment_approval"
        ):
            blockers.append(
                "Authorised internal payment approval is missing."
            )

        maximum_safe_release = max(
            0.0,
            buyer_funds
            - protected_profit
            - protected_cost_buffer,
        )

        if total_obligation > 0:
            maximum_safe_release = min(
                maximum_safe_release,
                total_obligation,
            )

        releasable_amount = min(
            requested_release,
            maximum_safe_release,
        )

        if requested_release > maximum_safe_release:
            conditions.append(
                "Requested payment exceeds the protected "
                "releasable amount."
            )

        retained_amount = max(
            0.0,
            buyer_funds - releasable_amount,
        )

        if blockers:
            decision = PaymentDecision.BLOCKED
            releasable_amount = 0.0
        elif not milestone_satisfied:
            decision = PaymentDecision.HOLD
            releasable_amount = 0.0
        elif releasable_amount < requested_release:
            decision = PaymentDecision.PARTIAL_RELEASE
        else:
            decision = PaymentDecision.RELEASE_APPROVED

        audit_message = (
            f"Payment decision: {decision.value}. "
            f"Releasable amount: {releasable_amount:.2f}. "
            f"Retained amount: {retained_amount:.2f}."
        )

        return PaymentProtectionResult(
            decision=decision,
            releasable_amount=round(
                releasable_amount,
                2,
            ),
            retained_amount=round(
                retained_amount,
                2,
            ),
            buyer_funds_cleared=buyer_funds_cleared,
            milestone_satisfied=milestone_satisfied,
            blockers=tuple(blockers),
            conditions=tuple(conditions),
            audit_message=audit_message,
        )


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


_engine = PaymentProtectionEngine()


def get_payment_protection_engine() -> PaymentProtectionEngine:
    return _engine