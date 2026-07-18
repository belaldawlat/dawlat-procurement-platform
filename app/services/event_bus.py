"""
Enterprise Event Bus.

Provides the in-process business-event backbone for the Dawlat AI Procurement
& Global Trade Intelligence Platform.

Design goals:
- typed business events;
- publish/subscribe architecture;
- correlation and causation tracing;
- workflow and user context;
- priority handling;
- idempotency;
- retry support;
- dead-letter handling;
- immutable audit records;
- future compatibility with Kafka, RabbitMQ, Azure Service Bus,
  AWS EventBridge and Google Pub/Sub.

This implementation is deliberately provider-neutral and synchronous by
default. It is suitable for the current Streamlit/SQLite architecture and can
later be replaced by a distributed transport without changing publishers or
subscribers.

The event bus does not execute binding commercial or financial actions by
itself. Subscribers remain responsible for enforcing human approval, trust,
risk, payment and governance controls.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from threading import RLock
from typing import Any, Callable, Iterable
from uuid import uuid4

from database.connection import get_connection


class EventPriority(str, Enum):
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"
    CRITICAL = "Critical"


class EventStatus(str, Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    PARTIALLY_COMPLETED = "Partially Completed"
    FAILED = "Failed"
    DEAD_LETTER = "Dead Letter"
    IGNORED = "Ignored"


class EventCategory(str, Enum):
    BUYER = "Buyer"
    SUPPLIER = "Supplier"
    PRODUCT = "Product"
    RFQ = "RFQ"
    QUOTATION = "Quotation"
    PROCUREMENT = "Procurement"
    OPPORTUNITY = "Opportunity"
    WORKFLOW = "Workflow"
    PAYMENT = "Payment"
    FINANCE = "Finance"
    SHIPMENT = "Shipment"
    LOGISTICS = "Logistics"
    INVENTORY = "Inventory"
    WAREHOUSE = "Warehouse"
    COMPLIANCE = "Compliance"
    RISK = "Risk"
    TRUST = "Trust"
    EXECUTIVE = "Executive"
    NOTIFICATION = "Notification"
    MONITORING = "Monitoring"
    SECURITY = "Security"
    SYSTEM = "System"


@dataclass(frozen=True)
class BusinessEvent:
    event_id: str
    event_name: str
    category: EventCategory
    source: str
    payload: dict[str, Any]

    priority: EventPriority = EventPriority.NORMAL
    correlation_id: str | None = None
    causation_id: str | None = None
    workflow_id: str | None = None
    user_id: str | None = None
    idempotency_key: str | None = None
    schema_version: int = 1
    occurred_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubscriberRegistration:
    subscriber_id: str
    event_name: str
    handler_name: str
    priority: int
    active: bool = True


@dataclass
class HandlerResult:
    subscriber_id: str
    handler_name: str
    success: bool
    attempt: int
    started_at: str
    finished_at: str
    error_message: str | None = None
    result_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventDispatchResult:
    event_id: str
    event_name: str
    status: EventStatus
    handler_results: list[HandlerResult] = field(default_factory=list)
    published_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )

    @property
    def successful_handlers(self) -> int:
        return sum(
            1
            for item in self.handler_results
            if item.success
        )

    @property
    def failed_handlers(self) -> int:
        return sum(
            1
            for item in self.handler_results
            if not item.success
        )


EventHandler = Callable[[BusinessEvent], dict[str, Any] | None]


def create_event_bus_tables() -> None:
    """Create event, handler, audit and dead-letter tables."""

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS enterprise_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_name TEXT NOT NULL,
                category TEXT NOT NULL,
                source TEXT NOT NULL,
                priority TEXT NOT NULL,
                correlation_id TEXT,
                causation_id TEXT,
                workflow_id TEXT,
                user_id TEXT,
                idempotency_key TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1,
                payload_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                next_retry_at TEXT,
                occurred_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS enterprise_event_handlers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                subscriber_id TEXT NOT NULL,
                handler_name TEXT NOT NULL,
                success INTEGER NOT NULL,
                attempt INTEGER NOT NULL,
                error_message TEXT,
                result_json TEXT NOT NULL DEFAULT '{}',
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                UNIQUE(event_id, subscriber_id, attempt),
                FOREIGN KEY (event_id)
                    REFERENCES enterprise_events(event_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS enterprise_event_dead_letters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                subscriber_id TEXT,
                handler_name TEXT,
                reason TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                error_trace TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by TEXT,
                resolution_notes TEXT,
                UNIQUE(event_id, subscriber_id),
                FOREIGN KEY (event_id)
                    REFERENCES enterprise_events(event_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS enterprise_event_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id)
                    REFERENCES enterprise_events(event_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_event_idempotency
            ON enterprise_events(idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_event_name_status
            ON enterprise_events(event_name, status)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_event_workflow
            ON enterprise_events(workflow_id, occurred_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_event_correlation
            ON enterprise_events(correlation_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_event_retry
            ON enterprise_events(status, next_retry_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_dead_letter_open
            ON enterprise_event_dead_letters(resolved_at, created_at)
            """
        )

        connection.commit()


class EnterpriseEventBus:
    """
    In-process event dispatcher with persistent audit and retry state.

    Subscribers are registered at application startup. The event bus persists
    each event before dispatch, then stores one handler result per subscriber.
    """

    def __init__(
        self,
        *,
        max_retries: int = 3,
        retry_backoff_seconds: int = 30,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if retry_backoff_seconds < 1:
            raise ValueError(
                "retry_backoff_seconds must be greater than zero."
            )

        create_event_bus_tables()

        self._subscribers: dict[
            str,
            list[tuple[SubscriberRegistration, EventHandler]],
        ] = {}
        self._lock = RLock()
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def subscribe(
        self,
        event_name: str,
        handler: EventHandler,
        *,
        subscriber_id: str | None = None,
        priority: int = 100,
    ) -> SubscriberRegistration:
        """Register one subscriber for an event name or wildcard."""

        cleaned_event_name = event_name.strip()

        if not cleaned_event_name:
            raise ValueError("event_name is required.")

        registration = SubscriberRegistration(
            subscriber_id=(
                subscriber_id
                or f"SUB-{uuid4().hex[:12].upper()}"
            ),
            event_name=cleaned_event_name,
            handler_name=getattr(
                handler,
                "__qualname__",
                getattr(handler, "__name__", "EventHandler"),
            ),
            priority=priority,
            active=True,
        )

        with self._lock:
            registrations = self._subscribers.setdefault(
                cleaned_event_name,
                [],
            )
            registrations.append((registration, handler))
            registrations.sort(
                key=lambda item: item[0].priority
            )

        return registration

    def unsubscribe(
        self,
        subscriber_id: str,
    ) -> bool:
        """Remove a subscriber from all event registrations."""

        removed = False

        with self._lock:
            for event_name in list(self._subscribers):
                current = self._subscribers[event_name]
                filtered = [
                    item
                    for item in current
                    if item[0].subscriber_id != subscriber_id
                ]

                if len(filtered) != len(current):
                    removed = True

                if filtered:
                    self._subscribers[event_name] = filtered
                else:
                    del self._subscribers[event_name]

        return removed

    def publish(
        self,
        event: BusinessEvent,
        *,
        actor: str = "System",
        dispatch: bool = True,
    ) -> EventDispatchResult:
        """
        Persist and optionally dispatch an event.

        Duplicate idempotency keys return the existing event state rather than
        creating or processing the event again.
        """

        self._validate_event(event)

        existing = self._find_by_idempotency_key(
            event.idempotency_key
        )

        if existing is not None:
            self._append_audit(
                existing["event_id"],
                action="Duplicate Event Ignored",
                actor=actor,
                details={
                    "idempotency_key": event.idempotency_key,
                    "requested_event_id": event.event_id,
                },
            )

            return self._dispatch_result_from_database(
                existing["event_id"],
                fallback_status=EventStatus.IGNORED,
            )

        self._persist_event(event)

        self._append_audit(
            event.event_id,
            action="Event Published",
            actor=actor,
            details={
                "event_name": event.event_name,
                "source": event.source,
                "priority": event.priority.value,
            },
        )

        if not dispatch:
            return EventDispatchResult(
                event_id=event.event_id,
                event_name=event.event_name,
                status=EventStatus.PENDING,
            )

        return self.dispatch(
            event.event_id,
            actor=actor,
        )

    def publish_name(
        self,
        event_name: str,
        *,
        category: EventCategory,
        source: str,
        payload: dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        workflow_id: str | None = None,
        user_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        actor: str = "System",
        dispatch: bool = True,
    ) -> EventDispatchResult:
        """Convenience publishing method."""

        event = create_business_event(
            event_name=event_name,
            category=category,
            source=source,
            payload=payload,
            priority=priority,
            correlation_id=correlation_id,
            causation_id=causation_id,
            workflow_id=workflow_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
            metadata=metadata or {},
        )

        return self.publish(
            event,
            actor=actor,
            dispatch=dispatch,
        )

    def dispatch(
        self,
        event_id: str,
        *,
        actor: str = "System",
    ) -> EventDispatchResult:
        """Dispatch a persisted event to matching subscribers."""

        event = self.get_event(event_id)

        if event is None:
            raise LookupError(
                f"Event '{event_id}' was not found."
            )

        business_event = self._record_to_event(event)
        handlers = self._matching_handlers(
            business_event.event_name
        )

        self._update_event_status(
            event_id,
            EventStatus.PROCESSING,
        )

        self._append_audit(
            event_id,
            action="Dispatch Started",
            actor=actor,
            details={
                "handler_count": len(handlers),
            },
        )

        if not handlers:
            self._update_event_status(
                event_id,
                EventStatus.COMPLETED,
            )
            self._append_audit(
                event_id,
                action="Dispatch Completed",
                actor=actor,
                details={
                    "handler_count": 0,
                    "message": "No subscribers registered.",
                },
            )

            return EventDispatchResult(
                event_id=event_id,
                event_name=business_event.event_name,
                status=EventStatus.COMPLETED,
                handler_results=[],
            )

        handler_results: list[HandlerResult] = []

        for registration, handler in handlers:
            result = self._execute_handler(
                business_event,
                registration,
                handler,
            )
            handler_results.append(result)
            self._persist_handler_result(
                event_id,
                result,
            )

        success_count = sum(
            1
            for item in handler_results
            if item.success
        )
        failure_count = len(handler_results) - success_count

        if failure_count == 0:
            status = EventStatus.COMPLETED
            self._update_event_status(
                event_id,
                status,
                increment_attempt=True,
            )
        elif success_count > 0:
            status = EventStatus.PARTIALLY_COMPLETED
            self._schedule_retry_or_dead_letter(
                business_event,
                handler_results,
                actor=actor,
            )
        else:
            status = EventStatus.FAILED
            self._schedule_retry_or_dead_letter(
                business_event,
                handler_results,
                actor=actor,
            )

        self._append_audit(
            event_id,
            action="Dispatch Completed",
            actor=actor,
            details={
                "status": status.value,
                "successful_handlers": success_count,
                "failed_handlers": failure_count,
            },
        )

        return EventDispatchResult(
            event_id=event_id,
            event_name=business_event.event_name,
            status=status,
            handler_results=handler_results,
        )

    def retry_due_events(
        self,
        *,
        as_of: str | None = None,
        limit: int = 100,
        actor: str = "Event Retry Worker",
    ) -> list[EventDispatchResult]:
        """Dispatch events whose retry time has arrived."""

        timestamp = as_of or _now()

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT event_id
                FROM enterprise_events
                WHERE status IN (
                    'Failed',
                    'Partially Completed'
                )
                  AND next_retry_at IS NOT NULL
                  AND next_retry_at <= ?
                ORDER BY next_retry_at ASC
                LIMIT ?
                """,
                (
                    timestamp,
                    max(1, min(limit, 1000)),
                ),
            ).fetchall()

        return [
            self.dispatch(
                row["event_id"],
                actor=actor,
            )
            for row in rows
        ]

    def get_event(
        self,
        event_id: str,
    ) -> dict[str, Any] | None:
        """Return one decoded event record."""

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM enterprise_events
                WHERE event_id = ?
                LIMIT 1
                """,
                (event_id,),
            ).fetchone()

        return _decode_event_row(row) if row else None

    def list_events(
        self,
        *,
        event_name: str | None = None,
        status: EventStatus | None = None,
        workflow_id: str | None = None,
        correlation_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List events using optional filters."""

        conditions = ["1 = 1"]
        values: list[Any] = []

        if event_name:
            conditions.append("event_name = ?")
            values.append(event_name)

        if status:
            conditions.append("status = ?")
            values.append(status.value)

        if workflow_id:
            conditions.append("workflow_id = ?")
            values.append(workflow_id)

        if correlation_id:
            conditions.append("correlation_id = ?")
            values.append(correlation_id)

        values.append(max(1, min(limit, 1000)))

        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM enterprise_events
                WHERE {' AND '.join(conditions)}
                ORDER BY occurred_at DESC, id DESC
                LIMIT ?
                """,
                values,
            ).fetchall()

        return [
            _decode_event_row(row)
            for row in rows
        ]

    def list_dead_letters(
        self,
        *,
        include_resolved: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List failed event deliveries."""

        conditions = (
            ""
            if include_resolved
            else "WHERE resolved_at IS NULL"
        )

        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM enterprise_event_dead_letters
                {conditions}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 1000)),),
            ).fetchall()

        return [
            {
                **dict(row),
                "payload": _decode_json(
                    row["payload_json"],
                    {},
                ),
                "metadata": _decode_json(
                    row["metadata_json"],
                    {},
                ),
            }
            for row in rows
        ]

    def resolve_dead_letter(
        self,
        dead_letter_id: int,
        *,
        resolved_by: str,
        resolution_notes: str,
    ) -> None:
        """Mark a dead-letter record as resolved."""

        now = _now()

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT event_id
                FROM enterprise_event_dead_letters
                WHERE id = ?
                LIMIT 1
                """,
                (dead_letter_id,),
            ).fetchone()

            if row is None:
                raise LookupError(
                    f"Dead-letter record {dead_letter_id} was not found."
                )

            connection.execute(
                """
                UPDATE enterprise_event_dead_letters
                SET
                    resolved_at = ?,
                    resolved_by = ?,
                    resolution_notes = ?
                WHERE id = ?
                """,
                (
                    now,
                    resolved_by,
                    resolution_notes,
                    dead_letter_id,
                ),
            )

            self._append_audit_with_connection(
                connection,
                row["event_id"],
                action="Dead Letter Resolved",
                actor=resolved_by,
                details={
                    "dead_letter_id": dead_letter_id,
                    "resolution_notes": resolution_notes,
                },
                created_at=now,
            )

            connection.commit()

    def list_audit_history(
        self,
        event_id: str,
    ) -> list[dict[str, Any]]:
        """Return immutable event audit history."""

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM enterprise_event_audit
                WHERE event_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (event_id,),
            ).fetchall()

        return [
            {
                **dict(row),
                "details": _decode_json(
                    row["details_json"],
                    {},
                ),
            }
            for row in rows
        ]

    def _execute_handler(
        self,
        event: BusinessEvent,
        registration: SubscriberRegistration,
        handler: EventHandler,
    ) -> HandlerResult:
        attempt = self._next_handler_attempt(
            event.event_id,
            registration.subscriber_id,
        )
        started_at = _now()

        try:
            result = handler(event) or {}

            if not isinstance(result, dict):
                result = {
                    "result": str(result),
                }

            return HandlerResult(
                subscriber_id=registration.subscriber_id,
                handler_name=registration.handler_name,
                success=True,
                attempt=attempt,
                started_at=started_at,
                finished_at=_now(),
                result_payload=result,
            )

        except Exception as error:
            return HandlerResult(
                subscriber_id=registration.subscriber_id,
                handler_name=registration.handler_name,
                success=False,
                attempt=attempt,
                started_at=started_at,
                finished_at=_now(),
                error_message=str(error),
                result_payload={
                    "traceback": traceback.format_exc(),
                },
            )

    def _matching_handlers(
        self,
        event_name: str,
    ) -> list[tuple[SubscriberRegistration, EventHandler]]:
        with self._lock:
            handlers = list(
                self._subscribers.get(event_name, [])
            )
            handlers.extend(
                self._subscribers.get("*", [])
            )

        unique: dict[
            str,
            tuple[SubscriberRegistration, EventHandler],
        ] = {}

        for registration, handler in handlers:
            if registration.active:
                unique[registration.subscriber_id] = (
                    registration,
                    handler,
                )

        return sorted(
            unique.values(),
            key=lambda item: item[0].priority,
        )

    def _schedule_retry_or_dead_letter(
        self,
        event: BusinessEvent,
        results: list[HandlerResult],
        *,
        actor: str,
    ) -> None:
        current = self.get_event(event.event_id)

        if current is None:
            return

        next_attempt = int(
            current.get("attempt_count", 0)
        ) + 1

        failed_results = [
            item
            for item in results
            if not item.success
        ]

        if next_attempt <= self._max_retries:
            retry_at = (
                datetime.now()
                + timedelta(
                    seconds=(
                        self._retry_backoff_seconds
                        * max(1, next_attempt)
                    )
                )
            ).isoformat(timespec="seconds")

            status = (
                EventStatus.PARTIALLY_COMPLETED
                if any(item.success for item in results)
                else EventStatus.FAILED
            )

            self._update_event_status(
                event.event_id,
                status,
                increment_attempt=True,
                next_retry_at=retry_at,
            )

            self._append_audit(
                event.event_id,
                action="Retry Scheduled",
                actor=actor,
                details={
                    "attempt": next_attempt,
                    "retry_at": retry_at,
                    "failed_handlers": [
                        item.handler_name
                        for item in failed_results
                    ],
                },
            )
            return

        self._update_event_status(
            event.event_id,
            EventStatus.DEAD_LETTER,
            increment_attempt=True,
            next_retry_at=None,
        )

        for item in failed_results:
            self._insert_dead_letter(
                event,
                item,
                retry_count=next_attempt,
            )

        self._append_audit(
            event.event_id,
            action="Moved to Dead Letter",
            actor=actor,
            details={
                "retry_count": next_attempt,
                "failed_handlers": [
                    item.handler_name
                    for item in failed_results
                ],
            },
        )

    def _persist_event(
        self,
        event: BusinessEvent,
    ) -> None:
        now = _now()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO enterprise_events (
                    event_id,
                    event_name,
                    category,
                    source,
                    priority,
                    correlation_id,
                    causation_id,
                    workflow_id,
                    user_id,
                    idempotency_key,
                    schema_version,
                    payload_json,
                    metadata_json,
                    status,
                    attempt_count,
                    occurred_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, 0, ?, ?, ?
                )
                """,
                (
                    event.event_id,
                    event.event_name,
                    event.category.value,
                    event.source,
                    event.priority.value,
                    event.correlation_id,
                    event.causation_id,
                    event.workflow_id,
                    event.user_id,
                    event.idempotency_key,
                    event.schema_version,
                    json.dumps(
                        event.payload,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    json.dumps(
                        event.metadata,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    EventStatus.PENDING.value,
                    event.occurred_at,
                    now,
                    now,
                ),
            )
            connection.commit()

    def _persist_handler_result(
        self,
        event_id: str,
        result: HandlerResult,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO enterprise_event_handlers (
                    event_id,
                    subscriber_id,
                    handler_name,
                    success,
                    attempt,
                    error_message,
                    result_json,
                    started_at,
                    finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    result.subscriber_id,
                    result.handler_name,
                    1 if result.success else 0,
                    result.attempt,
                    result.error_message,
                    json.dumps(
                        result.result_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    result.started_at,
                    result.finished_at,
                ),
            )
            connection.commit()

    def _insert_dead_letter(
        self,
        event: BusinessEvent,
        result: HandlerResult,
        *,
        retry_count: int,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO enterprise_event_dead_letters (
                    event_id,
                    event_name,
                    subscriber_id,
                    handler_name,
                    reason,
                    payload_json,
                    metadata_json,
                    error_trace,
                    retry_count,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_name,
                    result.subscriber_id,
                    result.handler_name,
                    result.error_message
                    or "Unknown handler failure.",
                    json.dumps(
                        event.payload,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    json.dumps(
                        event.metadata,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    result.result_payload.get("traceback"),
                    retry_count,
                    _now(),
                ),
            )
            connection.commit()

    def _update_event_status(
        self,
        event_id: str,
        status: EventStatus,
        *,
        increment_attempt: bool = False,
        next_retry_at: str | None = None,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                f"""
                UPDATE enterprise_events
                SET
                    status = ?,
                    attempt_count = attempt_count + ?,
                    next_retry_at = ?,
                    updated_at = ?
                WHERE event_id = ?
                """,
                (
                    status.value,
                    1 if increment_attempt else 0,
                    next_retry_at,
                    _now(),
                    event_id,
                ),
            )
            connection.commit()

    def _find_by_idempotency_key(
        self,
        idempotency_key: str | None,
    ) -> dict[str, Any] | None:
        if not idempotency_key:
            return None

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM enterprise_events
                WHERE idempotency_key = ?
                LIMIT 1
                """,
                (idempotency_key,),
            ).fetchone()

        return _decode_event_row(row) if row else None

    def _next_handler_attempt(
        self,
        event_id: str,
        subscriber_id: str,
    ) -> int:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT MAX(attempt) AS maximum_attempt
                FROM enterprise_event_handlers
                WHERE event_id = ?
                  AND subscriber_id = ?
                """,
                (
                    event_id,
                    subscriber_id,
                ),
            ).fetchone()

        maximum = (
            int(row["maximum_attempt"])
            if row
            and row["maximum_attempt"] is not None
            else 0
        )

        return maximum + 1

    def _dispatch_result_from_database(
        self,
        event_id: str,
        *,
        fallback_status: EventStatus,
    ) -> EventDispatchResult:
        event = self.get_event(event_id)

        if event is None:
            raise LookupError(
                f"Event '{event_id}' was not found."
            )

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM enterprise_event_handlers
                WHERE event_id = ?
                ORDER BY id ASC
                """,
                (event_id,),
            ).fetchall()

        results = [
            HandlerResult(
                subscriber_id=row["subscriber_id"],
                handler_name=row["handler_name"],
                success=bool(row["success"]),
                attempt=int(row["attempt"]),
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                error_message=row["error_message"],
                result_payload=_decode_json(
                    row["result_json"],
                    {},
                ),
            )
            for row in rows
        ]

        try:
            status = EventStatus(event["status"])
        except ValueError:
            status = fallback_status

        return EventDispatchResult(
            event_id=event_id,
            event_name=event["event_name"],
            status=status,
            handler_results=results,
        )

    def _record_to_event(
        self,
        record: dict[str, Any],
    ) -> BusinessEvent:
        return BusinessEvent(
            event_id=record["event_id"],
            event_name=record["event_name"],
            category=EventCategory(record["category"]),
            source=record["source"],
            payload=record["payload"],
            priority=EventPriority(record["priority"]),
            correlation_id=record.get("correlation_id"),
            causation_id=record.get("causation_id"),
            workflow_id=record.get("workflow_id"),
            user_id=record.get("user_id"),
            idempotency_key=record.get("idempotency_key"),
            schema_version=int(record.get("schema_version", 1)),
            occurred_at=record["occurred_at"],
            metadata=record["metadata"],
        )

    def _append_audit(
        self,
        event_id: str,
        *,
        action: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        with get_connection() as connection:
            self._append_audit_with_connection(
                connection,
                event_id,
                action=action,
                actor=actor,
                details=details,
                created_at=_now(),
            )
            connection.commit()

    @staticmethod
    def _append_audit_with_connection(
        connection: Any,
        event_id: str,
        *,
        action: str,
        actor: str,
        details: dict[str, Any],
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO enterprise_event_audit (
                event_id,
                action,
                actor,
                details_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_id,
                action,
                actor,
                json.dumps(
                    details,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                created_at,
            ),
        )

    @staticmethod
    def _validate_event(
        event: BusinessEvent,
    ) -> None:
        if not event.event_id.strip():
            raise ValueError("event_id is required.")
        if not event.event_name.strip():
            raise ValueError("event_name is required.")
        if not event.source.strip():
            raise ValueError("source is required.")
        if event.schema_version < 1:
            raise ValueError(
                "schema_version must be at least 1."
            )
        if not isinstance(event.payload, dict):
            raise TypeError("payload must be a dictionary.")
        if not isinstance(event.metadata, dict):
            raise TypeError("metadata must be a dictionary.")


def create_business_event(
    *,
    event_name: str,
    category: EventCategory,
    source: str,
    payload: dict[str, Any],
    priority: EventPriority = EventPriority.NORMAL,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    workflow_id: str | None = None,
    user_id: str | None = None,
    idempotency_key: str | None = None,
    schema_version: int = 1,
    metadata: dict[str, Any] | None = None,
) -> BusinessEvent:
    """Create a new typed business event."""

    return BusinessEvent(
        event_id=f"EVT-{uuid4().hex[:16].upper()}",
        event_name=event_name.strip(),
        category=category,
        source=source.strip(),
        payload=payload,
        priority=priority,
        correlation_id=(
            correlation_id
            or f"COR-{uuid4().hex[:16].upper()}"
        ),
        causation_id=causation_id,
        workflow_id=workflow_id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        schema_version=schema_version,
        metadata=metadata or {},
    )


def _decode_event_row(
    row: Any,
) -> dict[str, Any]:
    record = dict(row)
    record["payload"] = _decode_json(
        record.get("payload_json"),
        {},
    )
    record["metadata"] = _decode_json(
        record.get("metadata_json"),
        {},
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


def _now() -> str:
    return datetime.now().isoformat(
        timespec="seconds"
    )


_event_bus = EnterpriseEventBus()


def get_event_bus() -> EnterpriseEventBus:
    """Return the platform event bus singleton."""

    return _event_bus


def subscribe(
    event_name: str,
    handler: EventHandler,
    *,
    subscriber_id: str | None = None,
    priority: int = 100,
) -> SubscriberRegistration:
    """Public subscription helper."""

    return _event_bus.subscribe(
        event_name,
        handler,
        subscriber_id=subscriber_id,
        priority=priority,
    )


def publish(
    event: BusinessEvent,
    *,
    actor: str = "System",
    dispatch: bool = True,
) -> EventDispatchResult:
    """Public event publishing helper."""

    return _event_bus.publish(
        event,
        actor=actor,
        dispatch=dispatch,
    )


def publish_event(
    event_name: str,
    *,
    category: EventCategory,
    source: str,
    payload: dict[str, Any],
    priority: EventPriority = EventPriority.NORMAL,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    workflow_id: str | None = None,
    user_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor: str = "System",
    dispatch: bool = True,
) -> EventDispatchResult:
    """Public convenience publishing helper."""

    return _event_bus.publish_name(
        event_name,
        category=category,
        source=source,
        payload=payload,
        priority=priority,
        correlation_id=correlation_id,
        causation_id=causation_id,
        workflow_id=workflow_id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
        actor=actor,
        dispatch=dispatch,
    )