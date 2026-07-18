"""Immutable GPNI audit service."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4
from database.connection import get_connection

@dataclass(frozen=True)
class GPNIAuditEntry:
    audit_id: str
    case_id: str
    event_name: str
    actor: str
    stage: str
    decision: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

def create_gpni_audit_tables() -> None:
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS gpni_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id TEXT NOT NULL UNIQUE,
                case_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                actor TEXT NOT NULL,
                stage TEXT NOT NULL,
                decision TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_gpni_audit_case
            ON gpni_audit_log(case_id, created_at DESC)
        """)
        connection.commit()

class GPNIAuditService:
    def __init__(self) -> None:
        create_gpni_audit_tables()

    def record(self, *, case_id: str, event_name: str, actor: str,
               stage: str, decision: str,
               details: dict[str, Any] | None = None) -> GPNIAuditEntry:
        entry = GPNIAuditEntry(
            audit_id=f"GPA-{uuid4().hex[:16].upper()}",
            case_id=case_id,
            event_name=event_name,
            actor=actor,
            stage=stage,
            decision=decision,
            details=details or {},
        )
        with get_connection() as connection:
            connection.execute("""
                INSERT INTO gpni_audit_log (
                    audit_id, case_id, event_name, actor, stage,
                    decision, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.audit_id, entry.case_id, entry.event_name,
                entry.actor, entry.stage, entry.decision,
                json.dumps(entry.details, ensure_ascii=False, sort_keys=True),
                entry.created_at,
            ))
            connection.commit()
        return entry

    def list_for_case(self, case_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute("""
                SELECT * FROM gpni_audit_log
                WHERE case_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (case_id, max(1, min(limit, 1000)))).fetchall()
        return [dict(row) for row in rows]

_service = GPNIAuditService()

def get_gpni_audit_service() -> GPNIAuditService:
    return _service