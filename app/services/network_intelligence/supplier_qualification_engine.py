"""Supplier Qualification Engine for GPNI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SupplierQualificationStatus(str, Enum):
    """Supported supplier qualification outcomes."""

    REJECTED = "Rejected"
    NEEDS_REVIEW = "Needs Review"
    QUALIFIED = "Qualified"
    VERIFIED = "Verified"


@dataclass(frozen=True)
class SupplierQualificationResult:
    """Immutable supplier qualification result."""

    score: int
    confidence_score: int
    status: SupplierQualificationStatus
    approved_for_matching: bool
    approved_for_quotation: bool
    approved_for_contract: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    reasons: tuple[str, ...]


class SupplierQualificationEngine:
    """Evaluate supplier identity, compliance and export readiness."""

    def qualify(
        self,
        supplier: dict[str, Any],
    ) -> SupplierQualificationResult:
        """Qualify a supplier using deterministic procurement rules."""

        score = 0
        confidence = 20

        blockers: list[str] = []
        warnings: list[str] = []
        reasons: list[str] = []

        if supplier.get("company_name"):
            score += 10
        else:
            blockers.append("Supplier company name is missing.")

        if supplier.get("registration_number"):
            score += 20
            confidence += 15
        else:
            blockers.append("Supplier registration is not verified.")

        verification_status = str(
            supplier.get("verification_status") or ""
        ).strip()

        if verification_status == "Verified":
            score += 20
            confidence += 25
            reasons.append("Supplier identity is verified.")
        elif verification_status == "Partially Verified":
            score += 10
            confidence += 10
            warnings.append("Supplier verification is incomplete.")
        elif verification_status == "Failed":
            blockers.append("Supplier verification failed.")
        else:
            warnings.append("Supplier verification status is missing.")

        if bool(supplier.get("factory_audited")):
            score += 15
            confidence += 15
            reasons.append("Factory audit is recorded.")
        else:
            warnings.append("Factory audit is not recorded.")

        if bool(supplier.get("sanctions_cleared")):
            score += 15
            confidence += 15
            reasons.append("Sanctions screening is cleared.")
        else:
            blockers.append("Sanctions screening is incomplete.")

        if supplier.get("certificates"):
            score += 10
        else:
            warnings.append("Certificates are not recorded.")

        capacity = _number(supplier.get("capacity"))

        if capacity > 0:
            score += 10
        else:
            blockers.append("Supply capacity is not confirmed.")

        export_readiness = str(
            supplier.get("export_readiness") or ""
        ).strip()

        if export_readiness == "Export Ready":
            score += 15
            reasons.append("Supplier is export-ready.")
        else:
            blockers.append("Supplier export readiness is incomplete.")

        score = max(0, min(100, score))
        confidence = max(0, min(100, confidence))

        critical_matching_blockers = {
            "Supplier verification failed.",
            "Supply capacity is not confirmed.",
            "Supplier export readiness is incomplete.",
        }

        approved_for_matching = (
            score >= 65
            and confidence >= 55
            and not any(
                blocker in critical_matching_blockers
                for blocker in blockers
            )
        )

        approved_for_quotation = (
            approved_for_matching
            and verification_status
            in {
                "Verified",
                "Partially Verified",
            }
        )

        approved_for_contract = (
            approved_for_quotation
            and verification_status == "Verified"
            and bool(supplier.get("sanctions_cleared"))
            and export_readiness == "Export Ready"
            and not blockers
        )

        if verification_status == "Failed":
            status = SupplierQualificationStatus.REJECTED
        elif approved_for_contract:
            status = SupplierQualificationStatus.VERIFIED
        elif approved_for_matching:
            status = SupplierQualificationStatus.QUALIFIED
        else:
            status = SupplierQualificationStatus.NEEDS_REVIEW

        return SupplierQualificationResult(
            score=score,
            confidence_score=confidence,
            status=status,
            approved_for_matching=approved_for_matching,
            approved_for_quotation=approved_for_quotation,
            approved_for_contract=approved_for_contract,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            reasons=tuple(reasons),
        )


def _number(value: Any) -> float:
    """Convert a value to a safe non-negative float."""

    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, number)


_engine = SupplierQualificationEngine()


def get_supplier_qualification_engine() -> SupplierQualificationEngine:
    """Return the shared supplier qualification engine."""

    return _engine