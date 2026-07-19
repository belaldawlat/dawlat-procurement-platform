"""Immutable models for the enterprise procurement orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from app.observability.redaction import redact_mapping
from app.orchestration.autonomous_procurement_result import (
    AutonomousProcurementResult,
)
from app.orchestration.procurement_decision_result import (
    ProcurementDecisionResult,
)
from app.orchestration.procurement_intelligence_result import (
    ProcurementIntelligenceResult,
)


class EnterpriseStage(str, Enum):
    """Enterprise orchestration stages."""

    RECEIVED = "received"
    VALIDATED = "validated"
    DECIDED = "decided"
    INTELLIGENCE_GENERATED = "intelligence_generated"
    AUTONOMOUS_PLAN_CREATED = "autonomous_plan_created"
    APPROVAL_REQUIRED = "approval_required"
    READY_FOR_EXECUTION = "ready_for_execution"
    EXECUTION_BLOCKED = "execution_blocked"
    COMPENSATION_REQUIRED = "compensation_required"
    COMPLETED = "completed"
    FAILED = "failed"


class EnterpriseCommand(str, Enum):
    """Commands emitted by the enterprise orchestrator."""

    PROCEED = "proceed"
    HOLD = "hold"
    REJECT = "reject"
    REQUEST_APPROVAL = "request_approval"
    EXECUTE = "execute"
    START_COMPENSATION = "start_compensation"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True)
class EnterpriseOrchestrationContext:
    """External controls supplied to the enterprise orchestrator."""

    actor_id: str = ""
    correlation_id: str = ""
    approval_satisfied: bool = False
    execution_requested: bool = False
    compensation_available: bool = True
    dry_run: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "actor_id",
            str(self.actor_id or "").strip(),
        )
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
class EnterpriseOrchestrationSnapshot:
    """Cross-engine snapshot used for orchestration."""

    case_id: str
    decision_result: ProcurementDecisionResult
    intelligence_result: ProcurementIntelligenceResult
    autonomous_result: AutonomousProcurementResult
    context: EnterpriseOrchestrationContext

    def __post_init__(self) -> None:
        case_id = str(self.case_id or "").strip()

        if not case_id:
            raise ValueError("Enterprise orchestration case ID is required.")

        result_case_ids = {
            self.decision_result.case_id,
            self.intelligence_result.case_id,
            self.autonomous_result.case_id,
        }

        if result_case_ids != {case_id}:
            raise ValueError(
                "All enterprise orchestration results must belong "
                "to the same procurement case."
            )

        object.__setattr__(self, "case_id", case_id)