"""Central approval gateway for sensitive enterprise actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from services.integration.execution_context import ExecutionContext


class GatewayDecision(str, Enum):
    DENIED = "Denied"
    PENDING = "Pending"
    APPROVED = "Approved"


@dataclass(frozen=True)
class ApprovalGatewayRequest:
    action_name: str
    sensitive: bool
    requires_compliance: bool
    requires_cleared_funds: bool
    requires_contract: bool
    compliance_cleared: bool
    funds_cleared: bool
    contract_ready: bool
    human_approval: bool


@dataclass(frozen=True)
class ApprovalGatewayResult:
    decision: GatewayDecision
    allowed: bool
    blockers: tuple[str, ...]
    explanation: str
    evaluated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class ApprovalGateway:
    def evaluate(
        self,
        request: ApprovalGatewayRequest,
        context: ExecutionContext,
    ) -> ApprovalGatewayResult:
        blockers: list[str] = []

        if request.requires_compliance and not request.compliance_cleared:
            blockers.append("Compliance clearance is incomplete.")

        if request.requires_cleared_funds and not request.funds_cleared:
            blockers.append("Cleared funds are not confirmed.")

        if request.requires_contract and not request.contract_ready:
            blockers.append("Contract readiness is incomplete.")

        if request.sensitive and not request.human_approval:
            blockers.append("Authorised human approval is required.")

        if request.sensitive and not context.approved:
            blockers.append("Execution context is not approved.")

        if blockers:
            decision = GatewayDecision.DENIED
            allowed = False
        elif request.sensitive:
            decision = GatewayDecision.APPROVED
            allowed = True
        else:
            decision = GatewayDecision.APPROVED
            allowed = True

        return ApprovalGatewayResult(
            decision=decision,
            allowed=allowed,
            blockers=tuple(blockers),
            explanation=(
                f"Action '{request.action_name}' is "
                f"{'allowed' if allowed else 'not allowed'}."
            ),
        )


_gateway = ApprovalGateway()


def get_approval_gateway() -> ApprovalGateway:
    return _gateway