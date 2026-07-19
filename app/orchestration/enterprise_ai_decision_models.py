"""Immutable models for the enterprise AI decision network."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class AIDecisionOutcome(str, Enum):
    PROCEED = "proceed"
    HOLD = "hold"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"


class AIDecisionSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AIDecisionDomain(str, Enum):
    PROCUREMENT = "procurement"
    SUPPLIER = "supplier"
    QUOTATION = "quotation"
    SHIPMENT = "shipment"
    INVENTORY = "inventory"
    FINANCIAL = "financial"
    RISK = "risk"
    COMPLIANCE = "compliance"
    OPPORTUNITY = "opportunity"


@dataclass(frozen=True)
class AIDecisionSignal:
    signal_id: str
    domain: AIDecisionDomain
    name: str
    value: float
    weight: float
    positive: bool = True
    explanation: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.signal_id or "").strip():
            raise ValueError("AI decision signal ID is required.")
        if not str(self.name or "").strip():
            raise ValueError("AI decision signal name is required.")
        if not 0 <= self.value <= 100:
            raise ValueError("AI decision signal value must be between 0 and 100.")
        if not 0 <= self.weight <= 1:
            raise ValueError("AI decision signal weight must be between 0 and 1.")

        object.__setattr__(self, "signal_id", str(self.signal_id).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "explanation", str(self.explanation or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def adjusted_score(self) -> float:
        base = self.value if self.positive else 100.0 - self.value
        return round(base * self.weight, 4)

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "domain": self.domain.value,
            "name": self.name,
            "value": self.value,
            "weight": self.weight,
            "positive": self.positive,
            "explanation": self.explanation,
            "adjusted_score": self.adjusted_score(),
            "metadata": redact_mapping(self.metadata),
        }


@dataclass(frozen=True)
class AIDecisionRequest:
    case_id: str
    signals: tuple[AIDecisionSignal, ...]
    request_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    requested_at: str = dataclass_field(default_factory=utc_timestamp)
    correlation_id: str = ""
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise ValueError("AI decision case ID is required.")
        if not str(self.request_id or "").strip():
            raise ValueError("AI decision request ID is required.")
        if not self.signals:
            raise ValueError("At least one AI decision signal is required.")

        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "request_id", str(self.request_id).strip())
        object.__setattr__(self, "signals", tuple(self.signals))
        object.__setattr__(self, "correlation_id", str(self.correlation_id or "").strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))


@dataclass(frozen=True)
class AIDecisionExplanation:
    code: str
    message: str
    severity: AIDecisionSeverity
    domain: AIDecisionDomain
    blocking: bool = False
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("AI decision explanation code is required.")
        if not str(self.message or "").strip():
            raise ValueError("AI decision explanation message is required.")

        object.__setattr__(self, "code", str(self.code).strip())
        object.__setattr__(self, "message", str(self.message).strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "domain": self.domain.value,
            "blocking": self.blocking,
            "metadata": redact_mapping(self.metadata),
        }