"""Audit trail for Package T enterprise decisions."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
import hashlib
import json
import threading
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping
from app.orchestration.exceptions import WorkflowNotFoundError


def utc_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EnterpriseDecisionAuditRecord:
    """Immutable audit record for one decision lifecycle event."""

    decision_id: str
    case_id: str
    action: str
    actor_id: str
    payload: dict[str, Any]
    audit_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    occurred_at: str = dataclass_field(default_factory=utc_timestamp)
    previous_hash: str = ""
    record_hash: str = ""

    def __post_init__(self) -> None:
        if not str(self.audit_id or "").strip():
            raise ValueError("Decision audit ID is required.")
        if not str(self.decision_id or "").strip():
            raise ValueError("Decision audit decision ID is required.")
        if not str(self.case_id or "").strip():
            raise ValueError("Decision audit case ID is required.")
        if not str(self.action or "").strip():
            raise ValueError("Decision audit action is required.")
        if not str(self.actor_id or "").strip():
            raise ValueError("Decision audit actor ID is required.")

        safe_payload = redact_mapping(self.payload)

        object.__setattr__(self, "audit_id", str(self.audit_id).strip())
        object.__setattr__(self, "decision_id", str(self.decision_id).strip())
        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "action", str(self.action).strip())
        object.__setattr__(self, "actor_id", str(self.actor_id).strip())
        object.__setattr__(self, "previous_hash", str(self.previous_hash or "").strip())
        object.__setattr__(self, "payload", safe_payload)

        expected_hash = self.record_hash or self.calculate_hash()

        object.__setattr__(
            self,
            "record_hash",
            str(expected_hash).strip(),
        )

    def calculate_hash(self) -> str:
        """Calculate a deterministic SHA-256 record hash."""

        material = {
            "audit_id": self.audit_id,
            "decision_id": self.decision_id,
            "case_id": self.case_id,
            "action": self.action,
            "actor_id": self.actor_id,
            "payload": redact_mapping(self.payload),
            "occurred_at": self.occurred_at,
            "previous_hash": self.previous_hash,
        }

        encoded = json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")

        return hashlib.sha256(encoded).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        """Return a safe serialisable audit record."""

        return {
            "audit_id": self.audit_id,
            "decision_id": self.decision_id,
            "case_id": self.case_id,
            "action": self.action,
            "actor_id": self.actor_id,
            "payload": redact_mapping(self.payload),
            "occurred_at": self.occurred_at,
            "previous_hash": self.previous_hash,
            "record_hash": self.record_hash,
        }


class EnterpriseDecisionAuditTrail:
    """Thread-safe append-only decision audit trail."""

    def __init__(self) -> None:
        self._records: list[EnterpriseDecisionAuditRecord] = []
        self._lock = threading.RLock()

    def append(
        self,
        *,
        decision_id: str,
        case_id: str,
        action: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> EnterpriseDecisionAuditRecord:
        """Append one audit record to the chain."""

        with self._lock:
            previous_hash = (
                self._records[-1].record_hash
                if self._records
                else ""
            )

            record = EnterpriseDecisionAuditRecord(
                decision_id=decision_id,
                case_id=case_id,
                action=action,
                actor_id=actor_id,
                payload=payload,
                previous_hash=previous_hash,
            )
            self._records.append(record)

        return record

    def get(
        self,
        audit_id: str,
    ) -> EnterpriseDecisionAuditRecord:
        """Return one audit record by ID."""

        cleaned_id = str(audit_id or "").strip()

        if not cleaned_id:
            raise ValueError("Decision audit ID is required.")

        with self._lock:
            for record in self._records:
                if record.audit_id == cleaned_id:
                    return record

        raise WorkflowNotFoundError(
            technical_message=(
                f"Decision audit record {cleaned_id!r} was not found."
            )
        )

    def list_records(
        self,
        *,
        decision_id: str | None = None,
        case_id: str | None = None,
    ) -> tuple[EnterpriseDecisionAuditRecord, ...]:
        """Return filtered audit records in append order."""

        cleaned_decision_id = (
            str(decision_id).strip()
            if decision_id is not None
            else None
        )
        cleaned_case_id = (
            str(case_id).strip()
            if case_id is not None
            else None
        )

        with self._lock:
            return tuple(
                record
                for record in self._records
                if (
                    cleaned_decision_id is None
                    or record.decision_id == cleaned_decision_id
                )
                and (
                    cleaned_case_id is None
                    or record.case_id == cleaned_case_id
                )
            )

    def verify_integrity(self) -> bool:
        """Verify the entire audit hash chain."""

        with self._lock:
            previous_hash = ""

            for record in self._records:
                if record.previous_hash != previous_hash:
                    return False
                if record.record_hash != record.calculate_hash():
                    return False

                previous_hash = record.record_hash

        return True

    def clear(self) -> None:
        """Remove all audit records."""

        with self._lock:
            self._records.clear()


_default_enterprise_decision_audit_trail = (
    EnterpriseDecisionAuditTrail()
)


def get_enterprise_decision_audit_trail(
) -> EnterpriseDecisionAuditTrail:
    """Return the process-local default decision audit trail."""

    return _default_enterprise_decision_audit_trail