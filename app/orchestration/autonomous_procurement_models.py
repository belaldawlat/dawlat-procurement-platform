"""Immutable models for the autonomous procurement brain."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.procurement_decision_models import ProcurementDecision
from app.orchestration.procurement_intelligence_models import ProcurementRecommendation


class AutonomousAction(str, Enum):
    PROCEED = "proceed"
    HOLD = "hold"
    REJECT = "reject"
    REQUEST_APPROVAL = "request_approval"
    SECURE_PAYMENT = "secure_payment"
    SELECT_SUPPLIER = "select_supplier"
    NEGOTIATE = "negotiate"
    ESCALATE_RISK = "escalate_risk"
    COMPLETE_DOCUMENTS = "complete_documents"
    HANDOFF_SHIPMENT = "handoff_shipment"
    START_COMPENSATION = "start_compensation"
    MANUAL_REVIEW = "manual_review"


class AutonomyMode(str, Enum):
    ADVISORY = "advisory"
    SUPERVISED = "supervised"
    CONTROLLED_AUTOMATION = "controlled_automation"


class BrainConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True)
class AutonomousProcurementContext:
    approval_satisfied: bool = False
    payment_cleared: bool = False
    documents_complete: bool = True
    shipment_ready: bool = False
    compensation_available: bool = True
    human_override_required: bool = False
    autonomy_mode: AutonomyMode = AutonomyMode.ADVISORY
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))


@dataclass(frozen=True)
class AutonomousProcurementAction:
    action: AutonomousAction
    title: str
    rationale: str
    priority: int
    requires_human_approval: bool
    executable: bool
    source_decision: ProcurementDecision
    source_recommendation: ProcurementRecommendation | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.title or "").strip():
            raise ValueError("Autonomous action title is required.")
        if not str(self.rationale or "").strip():
            raise ValueError("Autonomous action rationale is required.")
        if not 1 <= self.priority <= 100:
            raise ValueError("Autonomous action priority must be between 1 and 100.")

        object.__setattr__(self, "title", str(self.title).strip())
        object.__setattr__(self, "rationale", str(self.rationale).strip())
        object.__setattr__(self, "metadata", redact_mapping(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "title": self.title,
            "rationale": self.rationale,
            "priority": self.priority,
            "requires_human_approval": self.requires_human_approval,
            "executable": self.executable,
            "source_decision": self.source_decision.value,
            "source_recommendation": (
                self.source_recommendation.as_dict()
                if self.source_recommendation
                else None
            ),
            "metadata": redact_mapping(self.metadata),
        }