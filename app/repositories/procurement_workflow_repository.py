"""
Procurement Workflow Repository.

Persistent storage for autonomous procurement workflows.

This repository provides:
- workflow creation and retrieval;
- optimistic locking;
- JSON snapshots of the complete orchestrated workflow;
- stage, status and monitoring persistence;
- immutable workflow events and audit history;
- version snapshots;
- archive and soft-delete controls;
- active, blocked and completed workflow queries;
- search support;
- transaction-safe SQLite operations.

The repository depends only on the platform database connection layer and
serialized workflow data. It does not contain procurement decision logic.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable

from database.connection import get_connection


ACTIVE_STATUSES = {
    "Not Started",
    "In Progress",
    "Waiting for Information",
    "Waiting for Approval",
    "Ready for Next Stage",
}

TERMINAL_STATUSES = {
    "Completed",
    "Cancelled",
}


class WorkflowNotFoundError(LookupError):
    """Raised when a workflow cannot be found."""


class WorkflowVersionConflictError(RuntimeError):
    """Raised when optimistic locking detects a stale update."""


class WorkflowRepositoryError(RuntimeError):
    """Raised when workflow persistence fails."""


def create_workflow_tables() -> None:
    """Create workflow persistence tables and indexes."""

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS procurement_workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                product TEXT NOT NULL,
                destination TEXT NOT NULL,
                buyer_name TEXT,
                supplier_name TEXT,
                current_stage TEXT NOT NULL,
                status TEXT NOT NULL,
                decision_id TEXT,
                opportunity_score INTEGER NOT NULL DEFAULT 0,
                risk_score INTEGER NOT NULL DEFAULT 0,
                trust_score INTEGER NOT NULL DEFAULT 0,
                confidence_score INTEGER NOT NULL DEFAULT 0,
                blocker_count INTEGER NOT NULL DEFAULT 0,
                priority_count INTEGER NOT NULL DEFAULT 0,
                monitoring_enabled INTEGER NOT NULL DEFAULT 1,
                next_monitor_at TEXT,
                last_monitored_at TEXT,
                snapshot_json TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                archived_at TEXT,
                deleted_at TEXT,
                created_by TEXT NOT NULL DEFAULT 'System',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS procurement_workflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                actor TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                UNIQUE(workflow_id, event_id),
                FOREIGN KEY (workflow_id)
                    REFERENCES procurement_workflows(workflow_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS procurement_workflow_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                old_stage TEXT,
                new_stage TEXT,
                old_status TEXT,
                new_status TEXT,
                old_version INTEGER,
                new_version INTEGER,
                reason TEXT,
                changes_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id)
                    REFERENCES procurement_workflows(workflow_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS procurement_workflow_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(workflow_id, version),
                FOREIGN KEY (workflow_id)
                    REFERENCES procurement_workflows(workflow_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workflow_status
            ON procurement_workflows(status)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workflow_stage
            ON procurement_workflows(current_stage)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workflow_updated
            ON procurement_workflows(updated_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workflow_product
            ON procurement_workflows(product)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workflow_monitoring
            ON procurement_workflows(
                monitoring_enabled,
                next_monitor_at
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workflow_events
            ON procurement_workflow_events(
                workflow_id,
                created_at
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workflow_audit
            ON procurement_workflow_audit(
                workflow_id,
                created_at
            )
            """
        )

        connection.commit()


class ProcurementWorkflowRepository:
    """Repository for persisted procurement workflows."""

    def __init__(self) -> None:
        create_workflow_tables()

    def create_workflow(
        self,
        workflow: Any,
        *,
        created_by: str = "System",
    ) -> int:
        """Persist a new workflow and its initial version."""

        now = _now()
        snapshot = _serialize(workflow)
        summary = _workflow_summary(workflow)

        try:
            with get_connection() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO procurement_workflows (
                        workflow_id,
                        title,
                        product,
                        destination,
                        buyer_name,
                        supplier_name,
                        current_stage,
                        status,
                        decision_id,
                        opportunity_score,
                        risk_score,
                        trust_score,
                        confidence_score,
                        blocker_count,
                        priority_count,
                        monitoring_enabled,
                        snapshot_json,
                        version,
                        created_by,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, 1, ?, ?, ?
                    )
                    """,
                    (
                        summary["workflow_id"],
                        summary["title"],
                        summary["product"],
                        summary["destination"],
                        summary["buyer_name"],
                        summary["supplier_name"],
                        summary["current_stage"],
                        summary["status"],
                        summary["decision_id"],
                        summary["opportunity_score"],
                        summary["risk_score"],
                        summary["trust_score"],
                        summary["confidence_score"],
                        summary["blocker_count"],
                        summary["priority_count"],
                        1,
                        snapshot,
                        created_by,
                        now,
                        now,
                    ),
                )

                self._insert_version(
                    connection,
                    workflow_id=summary["workflow_id"],
                    version=1,
                    snapshot_json=snapshot,
                    actor=created_by,
                    created_at=now,
                )

                self._insert_new_events(
                    connection,
                    workflow_id=summary["workflow_id"],
                    events=getattr(workflow, "events", []),
                )

                self._insert_audit(
                    connection,
                    workflow_id=summary["workflow_id"],
                    action="Workflow Created",
                    actor=created_by,
                    old_stage=None,
                    new_stage=summary["current_stage"],
                    old_status=None,
                    new_status=summary["status"],
                    old_version=None,
                    new_version=1,
                    reason="Initial workflow persistence.",
                    changes={"created": True},
                    created_at=now,
                )

                connection.commit()
                return int(cursor.lastrowid)

        except Exception as error:
            raise WorkflowRepositoryError(
                f"Unable to create workflow: {error}"
            ) from error

    def get_workflow(
        self,
        workflow_id: str,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        """Return one persisted workflow record and decoded snapshot."""

        conditions = ["workflow_id = ?"]
        values: list[Any] = [workflow_id]

        if not include_archived:
            conditions.append("archived_at IS NULL")

        if not include_deleted:
            conditions.append("deleted_at IS NULL")

        query = f"""
            SELECT *
            FROM procurement_workflows
            WHERE {' AND '.join(conditions)}
            LIMIT 1
        """

        with get_connection() as connection:
            row = connection.execute(
                query,
                values,
            ).fetchone()

        if row is None:
            raise WorkflowNotFoundError(
                f"Workflow '{workflow_id}' was not found."
            )

        return _row_to_record(row)

    def update_workflow(
        self,
        workflow: Any,
        *,
        expected_version: int,
        actor: str = "System",
        reason: str = "",
    ) -> int:
        """
        Persist a workflow update using optimistic locking.

        Returns the new version.
        """

        workflow_id = str(
            getattr(workflow, "workflow_id", "")
        ).strip()

        if not workflow_id:
            raise ValueError("Workflow ID is required.")

        existing = self.get_workflow(
            workflow_id,
            include_archived=True,
        )

        current_version = int(existing["version"])

        if current_version != expected_version:
            raise WorkflowVersionConflictError(
                f"Workflow '{workflow_id}' is version "
                f"{current_version}, not {expected_version}."
            )

        new_version = current_version + 1
        now = _now()
        snapshot = _serialize(workflow)
        summary = _workflow_summary(workflow)

        try:
            with get_connection() as connection:
                cursor = connection.execute(
                    """
                    UPDATE procurement_workflows
                    SET
                        title = ?,
                        product = ?,
                        destination = ?,
                        buyer_name = ?,
                        supplier_name = ?,
                        current_stage = ?,
                        status = ?,
                        decision_id = ?,
                        opportunity_score = ?,
                        risk_score = ?,
                        trust_score = ?,
                        confidence_score = ?,
                        blocker_count = ?,
                        priority_count = ?,
                        snapshot_json = ?,
                        version = ?,
                        updated_at = ?
                    WHERE workflow_id = ?
                      AND version = ?
                      AND deleted_at IS NULL
                    """,
                    (
                        summary["title"],
                        summary["product"],
                        summary["destination"],
                        summary["buyer_name"],
                        summary["supplier_name"],
                        summary["current_stage"],
                        summary["status"],
                        summary["decision_id"],
                        summary["opportunity_score"],
                        summary["risk_score"],
                        summary["trust_score"],
                        summary["confidence_score"],
                        summary["blocker_count"],
                        summary["priority_count"],
                        snapshot,
                        new_version,
                        now,
                        workflow_id,
                        expected_version,
                    ),
                )

                if cursor.rowcount != 1:
                    raise WorkflowVersionConflictError(
                        f"Workflow '{workflow_id}' changed before update."
                    )

                self._insert_version(
                    connection,
                    workflow_id=workflow_id,
                    version=new_version,
                    snapshot_json=snapshot,
                    actor=actor,
                    created_at=now,
                )

                self._insert_new_events(
                    connection,
                    workflow_id=workflow_id,
                    events=getattr(workflow, "events", []),
                )

                self._insert_audit(
                    connection,
                    workflow_id=workflow_id,
                    action="Workflow Updated",
                    actor=actor,
                    old_stage=existing["current_stage"],
                    new_stage=summary["current_stage"],
                    old_status=existing["status"],
                    new_status=summary["status"],
                    old_version=current_version,
                    new_version=new_version,
                    reason=reason,
                    changes=_summary_changes(
                        existing,
                        summary,
                    ),
                    created_at=now,
                )

                connection.commit()
                return new_version

        except WorkflowVersionConflictError:
            raise
        except Exception as error:
            raise WorkflowRepositoryError(
                f"Unable to update workflow: {error}"
            ) from error

    def advance_stage(
        self,
        workflow_id: str,
        *,
        new_stage: str,
        new_status: str,
        actor: str,
        reason: str,
        expected_version: int,
    ) -> int:
        """Update stage and status without replacing the snapshot."""

        return self._update_control_state(
            workflow_id=workflow_id,
            new_stage=new_stage,
            new_status=new_status,
            actor=actor,
            reason=reason,
            expected_version=expected_version,
            action="Stage Advanced",
        )

    def block_workflow(
        self,
        workflow_id: str,
        *,
        reason: str,
        actor: str,
        expected_version: int,
    ) -> int:
        """Persist a blocked workflow state."""

        return self._update_control_state(
            workflow_id=workflow_id,
            new_stage="Blocked",
            new_status="Blocked",
            actor=actor,
            reason=reason,
            expected_version=expected_version,
            action="Workflow Blocked",
        )

    def approve_stage(
        self,
        workflow_id: str,
        *,
        actor: str,
        reason: str,
        expected_version: int,
    ) -> int:
        """Record stage approval and move status to ready."""

        return self._update_control_state(
            workflow_id=workflow_id,
            new_stage=None,
            new_status="Ready for Next Stage",
            actor=actor,
            reason=reason,
            expected_version=expected_version,
            action="Stage Approved",
        )

    def reject_stage(
        self,
        workflow_id: str,
        *,
        actor: str,
        reason: str,
        expected_version: int,
    ) -> int:
        """Record stage rejection and block the workflow."""

        return self._update_control_state(
            workflow_id=workflow_id,
            new_stage="Blocked",
            new_status="Blocked",
            actor=actor,
            reason=reason,
            expected_version=expected_version,
            action="Stage Rejected",
        )

    def add_event(
        self,
        workflow_id: str,
        *,
        event_id: str,
        stage: str,
        event_type: str,
        message: str,
        actor: str,
        metadata: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> int:
        """Append one immutable workflow event."""

        self._ensure_exists(workflow_id)
        timestamp = created_at or _now()

        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO procurement_workflow_events (
                    workflow_id,
                    event_id,
                    stage,
                    event_type,
                    message,
                    actor,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_id,
                    event_id,
                    stage,
                    event_type,
                    message,
                    actor,
                    json.dumps(
                        metadata or {},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    timestamp,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def append_audit_log(
        self,
        workflow_id: str,
        *,
        action: str,
        actor: str,
        reason: str = "",
        changes: dict[str, Any] | None = None,
    ) -> int:
        """Append a general audit record."""

        record = self.get_workflow(
            workflow_id,
            include_archived=True,
        )
        now = _now()

        with get_connection() as connection:
            cursor = self._insert_audit(
                connection,
                workflow_id=workflow_id,
                action=action,
                actor=actor,
                old_stage=record["current_stage"],
                new_stage=record["current_stage"],
                old_status=record["status"],
                new_status=record["status"],
                old_version=record["version"],
                new_version=record["version"],
                reason=reason,
                changes=changes or {},
                created_at=now,
            )
            connection.commit()
            return int(cursor.lastrowid)

    def update_monitoring_state(
        self,
        workflow_id: str,
        *,
        enabled: bool,
        next_monitor_at: str | None = None,
        last_monitored_at: str | None = None,
        actor: str = "System",
    ) -> None:
        """Update workflow monitoring configuration."""

        self._ensure_exists(workflow_id)
        now = _now()

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE procurement_workflows
                SET
                    monitoring_enabled = ?,
                    next_monitor_at = ?,
                    last_monitored_at = ?,
                    updated_at = ?
                WHERE workflow_id = ?
                  AND deleted_at IS NULL
                """,
                (
                    1 if enabled else 0,
                    next_monitor_at,
                    last_monitored_at,
                    now,
                    workflow_id,
                ),
            )

            self._insert_audit(
                connection,
                workflow_id=workflow_id,
                action="Monitoring Updated",
                actor=actor,
                old_stage=None,
                new_stage=None,
                old_status=None,
                new_status=None,
                old_version=None,
                new_version=None,
                reason="Workflow monitoring configuration changed.",
                changes={
                    "monitoring_enabled": enabled,
                    "next_monitor_at": next_monitor_at,
                    "last_monitored_at": last_monitored_at,
                },
                created_at=now,
            )

            connection.commit()

    def list_due_for_monitoring(
        self,
        *,
        as_of: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List active workflows due for monitoring."""

        timestamp = as_of or _now()

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM procurement_workflows
                WHERE monitoring_enabled = 1
                  AND deleted_at IS NULL
                  AND archived_at IS NULL
                  AND status NOT IN ('Completed', 'Cancelled')
                  AND (
                      next_monitor_at IS NULL
                      OR next_monitor_at <= ?
                  )
                ORDER BY
                    COALESCE(next_monitor_at, created_at) ASC,
                    updated_at ASC
                LIMIT ?
                """,
                (
                    timestamp,
                    max(1, min(limit, 1000)),
                ),
            ).fetchall()

        return [_row_to_record(row) for row in rows]

    def list_active_workflows(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._list_by_statuses(
            ACTIVE_STATUSES,
            limit=limit,
        )

    def list_blocked_workflows(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._list_by_statuses(
            {"Blocked"},
            limit=limit,
        )

    def list_completed_workflows(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._list_by_statuses(
            {"Completed"},
            limit=limit,
        )

    def search_workflows(
        self,
        search_text: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search workflow summaries."""

        conditions = ["deleted_at IS NULL"]
        values: list[Any] = []

        if not include_archived:
            conditions.append("archived_at IS NULL")

        if search_text.strip():
            pattern = f"%{search_text.strip()}%"
            conditions.append(
                """
                (
                    workflow_id LIKE ?
                    OR title LIKE ?
                    OR product LIKE ?
                    OR destination LIKE ?
                    OR buyer_name LIKE ?
                    OR supplier_name LIKE ?
                    OR decision_id LIKE ?
                )
                """
            )
            values.extend([pattern] * 7)

        if status:
            conditions.append("status = ?")
            values.append(status)

        if stage:
            conditions.append("current_stage = ?")
            values.append(stage)

        values.append(max(1, min(limit, 1000)))

        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM procurement_workflows
                WHERE {' AND '.join(conditions)}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                values,
            ).fetchall()

        return [_row_to_record(row) for row in rows]

    def archive_workflow(
        self,
        workflow_id: str,
        *,
        actor: str,
        reason: str = "",
    ) -> None:
        """Archive a workflow without deleting history."""

        self._set_archive_state(
            workflow_id,
            archived=True,
            actor=actor,
            reason=reason,
        )

    def restore_workflow(
        self,
        workflow_id: str,
        *,
        actor: str,
        reason: str = "",
    ) -> None:
        """Restore an archived workflow."""

        self._set_archive_state(
            workflow_id,
            archived=False,
            actor=actor,
            reason=reason,
        )

    def soft_delete_workflow(
        self,
        workflow_id: str,
        *,
        actor: str,
        reason: str,
    ) -> None:
        """Soft-delete a workflow while retaining audit history."""

        self._ensure_exists(workflow_id)
        now = _now()

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE procurement_workflows
                SET
                    deleted_at = ?,
                    monitoring_enabled = 0,
                    updated_at = ?
                WHERE workflow_id = ?
                """,
                (
                    now,
                    now,
                    workflow_id,
                ),
            )

            self._insert_audit(
                connection,
                workflow_id=workflow_id,
                action="Workflow Soft Deleted",
                actor=actor,
                old_stage=None,
                new_stage=None,
                old_status=None,
                new_status=None,
                old_version=None,
                new_version=None,
                reason=reason,
                changes={"deleted_at": now},
                created_at=now,
            )

            connection.commit()

    def list_events(
        self,
        workflow_id: str,
    ) -> list[dict[str, Any]]:
        """Return workflow events in chronological order."""

        self._ensure_exists(
            workflow_id,
            include_deleted=True,
        )

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM procurement_workflow_events
                WHERE workflow_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (workflow_id,),
            ).fetchall()

        return [
            {
                **dict(row),
                "metadata": _decode_json(
                    row["metadata_json"],
                    {},
                ),
            }
            for row in rows
        ]

    def list_audit_history(
        self,
        workflow_id: str,
    ) -> list[dict[str, Any]]:
        """Return audit records newest first."""

        self._ensure_exists(
            workflow_id,
            include_deleted=True,
        )

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM procurement_workflow_audit
                WHERE workflow_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (workflow_id,),
            ).fetchall()

        return [
            {
                **dict(row),
                "changes": _decode_json(
                    row["changes_json"],
                    {},
                ),
            }
            for row in rows
        ]

    def list_versions(
        self,
        workflow_id: str,
    ) -> list[dict[str, Any]]:
        """Return saved workflow versions newest first."""

        self._ensure_exists(
            workflow_id,
            include_deleted=True,
        )

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    workflow_id,
                    version,
                    created_by,
                    created_at
                FROM procurement_workflow_versions
                WHERE workflow_id = ?
                ORDER BY version DESC
                """,
                (workflow_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_version(
        self,
        workflow_id: str,
        version: int,
    ) -> dict[str, Any]:
        """Return one historical workflow snapshot."""

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM procurement_workflow_versions
                WHERE workflow_id = ?
                  AND version = ?
                LIMIT 1
                """,
                (
                    workflow_id,
                    version,
                ),
            ).fetchone()

        if row is None:
            raise WorkflowNotFoundError(
                f"Workflow '{workflow_id}' version {version} was not found."
            )

        record = dict(row)
        record["snapshot"] = _decode_json(
            record["snapshot_json"],
            {},
        )
        return record

    def _update_control_state(
        self,
        *,
        workflow_id: str,
        new_stage: str | None,
        new_status: str,
        actor: str,
        reason: str,
        expected_version: int,
        action: str,
    ) -> int:
        existing = self.get_workflow(
            workflow_id,
            include_archived=True,
        )

        if int(existing["version"]) != expected_version:
            raise WorkflowVersionConflictError(
                f"Workflow '{workflow_id}' has a newer version."
            )

        stage = new_stage or existing["current_stage"]
        new_version = expected_version + 1
        now = _now()

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE procurement_workflows
                SET
                    current_stage = ?,
                    status = ?,
                    version = ?,
                    updated_at = ?
                WHERE workflow_id = ?
                  AND version = ?
                  AND deleted_at IS NULL
                """,
                (
                    stage,
                    new_status,
                    new_version,
                    now,
                    workflow_id,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                raise WorkflowVersionConflictError(
                    f"Workflow '{workflow_id}' changed before update."
                )

            self._insert_audit(
                connection,
                workflow_id=workflow_id,
                action=action,
                actor=actor,
                old_stage=existing["current_stage"],
                new_stage=stage,
                old_status=existing["status"],
                new_status=new_status,
                old_version=expected_version,
                new_version=new_version,
                reason=reason,
                changes={
                    "current_stage": stage,
                    "status": new_status,
                },
                created_at=now,
            )

            connection.commit()
            return new_version

    def _list_by_statuses(
        self,
        statuses: Iterable[str],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        values = list(statuses)

        if not values:
            return []

        placeholders = ", ".join("?" for _ in values)

        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM procurement_workflows
                WHERE status IN ({placeholders})
                  AND archived_at IS NULL
                  AND deleted_at IS NULL
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                [
                    *values,
                    max(1, min(limit, 1000)),
                ],
            ).fetchall()

        return [_row_to_record(row) for row in rows]

    def _set_archive_state(
        self,
        workflow_id: str,
        *,
        archived: bool,
        actor: str,
        reason: str,
    ) -> None:
        self._ensure_exists(
            workflow_id,
            include_deleted=False,
        )
        now = _now()
        archived_at = now if archived else None

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE procurement_workflows
                SET
                    archived_at = ?,
                    monitoring_enabled = ?,
                    updated_at = ?
                WHERE workflow_id = ?
                  AND deleted_at IS NULL
                """,
                (
                    archived_at,
                    0 if archived else 1,
                    now,
                    workflow_id,
                ),
            )

            self._insert_audit(
                connection,
                workflow_id=workflow_id,
                action=(
                    "Workflow Archived"
                    if archived
                    else "Workflow Restored"
                ),
                actor=actor,
                old_stage=None,
                new_stage=None,
                old_status=None,
                new_status=None,
                old_version=None,
                new_version=None,
                reason=reason,
                changes={"archived_at": archived_at},
                created_at=now,
            )

            connection.commit()

    def _ensure_exists(
        self,
        workflow_id: str,
        *,
        include_deleted: bool = False,
    ) -> None:
        conditions = ["workflow_id = ?"]
        values: list[Any] = [workflow_id]

        if not include_deleted:
            conditions.append("deleted_at IS NULL")

        with get_connection() as connection:
            row = connection.execute(
                f"""
                SELECT workflow_id
                FROM procurement_workflows
                WHERE {' AND '.join(conditions)}
                LIMIT 1
                """,
                values,
            ).fetchone()

        if row is None:
            raise WorkflowNotFoundError(
                f"Workflow '{workflow_id}' was not found."
            )

    @staticmethod
    def _insert_new_events(
        connection: Any,
        *,
        workflow_id: str,
        events: Iterable[Any],
    ) -> None:
        for event in events:
            connection.execute(
                """
                INSERT OR IGNORE INTO procurement_workflow_events (
                    workflow_id,
                    event_id,
                    stage,
                    event_type,
                    message,
                    actor,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_id,
                    str(getattr(event, "event_id", "")),
                    _enum_value(getattr(event, "stage", "")),
                    str(getattr(event, "event_type", "")),
                    str(getattr(event, "message", "")),
                    str(getattr(event, "actor", "System")),
                    json.dumps(
                        _json_safe(
                            getattr(event, "metadata", {})
                        ),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    str(
                        getattr(
                            event,
                            "created_at",
                            _now(),
                        )
                    ),
                ),
            )

    @staticmethod
    def _insert_version(
        connection: Any,
        *,
        workflow_id: str,
        version: int,
        snapshot_json: str,
        actor: str,
        created_at: str,
    ) -> Any:
        return connection.execute(
            """
            INSERT INTO procurement_workflow_versions (
                workflow_id,
                version,
                snapshot_json,
                created_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                workflow_id,
                version,
                snapshot_json,
                actor,
                created_at,
            ),
        )

    @staticmethod
    def _insert_audit(
        connection: Any,
        *,
        workflow_id: str,
        action: str,
        actor: str,
        old_stage: str | None,
        new_stage: str | None,
        old_status: str | None,
        new_status: str | None,
        old_version: int | None,
        new_version: int | None,
        reason: str,
        changes: dict[str, Any],
        created_at: str,
    ) -> Any:
        return connection.execute(
            """
            INSERT INTO procurement_workflow_audit (
                workflow_id,
                action,
                actor,
                old_stage,
                new_stage,
                old_status,
                new_status,
                old_version,
                new_version,
                reason,
                changes_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_id,
                action,
                actor,
                old_stage,
                new_stage,
                old_status,
                new_status,
                old_version,
                new_version,
                reason,
                json.dumps(
                    _json_safe(changes),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                created_at,
            ),
        )


def _workflow_summary(
    workflow: Any,
) -> dict[str, Any]:
    requirement = getattr(workflow, "requirement", None)
    decision = getattr(workflow, "enterprise_decision", None)
    opportunity = getattr(workflow, "opportunity", None)
    risk = getattr(workflow, "risk_assessment", None)
    trust = getattr(workflow, "trust_assessment", None)
    explanation = getattr(workflow, "explanation", None)

    buyer = (
        getattr(decision, "buyer_commitment", None)
        if decision
        else None
    )
    supplier = (
        getattr(decision, "supplier_offer", None)
        if decision
        else None
    )

    return {
        "workflow_id": str(
            getattr(workflow, "workflow_id", "")
        ),
        "title": str(
            getattr(workflow, "title", "Procurement Workflow")
        ),
        "product": str(
            getattr(requirement, "product", "")
        ),
        "destination": str(
            getattr(requirement, "destination", "")
        ),
        "buyer_name": (
            getattr(buyer, "buyer_name", None)
            if buyer
            else getattr(requirement, "buyer_name", None)
        ),
        "supplier_name": (
            getattr(supplier, "supplier_name", None)
            if supplier
            else None
        ),
        "current_stage": _enum_value(
            getattr(workflow, "current_stage", "")
        ),
        "status": _enum_value(
            getattr(workflow, "status", "")
        ),
        "decision_id": (
            getattr(decision, "decision_id", None)
            if decision
            else None
        ),
        "opportunity_score": int(
            getattr(opportunity, "opportunity_score", 0)
            if opportunity
            else 0
        ),
        "risk_score": int(
            getattr(risk, "overall_score", 0)
            if risk
            else 0
        ),
        "trust_score": int(
            getattr(trust, "overall_score", 0)
            if trust
            else 0
        ),
        "confidence_score": int(
            getattr(explanation, "confidence_score", 0)
            if explanation
            else getattr(decision, "confidence_score", 0)
            if decision
            else 0
        ),
        "blocker_count": len(
            getattr(workflow, "blockers", [])
        ),
        "priority_count": len(
            getattr(workflow, "action_plan", [])
        ),
    }


def _row_to_record(
    row: Any,
) -> dict[str, Any]:
    record = dict(row)
    record["snapshot"] = _decode_json(
        record.get("snapshot_json"),
        {},
    )
    record["monitoring_enabled"] = bool(
        record.get("monitoring_enabled")
    )
    return record


def _summary_changes(
    existing: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    fields = (
        "title",
        "product",
        "destination",
        "buyer_name",
        "supplier_name",
        "current_stage",
        "status",
        "decision_id",
        "opportunity_score",
        "risk_score",
        "trust_score",
        "confidence_score",
        "blocker_count",
        "priority_count",
    )

    changes = {}

    for field_name in fields:
        old_value = existing.get(field_name)
        new_value = summary.get(field_name)

        if old_value != new_value:
            changes[field_name] = {
                "old": old_value,
                "new": new_value,
            }

    return changes


def _serialize(
    value: Any,
) -> str:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_safe(
    value: Any,
) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            field_info.name: _json_safe(
                getattr(value, field_info.name)
            )
            for field_info in dataclasses.fields(value)
        }

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _json_safe(item)
            for item in value
        ]

    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return str(value)


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


def _enum_value(
    value: Any,
) -> str:
    if isinstance(value, Enum):
        return str(value.value)

    return str(value or "")


def _now() -> str:
    return datetime.now().isoformat(
        timespec="seconds"
    )


_repository = ProcurementWorkflowRepository()


def create_workflow(
    workflow: Any,
    *,
    created_by: str = "System",
) -> int:
    return _repository.create_workflow(
        workflow,
        created_by=created_by,
    )


def get_workflow(
    workflow_id: str,
    *,
    include_archived: bool = False,
    include_deleted: bool = False,
) -> dict[str, Any]:
    return _repository.get_workflow(
        workflow_id,
        include_archived=include_archived,
        include_deleted=include_deleted,
    )


def update_workflow(
    workflow: Any,
    *,
    expected_version: int,
    actor: str = "System",
    reason: str = "",
) -> int:
    return _repository.update_workflow(
        workflow,
        expected_version=expected_version,
        actor=actor,
        reason=reason,
    )


def list_active_workflows(
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return _repository.list_active_workflows(
        limit=limit,
    )


def list_blocked_workflows(
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return _repository.list_blocked_workflows(
        limit=limit,
    )


def list_completed_workflows(
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return _repository.list_completed_workflows(
        limit=limit,
    )


def search_workflows(
    search_text: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    include_archived: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return _repository.search_workflows(
        search_text,
        status=status,
        stage=stage,
        include_archived=include_archived,
        limit=limit,
    )