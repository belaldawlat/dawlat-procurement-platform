"""Enterprise integration service for GPNI."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from services.network_intelligence.gpni_audit_service import (
    GPNIAuditEntry,
    get_gpni_audit_service,
)
from services.network_intelligence.gpni_workflow_service import (
    GPNIWorkflowStage,
    WorkflowTransition,
    get_gpni_workflow_service,
)
from services.network_intelligence.procurement_network_engine import (
    NetworkDecision,
    ProcurementNetworkAssessment,
    ProcurementNetworkCase,
    get_procurement_network_engine,
)

@dataclass(frozen=True)
class GPNIIntegrationResult:
    assessment: ProcurementNetworkAssessment
    workflow_transition: WorkflowTransition | None
    audit_entry: GPNIAuditEntry
    actions_executed: tuple[str, ...]
    actions_blocked: tuple[str, ...]
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

class GPNIIntegrationService:
    def __init__(self) -> None:
        self._network_engine = get_procurement_network_engine()
        self._workflow = get_gpni_workflow_service()
        self._audit = get_gpni_audit_service()

    def evaluate_case(
        self,
        case: ProcurementNetworkCase,
        *,
        actor: str,
        apply_transition: bool = False,
    ) -> GPNIIntegrationResult:
        self._workflow.create_case(
            case.case_id,
            assigned_owner=actor,
            metadata=case.metadata,
        )
        assessment = self._network_engine.assess(case)
        actions_executed: list[str] = []
        actions_blocked: list[str] = []
        transition: WorkflowTransition | None = None
        target_stage = self._target_stage(assessment)

        if apply_transition and target_stage is not None:
            current = self._workflow.get_case(case.case_id)
            if current is not None:
                current_stage = GPNIWorkflowStage(current["current_stage"])
                if current_stage != target_stage:
                    try:
                        transition = self._workflow.transition(
                            case_id=case.case_id,
                            new_stage=target_stage,
                            actor=actor,
                            reason=assessment.explanation,
                            approved=True,
                            metadata={
                                "overall_score": assessment.overall_score,
                                "decision": assessment.decision.value,
                            },
                        )
                        actions_executed.append(
                            f"Workflow moved to {target_stage.value}."
                        )
                    except (ValueError, PermissionError) as error:
                        actions_blocked.append(str(error))

        if assessment.execution_allowed:
            actions_executed.append(
                "Case is eligible for authorised execution."
            )
        else:
            actions_blocked.append(
                "Binding execution remains blocked."
            )

        audit_entry = self._audit.record(
            case_id=case.case_id,
            event_name="GPNI Case Evaluated",
            actor=actor,
            stage=assessment.stage.value,
            decision=assessment.decision.value,
            details={
                "overall_score": assessment.overall_score,
                "execution_allowed": assessment.execution_allowed,
                "blockers": list(assessment.blockers),
                "warnings": list(assessment.warnings),
                "required_actions": list(assessment.required_actions),
                "actions_executed": actions_executed,
                "actions_blocked": actions_blocked,
            },
        )

        return GPNIIntegrationResult(
            assessment=assessment,
            workflow_transition=transition,
            audit_entry=audit_entry,
            actions_executed=tuple(actions_executed),
            actions_blocked=tuple(actions_blocked),
        )

    @staticmethod
    def _target_stage(
        assessment: ProcurementNetworkAssessment,
    ) -> GPNIWorkflowStage | None:
        if assessment.decision == NetworkDecision.BLOCK:
            return GPNIWorkflowStage.BLOCKED
        mapping = {
            "Buyer Qualification": GPNIWorkflowStage.BUYER_QUALIFICATION,
            "Supplier Qualification": GPNIWorkflowStage.SUPPLIER_QUALIFICATION,
            "Demand-Supply Matching": GPNIWorkflowStage.MATCHING,
            "Commercial Review": GPNIWorkflowStage.COMMERCIAL_REVIEW,
            "Payment Protection": GPNIWorkflowStage.FUNDS_CLEARANCE,
            "Contract Readiness": GPNIWorkflowStage.CONTRACT_READINESS,
            "Execution Ready": GPNIWorkflowStage.EXECUTION_READY,
        }
        return mapping.get(assessment.stage.value)

_service = GPNIIntegrationService()

def get_gpni_integration_service() -> GPNIIntegrationService:
    return _service