"""
Enterprise Workflow Manager.

Connects the Enterprise Event Bus to persisted procurement workflows.

Responsibilities:
- subscribe to business events;
- locate the related procurement workflow;
- advance, hold or block workflow stages safely;
- preserve optimistic locking;
- append immutable workflow events and audit records;
- schedule monitoring after material changes;
- prevent unsafe automatic commercial or financial execution.

The manager may update workflow state, but it never sends quotations, issues
purchase orders, commits suppliers, releases payments or instructs shipments.
Those actions remain subject to trust, risk, finance and management approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from repositories.procurement_workflow_repository import (
    ProcurementWorkflowRepository,
    WorkflowNotFoundError,
    WorkflowVersionConflictError,
)
from services.event_bus import (
    BusinessEvent,
    EnterpriseEventBus,
    EventCategory,
    EventPriority,
    get_event_bus,
    publish_event,
)


@dataclass(frozen=True)
class WorkflowTransitionRule:
    event_name: str
    target_stage: str | None
    target_status: str
    action: str
    reason: str
    blocking: bool = False
    requires_workflow_id: bool = True


TRANSITION_RULES = {
    "buyer.verified": WorkflowTransitionRule(
        event_name="buyer.verified",
        target_stage="Buyer Verified",
        target_status="Ready for Next Stage",
        action="Buyer Verified",
        reason="Buyer identity and qualification checks passed.",
    ),
    "buyer.quotation.accepted": WorkflowTransitionRule(
        event_name="buyer.quotation.accepted",
        target_stage="Buyer Confirmation",
        target_status="Ready for Next Stage",
        action="Buyer Quotation Accepted",
        reason="Buyer accepted the controlled quotation version.",
    ),
    "buyer.funds.cleared": WorkflowTransitionRule(
        event_name="buyer.funds.cleared",
        target_stage="Funds Secured",
        target_status="Ready for Next Stage",
        action="Buyer Funds Cleared",
        reason="Cleared buyer funds were confirmed.",
    ),
    "supplier.discovered": WorkflowTransitionRule(
        event_name="supplier.discovered",
        target_stage="Supplier Discovery",
        target_status="In Progress",
        action="Supplier Candidate Discovered",
        reason="A new supply candidate was identified.",
    ),
    "supplier.verified": WorkflowTransitionRule(
        event_name="supplier.verified",
        target_stage="Supplier Verification",
        target_status="Ready for Next Stage",
        action="Supplier Verified",
        reason="Supplier identity and verification controls passed.",
    ),
    "quotation.received": WorkflowTransitionRule(
        event_name="quotation.received",
        target_stage="Quotation Collection",
        target_status="Ready for Next Stage",
        action="Quotation Received",
        reason="A supplier quotation was recorded.",
    ),
    "landed_cost.calculated": WorkflowTransitionRule(
        event_name="landed_cost.calculated",
        target_stage="Commercial Evaluation",
        target_status="Ready for Next Stage",
        action="Landed Cost Calculated",
        reason="Commercial costing was completed.",
    ),
    "margin.protected": WorkflowTransitionRule(
        event_name="margin.protected",
        target_stage="Commercial Evaluation",
        target_status="Ready for Next Stage",
        action="Margin Protected",
        reason="The approved minimum commercial margin was protected.",
    ),
    "management.approved": WorkflowTransitionRule(
        event_name="management.approved",
        target_stage="Management Approval",
        target_status="Ready for Next Stage",
        action="Management Approval Recorded",
        reason="Required management approval was recorded.",
    ),
    "workflow.blocked": WorkflowTransitionRule(
        event_name="workflow.blocked",
        target_stage="Blocked",
        target_status="Blocked",
        action="Workflow Blocked",
        reason="A blocking workflow condition was reported.",
        blocking=True,
    ),
    "risk.critical": WorkflowTransitionRule(
        event_name="risk.critical",
        target_stage="Blocked",
        target_status="Blocked",
        action="Critical Risk Detected",
        reason="A critical risk requires immediate workflow hold.",
        blocking=True,
    ),
    "trust.failed": WorkflowTransitionRule(
        event_name="trust.failed",
        target_stage="Blocked",
        target_status="Blocked",
        action="Trust Validation Failed",
        reason="A mandatory trust control failed.",
        blocking=True,
    ),
    "shipment.delayed": WorkflowTransitionRule(
        event_name="shipment.delayed",
        target_stage="Shipment",
        target_status="Waiting for Information",
        action="Shipment Delay Recorded",
        reason="A shipment delay requires review and recovery planning.",
    ),
    "shipment.delivered": WorkflowTransitionRule(
        event_name="shipment.delivered",
        target_stage="Delivery",
        target_status="Ready for Next Stage",
        action="Shipment Delivered",
        reason="Delivery was recorded.",
    ),
    "payment.release.blocked": WorkflowTransitionRule(
        event_name="payment.release.blocked",
        target_stage="Blocked",
        target_status="Blocked",
        action="Payment Release Blocked",
        reason="Supplier payment release controls did not pass.",
        blocking=True,
    ),
    "payment.released": WorkflowTransitionRule(
        event_name="payment.released",
        target_stage="Supplier Payment Release",
        target_status="Ready for Next Stage",
        action="Payment Release Recorded",
        reason="An authorised payment release was recorded.",
    ),
    "deal.closed": WorkflowTransitionRule(
        event_name="deal.closed",
        target_stage="Deal Closed",
        target_status="Completed",
        action="Deal Closed",
        reason="The controlled deal lifecycle was completed.",
    ),
}


class EnterpriseWorkflowManager:
    """Event-driven manager for persisted procurement workflows."""

    def __init__(
        self,
        *,
        event_bus: EnterpriseEventBus | None = None,
        repository: ProcurementWorkflowRepository | None = None,
        monitoring_interval_minutes: int = 15,
    ) -> None:
        if monitoring_interval_minutes < 1:
            raise ValueError(
                "monitoring_interval_minutes must be at least 1."
            )

        self._event_bus = event_bus or get_event_bus()
        self._repository = repository or ProcurementWorkflowRepository()
        self._monitoring_interval_minutes = monitoring_interval_minutes
        self._subscriber_ids: list[str] = []
        self._registered = False

    def register_subscribers(self) -> list[str]:
        """Register all workflow event handlers once."""

        if self._registered:
            return list(self._subscriber_ids)

        for event_name in TRANSITION_RULES:
            registration = self._event_bus.subscribe(
                event_name,
                self._handle_transition_event,
                subscriber_id=f"workflow-manager:{event_name}",
                priority=20,
            )
            self._subscriber_ids.append(
                registration.subscriber_id
            )

        opportunity_registration = self._event_bus.subscribe(
            "opportunity.detected",
            self._handle_opportunity_detected,
            subscriber_id="workflow-manager:opportunity.detected",
            priority=30,
        )
        self._subscriber_ids.append(
            opportunity_registration.subscriber_id
        )

        monitoring_registration = self._event_bus.subscribe(
            "monitoring.workflow.refresh.requested",
            self._handle_monitoring_refresh,
            subscriber_id=(
                "workflow-manager:"
                "monitoring.workflow.refresh.requested"
            ),
            priority=10,
        )
        self._subscriber_ids.append(
            monitoring_registration.subscriber_id
        )

        wildcard_registration = self._event_bus.subscribe(
            "security.workflow.freeze",
            self._handle_security_freeze,
            subscriber_id="workflow-manager:security.workflow.freeze",
            priority=1,
        )
        self._subscriber_ids.append(
            wildcard_registration.subscriber_id
        )

        self._registered = True
        return list(self._subscriber_ids)

    def unregister_subscribers(self) -> None:
        """Remove manager registrations from the event bus."""

        for subscriber_id in self._subscriber_ids:
            self._event_bus.unsubscribe(subscriber_id)

        self._subscriber_ids.clear()
        self._registered = False

    def _handle_transition_event(
        self,
        event: BusinessEvent,
    ) -> dict[str, Any]:
        rule = TRANSITION_RULES[event.event_name]
        workflow_id = self._workflow_id(event)

        if not workflow_id:
            if rule.requires_workflow_id:
                raise ValueError(
                    f"Event '{event.event_name}' requires workflow_id."
                )
            return {
                "processed": False,
                "reason": "No workflow ID supplied.",
            }

        record = self._repository.get_workflow(
            workflow_id,
            include_archived=False,
        )
        version = int(record["version"])

        reason = str(
            event.payload.get("reason")
            or event.payload.get("message")
            or rule.reason
        )

        if rule.blocking:
            new_version = self._repository.block_workflow(
                workflow_id,
                reason=reason,
                actor=event.source,
                expected_version=version,
            )
        else:
            new_version = self._repository.advance_stage(
                workflow_id,
                new_stage=(
                    rule.target_stage
                    or record["current_stage"]
                ),
                new_status=rule.target_status,
                actor=event.source,
                reason=reason,
                expected_version=version,
            )

        self._repository.add_event(
            workflow_id,
            event_id=event.event_id,
            stage=(
                rule.target_stage
                or record["current_stage"]
            ),
            event_type=rule.action,
            message=reason,
            actor=event.source,
            metadata={
                "business_event_name": event.event_name,
                "correlation_id": event.correlation_id,
                "causation_id": event.causation_id,
                "payload": event.payload,
            },
            created_at=event.occurred_at,
        )

        self._schedule_monitoring(
            workflow_id,
            actor=event.source,
        )

        self._publish_workflow_state_changed(
            workflow_id=workflow_id,
            event=event,
            new_version=new_version,
            stage=(
                rule.target_stage
                or record["current_stage"]
            ),
            status=rule.target_status,
        )

        return {
            "processed": True,
            "workflow_id": workflow_id,
            "new_version": new_version,
            "stage": (
                rule.target_stage
                or record["current_stage"]
            ),
            "status": rule.target_status,
        }

    def _handle_opportunity_detected(
        self,
        event: BusinessEvent,
    ) -> dict[str, Any]:
        workflow_id = self._workflow_id(event)

        if workflow_id:
            record = self._repository.get_workflow(workflow_id)
            self._repository.append_audit_log(
                workflow_id,
                action="Opportunity Linked",
                actor=event.source,
                reason=(
                    event.payload.get("reason")
                    or "Opportunity event linked to workflow."
                ),
                changes={
                    "opportunity_id": event.payload.get(
                        "opportunity_id"
                    ),
                    "opportunity_score": event.payload.get(
                        "opportunity_score"
                    ),
                },
            )
            self._schedule_monitoring(
                workflow_id,
                actor=event.source,
            )

            return {
                "processed": True,
                "workflow_id": workflow_id,
                "version": record["version"],
                "action": "Opportunity linked.",
            }

        publish_event(
            "executive.alert.generated",
            category=EventCategory.EXECUTIVE,
            source="EnterpriseWorkflowManager",
            payload={
                "title": "Unlinked opportunity detected",
                "description": (
                    event.payload.get("title")
                    or "A new trade opportunity requires review."
                ),
                "opportunity_id": event.payload.get(
                    "opportunity_id"
                ),
                "opportunity_score": event.payload.get(
                    "opportunity_score"
                ),
            },
            priority=EventPriority.HIGH,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            idempotency_key=(
                f"executive-alert:{event.event_id}"
            ),
            actor="EnterpriseWorkflowManager",
        )

        return {
            "processed": True,
            "workflow_id": None,
            "action": "Executive alert generated.",
        }

    def _handle_monitoring_refresh(
        self,
        event: BusinessEvent,
    ) -> dict[str, Any]:
        workflow_id = self._workflow_id(event)

        if not workflow_id:
            raise ValueError(
                "Monitoring refresh event requires workflow_id."
            )

        record = self._repository.get_workflow(workflow_id)

        self._repository.update_monitoring_state(
            workflow_id,
            enabled=True,
            next_monitor_at=self._next_monitor_at(),
            last_monitored_at=datetime.now().isoformat(
                timespec="seconds"
            ),
            actor=event.source,
        )

        self._repository.append_audit_log(
            workflow_id,
            action="Monitoring Refresh Requested",
            actor=event.source,
            reason=(
                event.payload.get("reason")
                or "Workflow monitoring refresh requested."
            ),
            changes={
                "event_id": event.event_id,
                "previous_status": record["status"],
            },
        )

        return {
            "processed": True,
            "workflow_id": workflow_id,
            "monitoring_scheduled": True,
        }

    def _handle_security_freeze(
        self,
        event: BusinessEvent,
    ) -> dict[str, Any]:
        workflow_id = self._workflow_id(event)

        if not workflow_id:
            raise ValueError(
                "Security freeze event requires workflow_id."
            )

        record = self._repository.get_workflow(workflow_id)

        reason = str(
            event.payload.get("reason")
            or "Security control requested workflow freeze."
        )

        new_version = self._repository.block_workflow(
            workflow_id,
            reason=reason,
            actor=event.source,
            expected_version=int(record["version"]),
        )

        self._repository.update_monitoring_state(
            workflow_id,
            enabled=True,
            next_monitor_at=self._next_monitor_at(
                minutes=1
            ),
            actor=event.source,
        )

        publish_event(
            "executive.alert.generated",
            category=EventCategory.EXECUTIVE,
            source="EnterpriseWorkflowManager",
            payload={
                "severity": "Critical",
                "title": "Workflow security freeze",
                "workflow_id": workflow_id,
                "reason": reason,
            },
            priority=EventPriority.CRITICAL,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            workflow_id=workflow_id,
            idempotency_key=(
                f"security-freeze-alert:{event.event_id}"
            ),
            actor="EnterpriseWorkflowManager",
        )

        return {
            "processed": True,
            "workflow_id": workflow_id,
            "new_version": new_version,
            "status": "Blocked",
        }

    def process_due_monitoring(
        self,
        *,
        limit: int = 100,
        actor: str = "Workflow Monitoring Scheduler",
    ) -> list[dict[str, Any]]:
        """
        Publish refresh requests for workflows due for monitoring.

        This method is intended to be called by a future scheduler.
        """

        due = self._repository.list_due_for_monitoring(
            limit=limit,
        )
        results = []

        for record in due:
            workflow_id = record["workflow_id"]

            dispatch = publish_event(
                "monitoring.workflow.refresh.requested",
                category=EventCategory.MONITORING,
                source=actor,
                payload={
                    "reason": (
                        "Scheduled workflow monitoring cycle."
                    ),
                    "workflow_version": record["version"],
                    "current_stage": record["current_stage"],
                    "status": record["status"],
                },
                priority=(
                    EventPriority.HIGH
                    if record["status"] == "Blocked"
                    else EventPriority.NORMAL
                ),
                workflow_id=workflow_id,
                idempotency_key=(
                    f"workflow-monitor:"
                    f"{workflow_id}:"
                    f"{record['version']}:"
                    f"{datetime.now().strftime('%Y%m%d%H%M')}"
                ),
                actor=actor,
            )

            results.append(
                {
                    "workflow_id": workflow_id,
                    "event_id": dispatch.event_id,
                    "status": dispatch.status.value,
                }
            )

        return results

    def rebuild_workflow_timeline(
        self,
        workflow_id: str,
    ) -> list[dict[str, Any]]:
        """Return merged workflow events and audit history."""

        events = self._repository.list_events(workflow_id)
        audit = self._repository.list_audit_history(workflow_id)

        timeline = []

        for item in events:
            timeline.append(
                {
                    "type": "Event",
                    "created_at": item["created_at"],
                    "title": item["event_type"],
                    "stage": item["stage"],
                    "actor": item["actor"],
                    "description": item["message"],
                    "details": item.get("metadata", {}),
                }
            )

        for item in audit:
            timeline.append(
                {
                    "type": "Audit",
                    "created_at": item["created_at"],
                    "title": item["action"],
                    "stage": (
                        item.get("new_stage")
                        or item.get("old_stage")
                    ),
                    "actor": item["actor"],
                    "description": item.get("reason") or "",
                    "details": item.get("changes", {}),
                }
            )

        timeline.sort(
            key=lambda item: (
                item["created_at"],
                item["type"],
            )
        )

        return timeline

    def _schedule_monitoring(
        self,
        workflow_id: str,
        *,
        actor: str,
    ) -> None:
        self._repository.update_monitoring_state(
            workflow_id,
            enabled=True,
            next_monitor_at=self._next_monitor_at(),
            actor=actor,
        )

    def _publish_workflow_state_changed(
        self,
        *,
        workflow_id: str,
        event: BusinessEvent,
        new_version: int,
        stage: str,
        status: str,
    ) -> None:
        publish_event(
            "workflow.state.changed",
            category=EventCategory.WORKFLOW,
            source="EnterpriseWorkflowManager",
            payload={
                "workflow_id": workflow_id,
                "version": new_version,
                "stage": stage,
                "status": status,
                "trigger_event": event.event_name,
            },
            priority=(
                EventPriority.CRITICAL
                if status == "Blocked"
                else EventPriority.NORMAL
            ),
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            workflow_id=workflow_id,
            idempotency_key=(
                f"workflow-state:"
                f"{workflow_id}:"
                f"{new_version}"
            ),
            actor="EnterpriseWorkflowManager",
        )

    def _next_monitor_at(
        self,
        *,
        minutes: int | None = None,
    ) -> str:
        interval = (
            minutes
            if minutes is not None
            else self._monitoring_interval_minutes
        )

        return (
            datetime.now()
            + timedelta(minutes=interval)
        ).isoformat(timespec="seconds")

    @staticmethod
    def _workflow_id(
        event: BusinessEvent,
    ) -> str | None:
        value = (
            event.workflow_id
            or event.payload.get("workflow_id")
        )

        if value in (None, ""):
            return None

        return str(value)

    @staticmethod
    def create_event_id() -> str:
        return f"WFE-{uuid4().hex[:14].upper()}"


_workflow_manager = EnterpriseWorkflowManager()


def get_workflow_manager() -> EnterpriseWorkflowManager:
    """Return the workflow manager singleton."""

    return _workflow_manager


def register_workflow_subscribers() -> list[str]:
    """Register workflow manager event subscriptions."""

    return _workflow_manager.register_subscribers()


def process_due_workflow_monitoring(
    *,
    limit: int = 100,
    actor: str = "Workflow Monitoring Scheduler",
) -> list[dict[str, Any]]:
    """Process workflows due for monitoring."""

    return _workflow_manager.process_due_monitoring(
        limit=limit,
        actor=actor,
    )


def rebuild_workflow_timeline(
    workflow_id: str,
) -> list[dict[str, Any]]:
    """Return the complete workflow timeline."""

    return _workflow_manager.rebuild_workflow_timeline(
        workflow_id
    )