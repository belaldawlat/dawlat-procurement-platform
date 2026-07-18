"""
Enterprise Notification Service for the Dawlat AI Procurement Platform.

Centralizes notification routing, persistence, acknowledgement, escalation,
deduplication, quiet hours, dashboard delivery, executive briefing and audit.
External channels remain provider extensions and are never used for binding
commercial or financial actions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

from database.connection import get_connection
from services.event_bus import (
    BusinessEvent,
    EnterpriseEventBus,
    EventPriority,
    get_event_bus,
)


class NotificationSeverity(str, Enum):
    INFO = "Info"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"
    EMERGENCY = "Emergency"


class NotificationStatus(str, Enum):
    CREATED = "Created"
    QUEUED = "Queued"
    DELIVERED = "Delivered"
    READ = "Read"
    ACKNOWLEDGED = "Acknowledged"
    ESCALATED = "Escalated"
    CLOSED = "Closed"
    FAILED = "Failed"


class DeliveryChannel(str, Enum):
    DASHBOARD = "Dashboard"
    EMAIL = "Email"
    SMS = "SMS"
    WHATSAPP = "WhatsApp"
    SLACK = "Slack"
    TEAMS = "Microsoft Teams"
    PUSH = "Push"
    WEBHOOK = "Webhook"
    AI_ASSISTANT = "AI Assistant"
    EXECUTIVE_BRIEF = "Executive Brief"


@dataclass(frozen=True)
class NotificationRecipient:
    recipient_type: str
    recipient_id: str
    display_name: str
    role: str
    channels: tuple[DeliveryChannel, ...] = (
        DeliveryChannel.DASHBOARD,
    )


@dataclass(frozen=True)
class NotificationMessage:
    notification_id: str
    event_id: str
    event_name: str
    title: str
    message: str
    severity: NotificationSeverity
    category: str
    recipients: tuple[NotificationRecipient, ...]
    workflow_id: str | None = None
    source_record_id: str | None = None
    correlation_id: str | None = None
    acknowledgement_required: bool = False
    escalation_minutes: int | None = None
    deduplication_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


@dataclass(frozen=True)
class DeliveryResult:
    notification_id: str
    recipient_id: str
    channel: DeliveryChannel
    success: bool
    status: NotificationStatus
    delivered_at: str | None = None
    error_message: str | None = None
    provider_reference: str | None = None


@dataclass(frozen=True)
class NotificationRoute:
    event_name: str
    roles: tuple[str, ...]
    channels: tuple[DeliveryChannel, ...]
    severity: NotificationSeverity
    acknowledgement_required: bool = False
    escalation_minutes: int | None = None


DeliveryProvider = Callable[
    [NotificationMessage, NotificationRecipient, DeliveryChannel],
    DeliveryResult,
]


ROUTES: dict[str, NotificationRoute] = {
    "risk.critical": NotificationRoute(
        "risk.critical",
        ("Managing Director", "Risk Manager", "Compliance Manager"),
        (DeliveryChannel.DASHBOARD, DeliveryChannel.EXECUTIVE_BRIEF),
        NotificationSeverity.CRITICAL,
        True,
        15,
    ),
    "trust.failed": NotificationRoute(
        "trust.failed",
        ("Managing Director", "Commercial Manager", "Compliance Manager"),
        (DeliveryChannel.DASHBOARD, DeliveryChannel.EXECUTIVE_BRIEF),
        NotificationSeverity.CRITICAL,
        True,
        15,
    ),
    "workflow.blocked": NotificationRoute(
        "workflow.blocked",
        ("Managing Director", "Operations Manager"),
        (DeliveryChannel.DASHBOARD, DeliveryChannel.EXECUTIVE_BRIEF),
        NotificationSeverity.CRITICAL,
        True,
        30,
    ),
    "shipment.delayed": NotificationRoute(
        "shipment.delayed",
        ("Logistics Coordinator", "Operations Manager", "Managing Director"),
        (DeliveryChannel.DASHBOARD, DeliveryChannel.EXECUTIVE_BRIEF),
        NotificationSeverity.CRITICAL,
        True,
        30,
    ),
    "quotation.expiring": NotificationRoute(
        "quotation.expiring",
        ("Procurement Specialist", "Commercial Manager"),
        (DeliveryChannel.DASHBOARD,),
        NotificationSeverity.HIGH,
    ),
    "quotation.expired": NotificationRoute(
        "quotation.expired",
        ("Procurement Specialist", "Commercial Manager"),
        (DeliveryChannel.DASHBOARD, DeliveryChannel.EXECUTIVE_BRIEF),
        NotificationSeverity.CRITICAL,
        True,
        60,
    ),
    "supplier.verification.required": NotificationRoute(
        "supplier.verification.required",
        ("Global Sourcing Specialist", "Compliance Manager"),
        (DeliveryChannel.DASHBOARD,),
        NotificationSeverity.HIGH,
    ),
    "buyer.credit.review.required": NotificationRoute(
        "buyer.credit.review.required",
        ("Finance Approver", "Customer Acquisition Manager"),
        (DeliveryChannel.DASHBOARD,),
        NotificationSeverity.HIGH,
    ),
    "inventory.reorder.required": NotificationRoute(
        "inventory.reorder.required",
        ("Inventory Manager", "Procurement Specialist"),
        (DeliveryChannel.DASHBOARD,),
        NotificationSeverity.HIGH,
    ),
    "certificate.expiring": NotificationRoute(
        "certificate.expiring",
        ("Compliance Manager", "Global Sourcing Specialist"),
        (DeliveryChannel.DASHBOARD,),
        NotificationSeverity.HIGH,
    ),
    "certificate.expired": NotificationRoute(
        "certificate.expired",
        ("Compliance Manager", "Managing Director"),
        (DeliveryChannel.DASHBOARD, DeliveryChannel.EXECUTIVE_BRIEF),
        NotificationSeverity.CRITICAL,
        True,
        30,
    ),
    "opportunity.detected": NotificationRoute(
        "opportunity.detected",
        ("Managing Director", "Executive Advisor", "Sales Manager"),
        (DeliveryChannel.DASHBOARD, DeliveryChannel.EXECUTIVE_BRIEF),
        NotificationSeverity.HIGH,
    ),
    "executive.alert.generated": NotificationRoute(
        "executive.alert.generated",
        ("Managing Director",),
        (DeliveryChannel.DASHBOARD, DeliveryChannel.EXECUTIVE_BRIEF),
        NotificationSeverity.CRITICAL,
        True,
        30,
    ),
    "security.workflow.freeze": NotificationRoute(
        "security.workflow.freeze",
        ("Managing Director", "Security Administrator", "Finance Approver"),
        (DeliveryChannel.DASHBOARD, DeliveryChannel.EXECUTIVE_BRIEF),
        NotificationSeverity.EMERGENCY,
        True,
        5,
    ),
}


def create_notification_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id TEXT NOT NULL UNIQUE,
                event_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                workflow_id TEXT,
                source_record_id TEXT,
                correlation_id TEXT,
                acknowledgement_required INTEGER NOT NULL DEFAULT 0,
                escalation_minutes INTEGER,
                deduplication_key TEXT,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                acknowledged_at TEXT,
                acknowledged_by TEXT,
                closed_at TEXT,
                closed_by TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id TEXT NOT NULL,
                recipient_type TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                channels_json TEXT NOT NULL,
                read_at TEXT,
                acknowledged_at TEXT,
                UNIQUE(notification_id, recipient_id),
                FOREIGN KEY (notification_id)
                    REFERENCES notifications(notification_id)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                success INTEGER NOT NULL,
                status TEXT NOT NULL,
                delivered_at TEXT,
                error_message TEXT,
                provider_reference TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (notification_id)
                    REFERENCES notifications(notification_id)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (notification_id)
                    REFERENCES notifications(notification_id)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_notifications_status
            ON notifications(status, severity, created_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_notifications_workflow
            ON notifications(workflow_id, created_at DESC)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedupe
            ON notifications(deduplication_key)
            WHERE deduplication_key IS NOT NULL
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_notification_recipient
            ON notification_recipients(recipient_id, read_at)
            """
        )
        connection.commit()


class EnterpriseNotificationService:
    def __init__(
        self,
        *,
        event_bus: EnterpriseEventBus | None = None,
        quiet_hours_start: time = time(23, 0),
        quiet_hours_end: time = time(6, 0),
    ) -> None:
        create_notification_tables()
        self._event_bus = event_bus or get_event_bus()
        self._quiet_hours_start = quiet_hours_start
        self._quiet_hours_end = quiet_hours_end
        self._providers: dict[DeliveryChannel, DeliveryProvider] = {
            DeliveryChannel.DASHBOARD: self._dashboard_provider,
            DeliveryChannel.EXECUTIVE_BRIEF: self._dashboard_provider,
            DeliveryChannel.AI_ASSISTANT: self._dashboard_provider,
        }
        self._subscriber_ids: list[str] = []
        self._registered = False

    def register_subscribers(self) -> list[str]:
        if self._registered:
            return list(self._subscriber_ids)

        for event_name in ROUTES:
            registration = self._event_bus.subscribe(
                event_name,
                self._handle_event,
                subscriber_id=f"notification-service:{event_name}",
                priority=50,
            )
            self._subscriber_ids.append(registration.subscriber_id)

        direct = self._event_bus.subscribe(
            "notification.requested",
            self._handle_direct_request,
            subscriber_id="notification-service:notification.requested",
            priority=10,
        )
        self._subscriber_ids.append(direct.subscriber_id)
        self._registered = True
        return list(self._subscriber_ids)

    def register_provider(
        self,
        channel: DeliveryChannel,
        provider: DeliveryProvider,
    ) -> None:
        self._providers[channel] = provider

    def create_notification(
        self,
        message: NotificationMessage,
        *,
        actor: str = "Enterprise Notification Service",
    ) -> str:
        existing = self._find_by_deduplication_key(
            message.deduplication_key
        )
        if existing:
            self._append_audit(
                existing["notification_id"],
                action="Duplicate Notification Suppressed",
                actor=actor,
                details={
                    "requested_notification_id": message.notification_id,
                    "deduplication_key": message.deduplication_key,
                },
            )
            return existing["notification_id"]

        now = _now()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO notifications (
                    notification_id, event_id, event_name, title, message,
                    severity, category, workflow_id, source_record_id,
                    correlation_id, acknowledgement_required,
                    escalation_minutes, deduplication_key, status,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.notification_id,
                    message.event_id,
                    message.event_name,
                    message.title,
                    message.message,
                    message.severity.value,
                    message.category,
                    message.workflow_id,
                    message.source_record_id,
                    message.correlation_id,
                    1 if message.acknowledgement_required else 0,
                    message.escalation_minutes,
                    message.deduplication_key,
                    NotificationStatus.CREATED.value,
                    json.dumps(
                        message.metadata,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    message.created_at,
                    now,
                ),
            )

            for recipient in message.recipients:
                connection.execute(
                    """
                    INSERT INTO notification_recipients (
                        notification_id, recipient_type, recipient_id,
                        display_name, role, channels_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message.notification_id,
                        recipient.recipient_type,
                        recipient.recipient_id,
                        recipient.display_name,
                        recipient.role,
                        json.dumps(
                            [channel.value for channel in recipient.channels],
                            ensure_ascii=False,
                        ),
                    ),
                )

            connection.commit()

        self._append_audit(
            message.notification_id,
            action="Notification Created",
            actor=actor,
            details={
                "severity": message.severity.value,
                "recipient_count": len(message.recipients),
            },
        )
        self._deliver_notification(message, actor=actor)
        return message.notification_id

    def acknowledge(
        self,
        notification_id: str,
        *,
        acknowledged_by: str,
    ) -> None:
        now = _now()
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE notifications
                SET status = ?, acknowledged_at = ?, acknowledged_by = ?,
                    updated_at = ?
                WHERE notification_id = ?
                  AND status != 'Closed'
                """,
                (
                    NotificationStatus.ACKNOWLEDGED.value,
                    now,
                    acknowledged_by,
                    now,
                    notification_id,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError(
                    f"Notification '{notification_id}' was not found or is closed."
                )
            connection.commit()

        self._append_audit(
            notification_id,
            action="Notification Acknowledged",
            actor=acknowledged_by,
            details={},
        )

    def mark_read(
        self,
        notification_id: str,
        *,
        recipient_id: str,
    ) -> None:
        now = _now()
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE notification_recipients
                SET read_at = ?
                WHERE notification_id = ? AND recipient_id = ?
                """,
                (now, notification_id, recipient_id),
            )
            if cursor.rowcount != 1:
                raise LookupError(
                    "Notification recipient record was not found."
                )

            connection.execute(
                """
                UPDATE notifications
                SET status = CASE
                    WHEN status IN ('Created', 'Queued', 'Delivered')
                    THEN 'Read' ELSE status END,
                    updated_at = ?
                WHERE notification_id = ?
                """,
                (now, notification_id),
            )
            connection.commit()

        self._append_audit(
            notification_id,
            action="Notification Read",
            actor=recipient_id,
            details={},
        )

    def close(
        self,
        notification_id: str,
        *,
        closed_by: str,
        reason: str = "",
    ) -> None:
        now = _now()
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE notifications
                SET status = ?, closed_at = ?, closed_by = ?, updated_at = ?
                WHERE notification_id = ?
                """,
                (
                    NotificationStatus.CLOSED.value,
                    now,
                    closed_by,
                    now,
                    notification_id,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError(
                    f"Notification '{notification_id}' was not found."
                )
            connection.commit()

        self._append_audit(
            notification_id,
            action="Notification Closed",
            actor=closed_by,
            details={"reason": reason},
        )

    def process_escalations(
        self,
        *,
        as_of: str | None = None,
        actor: str = "Notification Escalation Worker",
    ) -> list[str]:
        timestamp = _parse_datetime(as_of) or datetime.now()
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM notifications
                WHERE acknowledgement_required = 1
                  AND escalation_minutes IS NOT NULL
                  AND status NOT IN ('Acknowledged', 'Closed', 'Escalated')
                ORDER BY created_at ASC
                """
            ).fetchall()

        escalated: list[str] = []
        for row in rows:
            created_at = _parse_datetime(row["created_at"])
            if created_at is None:
                continue

            due_at = created_at + timedelta(
                minutes=int(row["escalation_minutes"])
            )
            if due_at > timestamp:
                continue

            notification_id = row["notification_id"]
            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE notifications
                    SET status = ?, updated_at = ?
                    WHERE notification_id = ?
                    """,
                    (
                        NotificationStatus.ESCALATED.value,
                        _now(),
                        notification_id,
                    ),
                )
                connection.commit()

            self._append_audit(
                notification_id,
                action="Notification Escalated",
                actor=actor,
                details={
                    "due_at": due_at.isoformat(timespec="seconds")
                },
            )
            escalated.append(notification_id)

        return escalated

    def list_notifications(
        self,
        *,
        recipient_id: str | None = None,
        status: NotificationStatus | None = None,
        severity: NotificationSeverity | None = None,
        workflow_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conditions = ["1 = 1"]
        values: list[Any] = []
        join = ""

        if recipient_id:
            join = """
                INNER JOIN notification_recipients r
                    ON r.notification_id = n.notification_id
            """
            conditions.append("r.recipient_id = ?")
            values.append(recipient_id)

        if status:
            conditions.append("n.status = ?")
            values.append(status.value)

        if severity:
            conditions.append("n.severity = ?")
            values.append(severity.value)

        if workflow_id:
            conditions.append("n.workflow_id = ?")
            values.append(workflow_id)

        values.append(max(1, min(limit, 1000)))

        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT n.*
                FROM notifications n
                {join}
                WHERE {' AND '.join(conditions)}
                ORDER BY
                    CASE n.severity
                        WHEN 'Emergency' THEN 6
                        WHEN 'Critical' THEN 5
                        WHEN 'High' THEN 4
                        WHEN 'Medium' THEN 3
                        WHEN 'Low' THEN 2
                        ELSE 1
                    END DESC,
                    n.created_at DESC
                LIMIT ?
                """,
                values,
            ).fetchall()

        return [_decode_notification_row(row) for row in rows]

    def executive_brief(
        self,
        *,
        hours: int = 24,
        limit_per_severity: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        since = (
            datetime.now() - timedelta(hours=hours)
        ).isoformat(timespec="seconds")

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM notifications
                WHERE created_at >= ?
                  AND status != 'Closed'
                ORDER BY created_at DESC
                """,
                (since,),
            ).fetchall()

        grouped = {
            severity.value: []
            for severity in NotificationSeverity
        }
        for row in rows:
            bucket = grouped.setdefault(row["severity"], [])
            if len(bucket) < limit_per_severity:
                bucket.append(_decode_notification_row(row))

        return grouped

    def list_audit_history(
        self,
        notification_id: str,
    ) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM notification_audit
                WHERE notification_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (notification_id,),
            ).fetchall()

        return [
            {
                **dict(row),
                "details": _decode_json(row["details_json"], {}),
            }
            for row in rows
        ]

    def _handle_event(
        self,
        event: BusinessEvent,
    ) -> dict[str, Any]:
        route = ROUTES[event.event_name]
        message = self._message_from_event(event, route)
        notification_id = self.create_notification(
            message,
            actor=event.source,
        )
        return {
            "notification_id": notification_id,
            "recipient_count": len(message.recipients),
            "severity": message.severity.value,
        }

    def _handle_direct_request(
        self,
        event: BusinessEvent,
    ) -> dict[str, Any]:
        severity = NotificationSeverity(
            str(
                event.payload.get(
                    "severity",
                    NotificationSeverity.MEDIUM.value,
                )
            )
        )
        roles = tuple(
            event.payload.get("roles", ["Managing Director"])
        )
        channels = tuple(
            DeliveryChannel(channel)
            for channel in event.payload.get(
                "channels",
                [DeliveryChannel.DASHBOARD.value],
            )
        )
        recipients = self._recipients_for_roles(roles, channels)

        message = NotificationMessage(
            notification_id=self._notification_id(),
            event_id=event.event_id,
            event_name=event.event_name,
            title=str(
                event.payload.get("title", "Platform Notification")
            ),
            message=str(
                event.payload.get(
                    "message",
                    event.payload.get("description", ""),
                )
            ),
            severity=severity,
            category=str(
                event.payload.get("category", event.category.value)
            ),
            recipients=recipients,
            workflow_id=event.workflow_id,
            source_record_id=_optional_string(
                event.payload.get("source_record_id")
            ),
            correlation_id=event.correlation_id,
            acknowledgement_required=bool(
                event.payload.get(
                    "acknowledgement_required",
                    severity
                    in {
                        NotificationSeverity.CRITICAL,
                        NotificationSeverity.EMERGENCY,
                    },
                )
            ),
            escalation_minutes=_optional_int(
                event.payload.get("escalation_minutes")
            ),
            deduplication_key=(
                event.idempotency_key
                or f"notification:{event.event_id}"
            ),
            metadata=event.metadata,
        )
        notification_id = self.create_notification(
            message,
            actor=event.source,
        )
        return {
            "notification_id": notification_id,
            "recipient_count": len(recipients),
        }

    def _message_from_event(
        self,
        event: BusinessEvent,
        route: NotificationRoute,
    ) -> NotificationMessage:
        recipients = self._recipients_for_roles(
            route.roles,
            route.channels,
        )
        title = str(
            event.payload.get("title")
            or event.event_name.replace(".", " ").title()
        )
        message = str(
            event.payload.get("description")
            or event.payload.get("message")
            or event.payload.get("reason")
            or "A platform event requires attention."
        )
        severity = self._severity_from_event(event, route)

        return NotificationMessage(
            notification_id=self._notification_id(),
            event_id=event.event_id,
            event_name=event.event_name,
            title=title,
            message=message,
            severity=severity,
            category=event.category.value,
            recipients=recipients,
            workflow_id=event.workflow_id,
            source_record_id=_optional_string(
                event.payload.get("source_record_id")
            ),
            correlation_id=event.correlation_id,
            acknowledgement_required=route.acknowledgement_required,
            escalation_minutes=route.escalation_minutes,
            deduplication_key=(
                event.idempotency_key
                or f"notification:{event.event_id}"
            ),
            metadata={
                **event.metadata,
                "event_payload": event.payload,
                "event_source": event.source,
            },
        )

    @staticmethod
    def _recipients_for_roles(
        roles: tuple[str, ...],
        channels: tuple[DeliveryChannel, ...],
    ) -> tuple[NotificationRecipient, ...]:
        return tuple(
            NotificationRecipient(
                recipient_type="Role",
                recipient_id=f"role:{role.lower().replace(' ', '-')}",
                display_name=role,
                role=role,
                channels=channels,
            )
            for role in roles
        )

    def _deliver_notification(
        self,
        message: NotificationMessage,
        *,
        actor: str,
    ) -> None:
        results: list[DeliveryResult] = []

        for recipient in message.recipients:
            for channel in recipient.channels:
                if self._should_delay_for_quiet_hours(
                    message.severity,
                    channel,
                ):
                    result = DeliveryResult(
                        notification_id=message.notification_id,
                        recipient_id=recipient.recipient_id,
                        channel=channel,
                        success=True,
                        status=NotificationStatus.QUEUED,
                    )
                else:
                    provider = self._providers.get(channel)
                    if provider is None:
                        result = DeliveryResult(
                            notification_id=message.notification_id,
                            recipient_id=recipient.recipient_id,
                            channel=channel,
                            success=False,
                            status=NotificationStatus.FAILED,
                            error_message=(
                                f"No provider registered for {channel.value}."
                            ),
                        )
                    else:
                        result = provider(
                            message,
                            recipient,
                            channel,
                        )

                self._persist_delivery(result)
                results.append(result)

        delivered = any(
            item.success
            and item.status
            in {
                NotificationStatus.DELIVERED,
                NotificationStatus.QUEUED,
            }
            for item in results
        )
        new_status = (
            NotificationStatus.DELIVERED
            if delivered
            else NotificationStatus.FAILED
        )

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE notifications
                SET status = ?, updated_at = ?
                WHERE notification_id = ?
                """,
                (
                    new_status.value,
                    _now(),
                    message.notification_id,
                ),
            )
            connection.commit()

        self._append_audit(
            message.notification_id,
            action="Notification Delivery Completed",
            actor=actor,
            details={
                "delivery_count": len(results),
                "successful": sum(1 for item in results if item.success),
                "failed": sum(1 for item in results if not item.success),
            },
        )

    @staticmethod
    def _dashboard_provider(
        message: NotificationMessage,
        recipient: NotificationRecipient,
        channel: DeliveryChannel,
    ) -> DeliveryResult:
        return DeliveryResult(
            notification_id=message.notification_id,
            recipient_id=recipient.recipient_id,
            channel=channel,
            success=True,
            status=NotificationStatus.DELIVERED,
            delivered_at=_now(),
            provider_reference=(
                f"local:{message.notification_id}:"
                f"{recipient.recipient_id}:{channel.value}"
            ),
        )

    def _should_delay_for_quiet_hours(
        self,
        severity: NotificationSeverity,
        channel: DeliveryChannel,
    ) -> bool:
        if severity in {
            NotificationSeverity.CRITICAL,
            NotificationSeverity.EMERGENCY,
        }:
            return False

        if channel in {
            DeliveryChannel.DASHBOARD,
            DeliveryChannel.EXECUTIVE_BRIEF,
            DeliveryChannel.AI_ASSISTANT,
        }:
            return False

        current_time = datetime.now().time()
        if self._quiet_hours_start <= self._quiet_hours_end:
            return (
                self._quiet_hours_start
                <= current_time
                < self._quiet_hours_end
            )

        return (
            current_time >= self._quiet_hours_start
            or current_time < self._quiet_hours_end
        )

    @staticmethod
    def _severity_from_event(
        event: BusinessEvent,
        route: NotificationRoute,
    ) -> NotificationSeverity:
        explicit = event.payload.get("severity")
        if explicit:
            try:
                return NotificationSeverity(str(explicit))
            except ValueError:
                pass

        if event.priority == EventPriority.CRITICAL:
            return NotificationSeverity.CRITICAL
        if event.priority == EventPriority.HIGH:
            return NotificationSeverity.HIGH
        if event.priority == EventPriority.LOW:
            return NotificationSeverity.LOW
        return route.severity

    def _persist_delivery(
        self,
        result: DeliveryResult,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO notification_deliveries (
                    notification_id, recipient_id, channel, success,
                    status, delivered_at, error_message,
                    provider_reference, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.notification_id,
                    result.recipient_id,
                    result.channel.value,
                    1 if result.success else 0,
                    result.status.value,
                    result.delivered_at,
                    result.error_message,
                    result.provider_reference,
                    _now(),
                ),
            )
            connection.commit()

    def _find_by_deduplication_key(
        self,
        deduplication_key: str | None,
    ) -> dict[str, Any] | None:
        if not deduplication_key:
            return None

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM notifications
                WHERE deduplication_key = ?
                LIMIT 1
                """,
                (deduplication_key,),
            ).fetchone()

        return _decode_notification_row(row) if row else None

    def _append_audit(
        self,
        notification_id: str,
        *,
        action: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO notification_audit (
                    notification_id, action, actor, details_json, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    notification_id,
                    action,
                    actor,
                    json.dumps(
                        details,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    _now(),
                ),
            )
            connection.commit()

    @staticmethod
    def _notification_id() -> str:
        return f"NTF-{uuid4().hex[:16].upper()}"


def _decode_notification_row(
    row: Any,
) -> dict[str, Any]:
    record = dict(row)
    record["metadata"] = _decode_json(
        record.get("metadata_json"),
        {},
    )
    record["acknowledgement_required"] = bool(
        record.get("acknowledgement_required")
    )
    return record


def _decode_json(
    value: str | None,
    default: Any,
) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _parse_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _optional_string(
    value: Any,
) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _optional_int(
    value: Any,
) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


_notification_service = EnterpriseNotificationService()


def get_notification_service() -> EnterpriseNotificationService:
    return _notification_service


def register_notification_subscribers() -> list[str]:
    return _notification_service.register_subscribers()


def list_notifications(
    *,
    recipient_id: str | None = None,
    status: NotificationStatus | None = None,
    severity: NotificationSeverity | None = None,
    workflow_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return _notification_service.list_notifications(
        recipient_id=recipient_id,
        status=status,
        severity=severity,
        workflow_id=workflow_id,
        limit=limit,
    )


def acknowledge_notification(
    notification_id: str,
    *,
    acknowledged_by: str,
) -> None:
    _notification_service.acknowledge(
        notification_id,
        acknowledged_by=acknowledged_by,
    )


def process_notification_escalations(
    *,
    as_of: str | None = None,
    actor: str = "Notification Escalation Worker",
) -> list[str]:
    return _notification_service.process_escalations(
        as_of=as_of,
        actor=actor,
    )


def get_executive_notification_brief(
    *,
    hours: int = 24,
    limit_per_severity: int = 20,
) -> dict[str, list[dict[str, Any]]]:
    return _notification_service.executive_brief(
        hours=hours,
        limit_per_severity=limit_per_severity,
    )