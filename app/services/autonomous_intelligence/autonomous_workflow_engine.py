"""Autonomous workflow state machine for enterprise procurement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class WorkflowStage(str, Enum):
    DISCOVERY = "Discovery"
    QUALIFICATION = "Qualification"
    RFQ = "RFQ"
    QUOTATION_COMPARISON = "Quotation Comparison"
    BUYER_APPROVAL = "Buyer Approval"
    PURCHASE_ORDER = "Purchase Order"
    SHIPMENT = "Shipment"
    CUSTOMS = "Customs"
    WAREHOUSE = "Warehouse"
    DELIVERY = "Delivery"
    PAYMENT = "Payment"
    COMPLETED = "Completed"
    BLOCKED = "Blocked"
    CANCELLED = "Cancelled"


@dataclass(frozen=True)
class WorkflowState:
    workflow_id: str
    current_stage: WorkflowStage
    approved: bool
    blockers: tuple[str, ...] = ()
    history: tuple[WorkflowStage, ...] = ()
    updated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class AutonomousWorkflowEngine:
    ALLOWED: dict[WorkflowStage, set[WorkflowStage]] = {
        WorkflowStage.DISCOVERY: {
            WorkflowStage.QUALIFICATION,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.QUALIFICATION: {
            WorkflowStage.RFQ,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.RFQ: {
            WorkflowStage.QUOTATION_COMPARISON,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.QUOTATION_COMPARISON: {
            WorkflowStage.BUYER_APPROVAL,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.BUYER_APPROVAL: {
            WorkflowStage.PURCHASE_ORDER,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.PURCHASE_ORDER: {
            WorkflowStage.SHIPMENT,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.SHIPMENT: {
            WorkflowStage.CUSTOMS,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.CUSTOMS: {
            WorkflowStage.WAREHOUSE,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.WAREHOUSE: {
            WorkflowStage.DELIVERY,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.DELIVERY: {
            WorkflowStage.PAYMENT,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.PAYMENT: {
            WorkflowStage.COMPLETED,
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.BLOCKED: {
            WorkflowStage.QUALIFICATION,
            WorkflowStage.RFQ,
            WorkflowStage.QUOTATION_COMPARISON,
            WorkflowStage.BUYER_APPROVAL,
            WorkflowStage.PURCHASE_ORDER,
            WorkflowStage.SHIPMENT,
            WorkflowStage.CUSTOMS,
            WorkflowStage.WAREHOUSE,
            WorkflowStage.DELIVERY,
            WorkflowStage.PAYMENT,
            WorkflowStage.CANCELLED,
        },
        WorkflowStage.COMPLETED: set(),
        WorkflowStage.CANCELLED: set(),
    }

    def transition(
        self,
        state: WorkflowState,
        new_stage: WorkflowStage,
        *,
        approved: bool,
        blockers: tuple[str, ...] = (),
    ) -> WorkflowState:
        if new_stage not in self.ALLOWED.get(state.current_stage, set()):
            raise ValueError(
                f"Transition from {state.current_stage.value} "
                f"to {new_stage.value} is not allowed."
            )

        if not approved:
            raise PermissionError("Explicit approval is required.")

        if blockers and new_stage not in {
            WorkflowStage.BLOCKED,
            WorkflowStage.CANCELLED,
        }:
            raise PermissionError(
                "Workflow cannot progress while blockers remain."
            )

        return WorkflowState(
            workflow_id=state.workflow_id,
            current_stage=new_stage,
            approved=approved,
            blockers=blockers,
            history=(
                *state.history,
                state.current_stage,
            ),
        )


_engine = AutonomousWorkflowEngine()


def get_autonomous_workflow_engine() -> AutonomousWorkflowEngine:
    return _engine