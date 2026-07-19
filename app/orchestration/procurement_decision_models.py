"""Immutable models for enterprise procurement decisions."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping


class ProcurementDecision(str, Enum):
    """Final decision outcomes produced by the decision engine."""

    PROCEED = "proceed"
    HOLD = "hold"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"


class DecisionSeverity(str, Enum):
    """Severity assigned to decision findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionCategory(str, Enum):
    """Categories evaluated by procurement decision rules."""

    BUYER = "buyer"
    DEMAND = "demand"
    SUPPLIER = "supplier"
    QUOTATION = "quotation"
    COMPLIANCE = "compliance"
    FINANCIAL = "financial"
    APPROVAL = "approval"
    PAYMENT = "payment"
    SHIPMENT = "shipment"
    DATA_QUALITY = "data_quality"
    RISK = "risk"


@dataclass(frozen=True)
class DecisionFinding:
    """One deterministic decision finding."""

    code: str
    message: str
    category: DecisionCategory
    severity: DecisionSeverity
    blocking: bool = False
    recommendation: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalise finding data."""

        code = str(self.code or "").strip()
        message = str(self.message or "").strip()

        if not code:
            raise ValueError("Decision finding code is required.")

        if not message:
            raise ValueError("Decision finding message is required.")

        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(
            self,
            "recommendation",
            str(self.recommendation or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable representation."""

        return {
            "code": self.code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "blocking": self.blocking,
            "recommendation": self.recommendation,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class ProcurementDecisionContext:
    """Inputs used to evaluate a procurement case."""

    approval_satisfied: bool = False
    buyer_payment_cleared: bool = False
    shipment_ready: bool = False
    supplier_qualified: bool = True
    documents_complete: bool = True
    landed_cost_budget_ratio: float | None = None
    supplier_risk_score: float = 0.0
    external_risk_score: float = 0.0
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate risk and cost metrics."""

        for name, value in {
            "supplier_risk_score": self.supplier_risk_score,
            "external_risk_score": self.external_risk_score,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(
                    f"{name} must be between 0 and 100."
                )

        if (
            self.landed_cost_budget_ratio is not None
            and self.landed_cost_budget_ratio < 0
        ):
            raise ValueError(
                "Landed-cost budget ratio cannot be negative."
            )

        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )