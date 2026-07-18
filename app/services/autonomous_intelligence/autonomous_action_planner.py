"""Autonomous Action Planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable


class ActionPlanStatus(str, Enum):
    DRAFT = "Draft"
    READY_FOR_REVIEW = "Ready for Review"
    BLOCKED = "Blocked"
    APPROVED = "Approved"
    COMPLETED = "Completed"


@dataclass(frozen=True)
class PlannedAction:
    action_id: str
    sequence: int
    title: str
    description: str
    owner_role: str
    requires_approval: bool
    required_evidence: tuple[str, ...]
    dependencies: tuple[str, ...]
    prohibited_until_approved: bool = True


@dataclass(frozen=True)
class ActionPlan:
    plan_id: str
    case_id: str
    status: ActionPlanStatus
    actions: tuple[PlannedAction, ...]
    blockers: tuple[str, ...]
    explanation: str
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class AutonomousActionPlanner:
    """Create controlled, dependency-aware procurement plans."""

    def create_plan(
        self,
        *,
        plan_id: str,
        case_id: str,
        buyer_verified: bool,
        supplier_verified: bool,
        match_eligible: bool,
        commercial_safeguards_passed: bool,
        buyer_final_approval: bool,
        funds_cleared: bool,
        contract_ready: bool,
    ) -> ActionPlan:
        actions = (
            PlannedAction(
                action_id=f"{plan_id}-01",
                sequence=1,
                title="Verify buyer",
                description=(
                    "Confirm legal identity, authority, demand and payment readiness."
                ),
                owner_role="Customer Acquisition Manager",
                requires_approval=False,
                required_evidence=("Buyer registration", "Buyer requirement"),
                dependencies=(),
            ),
            PlannedAction(
                action_id=f"{plan_id}-02",
                sequence=2,
                title="Verify supplier",
                description=(
                    "Confirm legal identity, sanctions, capacity and export readiness."
                ),
                owner_role="Global Sourcing Specialist",
                requires_approval=False,
                required_evidence=("Supplier registration", "Capacity evidence"),
                dependencies=(f"{plan_id}-01",),
            ),
            PlannedAction(
                action_id=f"{plan_id}-03",
                sequence=3,
                title="Collect and compare quotations",
                description=(
                    "Obtain formal supplier quotations and calculate landed cost."
                ),
                owner_role="Procurement Specialist",
                requires_approval=True,
                required_evidence=("Formal quotation", "Landed cost"),
                dependencies=(f"{plan_id}-02",),
            ),
            PlannedAction(
                action_id=f"{plan_id}-04",
                sequence=4,
                title="Run safeguards",
                description=(
                    "Evaluate margin, compliance, documents, risk and trust."
                ),
                owner_role="Commercial Manager",
                requires_approval=True,
                required_evidence=("Risk assessment", "Compliance clearance"),
                dependencies=(f"{plan_id}-03",),
            ),
            PlannedAction(
                action_id=f"{plan_id}-05",
                sequence=5,
                title="Obtain buyer final approval",
                description=(
                    "Present the final quotation and receive explicit confirmation."
                ),
                owner_role="Account Manager",
                requires_approval=True,
                required_evidence=("Buyer approval",),
                dependencies=(f"{plan_id}-04",),
            ),
            PlannedAction(
                action_id=f"{plan_id}-06",
                sequence=6,
                title="Confirm cleared funds",
                description=(
                    "Verify bank clearance before any supplier commitment."
                ),
                owner_role="Finance Approver",
                requires_approval=True,
                required_evidence=("Bank clearance",),
                dependencies=(f"{plan_id}-05",),
            ),
            PlannedAction(
                action_id=f"{plan_id}-07",
                sequence=7,
                title="Activate contract and execution",
                description=(
                    "Activate only after signatures, safeguards and funds are confirmed."
                ),
                owner_role="Managing Director",
                requires_approval=True,
                required_evidence=("Signed contract", "Execution approval"),
                dependencies=(f"{plan_id}-06",),
            ),
        )

        blockers: list[str] = []

        if not buyer_verified:
            blockers.append("Buyer verification is incomplete.")
        if not supplier_verified:
            blockers.append("Supplier verification is incomplete.")
        if not match_eligible:
            blockers.append("Demand-supply match is not eligible.")
        if not commercial_safeguards_passed:
            blockers.append("Commercial safeguards have not passed.")
        if not buyer_final_approval:
            blockers.append("Buyer final approval is missing.")
        if not funds_cleared:
            blockers.append("Buyer funds are not cleared.")
        if not contract_ready:
            blockers.append("Contract is not ready.")

        status = (
            ActionPlanStatus.BLOCKED
            if blockers
            else ActionPlanStatus.READY_FOR_REVIEW
        )

        return ActionPlan(
            plan_id=plan_id,
            case_id=case_id,
            status=status,
            actions=actions,
            blockers=tuple(blockers),
            explanation=(
                f"Action plan contains {len(actions)} controlled step(s). "
                f"Status: {status.value}. No binding action may execute "
                "without the required approval and evidence."
            ),
        )

    @staticmethod
    def next_available_actions(
        plan: ActionPlan,
        completed_action_ids: Iterable[str],
    ) -> list[PlannedAction]:
        completed = set(completed_action_ids)

        return [
            action
            for action in plan.actions
            if action.action_id not in completed
            and all(
                dependency in completed
                for dependency in action.dependencies
            )
        ]


_engine = AutonomousActionPlanner()


def get_autonomous_action_planner() -> AutonomousActionPlanner:
    return _engine