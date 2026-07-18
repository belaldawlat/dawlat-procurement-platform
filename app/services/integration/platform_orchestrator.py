"""Top-level enterprise platform orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.integration.approval_gateway import (
    ApprovalGatewayRequest,
    ApprovalGatewayResult,
    get_approval_gateway,
)
from services.integration.audit_pipeline import get_audit_pipeline
from services.integration.event_dispatcher import (
    PlatformEvent,
    get_event_dispatcher,
)
from services.integration.execution_context import ExecutionContext
from services.integration.workflow_router import get_workflow_router


@dataclass(frozen=True)
class OrchestrationRequest:
    action_name: str
    payload: dict[str, Any]
    approval_request: ApprovalGatewayRequest


@dataclass(frozen=True)
class OrchestrationResult:
    action_name: str
    approval: ApprovalGatewayResult
    routed: bool
    result: Any
    emitted_event_id: str | None
    explanation: str
    completed_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class PlatformOrchestrator:
    def __init__(self) -> None:
        self._approval = get_approval_gateway()
        self._router = get_workflow_router()
        self._dispatcher = get_event_dispatcher()
        self._audit = get_audit_pipeline()

    def execute(
        self,
        request: OrchestrationRequest,
        context: ExecutionContext,
    ) -> OrchestrationResult:
        approval = self._approval.evaluate(
            request.approval_request,
            context,
        )

        if not approval.allowed:
            self._audit.record(
                action_name=request.action_name,
                result="Blocked",
                context=context,
                details={
                    "blockers": list(approval.blockers),
                },
            )

            return OrchestrationResult(
                action_name=request.action_name,
                approval=approval,
                routed=False,
                result=None,
                emitted_event_id=None,
                explanation=(
                    "Action was blocked by the approval gateway."
                ),
            )

        routed_result = self._router.route(
            request.action_name,
            context,
            request.payload,
        )

        event = PlatformEvent.create(
            event_name=f"{request.action_name}.completed",
            payload={
                "action_name": request.action_name,
                "result": routed_result,
                "case_id": context.case_id,
                "workflow_id": context.workflow_id,
            },
            correlation_id=context.correlation_id,
        )

        self._dispatcher.dispatch(event)

        self._audit.record(
            action_name=request.action_name,
            result="Completed",
            context=context,
            details={
                "event_id": event.event_id,
            },
        )

        return OrchestrationResult(
            action_name=request.action_name,
            approval=approval,
            routed=True,
            result=routed_result,
            emitted_event_id=event.event_id,
            explanation=(
                "Action passed approval, workflow routing, "
                "event dispatch, and audit recording."
            ),
        )


_orchestrator = PlatformOrchestrator()


def get_platform_orchestrator() -> PlatformOrchestrator:
    return _orchestrator