"""Immutable models for the enterprise decision brain."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


class EnterpriseDecisionOutcome(str, Enum):
    PROCEED = "proceed"
    HOLD = "hold"
    REJECT = "reject"
    ESCALATE = "escalate"
    MANUAL_REVIEW = "manual_review"


class EnterpriseDecisionDomain(str, Enum):
    PROCUREMENT = "procurement"
    SUPPLIER = "supplier"
    SHIPMENT = "shipment"
    INVENTORY = "inventory"
    FINANCIAL = "financial"
    RISK = "risk"
    COMPLIANCE = "compliance"
    OPPORTUNITY = "opportunity"
    KNOWLEDGE = "knowledge"


class EnterpriseDecisionSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class EnterpriseDecisionFactor:
    factor_id: str
    name: str
    domain: EnterpriseDecisionDomain
    score: float
    weight: float
    positive: bool = True
    blocking: bool = False
    explanation: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.factor_id or "").strip():
            raise ValueError("Decision factor ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("Decision factor name is required.")
        if not 0 <= self.score <= 100:
            raise ValueError("Decision factor score must be between 0 and 100.")
        if not 0 <= self.weight <= 1:
            raise ValueError("Decision factor weight must be between 0 and 1.")

        object.__setattr__(self, "factor_id", str(self.factor_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(
            self,
            "explanation",
            str(self.explanation or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    @property
    def effective_score(self) -> float:
        value = self.score if self.positive else 100.0 - self.score
        return round(value, 4)

    @property
    def weighted_score(self) -> float:
        return round(self.effective_score * self.weight, 4)

    def as_dict(self) -> dict[str, Any]:
        return {
            "factor_id": self.factor_id,
            "name": self.name,
            "domain": self.domain.value,
            "score": self.score,
            "weight": self.weight,
            "positive": self.positive,
            "blocking": self.blocking,
            "explanation": self.explanation,
            "effective_score": self.effective_score,
            "weighted_score": self.weighted_score,
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class EnterpriseDecisionRequest:
    case_id: str
    factors: tuple[EnterpriseDecisionFactor, ...]
    request_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    correlation_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise ValueError("Decision request case ID is required.")
        if not str(self.request_id or "").strip():
            raise ValueError("Decision request ID is required.")
        if not self.factors:
            raise ValueError("At least one decision factor is required.")

        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "request_id", str(self.request_id).strip())
        object.__setattr__(self, "factors", tuple(self.factors))
        object.__setattr__(
            self,
            "correlation_id",
            str(self.correlation_id or "").strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )


@dataclass(frozen=True)
class EnterpriseDecisionFinding:
    code: str
    message: str
    domain: EnterpriseDecisionDomain
    severity: EnterpriseDecisionSeverity
    blocking: bool = False
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("Decision finding code is required.")
        if not str(self.message or "").strip():
            raise ValueError("Decision finding message is required.")

        object.__setattr__(self, "code", str(self.code).strip())
        object.__setattr__(self, "message", str(self.message).strip())
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(self.metadata),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "domain": self.domain.value,
            "severity": self.severity.value,
            "blocking": self.blocking,
            "metadata": redact_mapping(self.metadata),
        }
