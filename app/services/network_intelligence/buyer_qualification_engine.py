"""Buyer Qualification Engine for the Global Procurement Network Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class BuyerQualificationStatus(str, Enum):
    """Supported buyer qualification outcomes."""

    REJECTED = "Rejected"
    NEEDS_REVIEW = "Needs Review"
    QUALIFIED = "Qualified"
    VERIFIED = "Verified"


@dataclass(frozen=True)
class BuyerQualificationResult:
    """Immutable result returned by the buyer qualification engine."""

    score: int
    confidence_score: int
    status: BuyerQualificationStatus
    approved_for_matching: bool
    approved_for_credit: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    reasons: tuple[str, ...]


class BuyerQualificationEngine:
    """Evaluate buyer identity, contact, credit and payment readiness."""

    def qualify(self, buyer: dict[str, Any]) -> BuyerQualificationResult:
        """Qualify a buyer using deterministic procurement rules."""

        score = 0
        confidence = 20

        blockers: list[str] = []
        warnings: list[str] = []
        reasons: list[str] = []

        if buyer.get("company_name"):
            score += 15
        else:
            blockers.append("Buyer company name is missing.")

        if buyer.get("registration_number"):
            score += 20
            confidence += 15
        else:
            blockers.append("Buyer registration is not verified.")

        if buyer.get("contact_name") and buyer.get("contact_role"):
            score += 15
        else:
            warnings.append("Authorised decision-maker is not confirmed.")

        if buyer.get("email") or buyer.get("phone"):
            score += 10
        else:
            blockers.append("No direct buyer contact method exists.")

        verification_status = str(
            buyer.get("verification_status") or ""
        ).strip()

        if verification_status == "Verified":
            score += 20
            confidence += 25
            reasons.append("Buyer identity is verified.")
        elif verification_status == "Failed":
            blockers.append("Buyer verification failed.")
        else:
            warnings.append("Buyer identity verification is incomplete.")

        credit_status = str(
            buyer.get("credit_status") or ""
        ).strip()

        acceptable_credit_statuses = {
            "Approved",
            "Good",
            "Assessed",
        }

        rejected_credit_statuses = {
            "Rejected",
            "Bad",
        }

        if credit_status in acceptable_credit_statuses:
            score += 20
            confidence += 20
            reasons.append("Buyer credit status is acceptable.")
        elif credit_status in rejected_credit_statuses:
            blockers.append("Buyer credit assessment failed.")
        else:
            warnings.append("Buyer credit status is incomplete.")

        payment_readiness = str(
            buyer.get("payment_readiness") or ""
        ).strip()

        if payment_readiness == "Funds Cleared":
            score += 20
            confidence += 10
            reasons.append("Buyer funds are cleared.")
        elif payment_readiness in {
            "Deposit Ready",
            "Full Payment Ready",
        }:
            score += 10
            warnings.append("Buyer funds are not yet confirmed as cleared.")
        else:
            warnings.append("Buyer payment readiness is not confirmed.")

        score = max(0, min(100, score))
        confidence = max(0, min(100, confidence))

        critical_matching_blockers = {
            "Buyer company name is missing.",
            "Buyer verification failed.",
            "No direct buyer contact method exists.",
        }

        approved_for_matching = (
            score >= 65
            and confidence >= 55
            and not any(
                blocker in critical_matching_blockers
                for blocker in blockers
            )
        )

        approved_for_credit = (
            approved_for_matching
            and credit_status in acceptable_credit_statuses
            and not blockers
        )

        if (
            verification_status == "Failed"
            or credit_status in rejected_credit_statuses
        ):
            status = BuyerQualificationStatus.REJECTED
        elif (
            approved_for_credit
            and verification_status == "Verified"
        ):
            status = BuyerQualificationStatus.VERIFIED
        elif approved_for_matching:
            status = BuyerQualificationStatus.QUALIFIED
        else:
            status = BuyerQualificationStatus.NEEDS_REVIEW

        return BuyerQualificationResult(
            score=score,
            confidence_score=confidence,
            status=status,
            approved_for_matching=approved_for_matching,
            approved_for_credit=approved_for_credit,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            reasons=tuple(reasons),
        )


_engine = BuyerQualificationEngine()


def get_buyer_qualification_engine() -> BuyerQualificationEngine:
    """Return the shared buyer qualification engine instance."""

    return _engine