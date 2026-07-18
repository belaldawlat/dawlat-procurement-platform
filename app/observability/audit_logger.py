"""Tamper-evident audit logging for enterprise activity."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.observability.redaction import redact_mapping


class AuditOutcome(str, Enum):
    """Supported audit event outcomes."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit event."""

    action: str
    resource_type: str
    outcome: AuditOutcome

    actor_id: str = ""
    actor_email: str = ""
    actor_role: str = ""
    resource_id: str = ""

    request_id: str = ""
    correlation_id: str = ""
    source_ip: str = ""

    details: dict[str, Any] = field(default_factory=dict)

    event_id: str = field(
        default_factory=lambda: uuid4().hex
    )
    occurred_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class AuditLogger:
    """Append tamper-evident audit events to a JSONL ledger."""

    def __init__(
        self,
        path: str | Path = "logs/audit.jsonl",
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        """Return the audit log path."""

        return self._path

    def record(self, event: AuditEvent) -> dict[str, Any]:
        """Append an audit event and return the stored record."""

        with self._lock:
            previous_hash = self._read_last_hash()

            event_payload = asdict(event)
            event_payload["outcome"] = event.outcome.value
            event_payload["details"] = redact_mapping(
                event.details
            )

            canonical = json.dumps(
                event_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )

            record_hash = hashlib.sha256(
                (
                    previous_hash
                    + canonical
                ).encode("utf-8")
            ).hexdigest()

            stored_record = {
                **event_payload,
                "previous_hash": previous_hash,
                "record_hash": record_hash,
            }

            with self._path.open(
                "a",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(
                    json.dumps(
                        stored_record,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                )
                handle.write("\n")

            return stored_record

    def verify_integrity(self) -> bool:
        """Verify the complete audit hash chain."""

        if not self._path.exists():
            return True

        previous_hash = ""

        with self._path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            for line in handle:
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    return False

                stored_hash = str(
                    record.pop("record_hash", "")
                )
                stored_previous_hash = str(
                    record.pop("previous_hash", "")
                )

                if stored_previous_hash != previous_hash:
                    return False

                canonical = json.dumps(
                    record,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )

                expected_hash = hashlib.sha256(
                    (
                        previous_hash
                        + canonical
                    ).encode("utf-8")
                ).hexdigest()

                if stored_hash != expected_hash:
                    return False

                previous_hash = stored_hash

        return True

    def _read_last_hash(self) -> str:
        """Return the final record hash in the ledger."""

        if not self._path.exists():
            return ""

        last_record: dict[str, Any] | None = None

        with self._path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            for line in handle:
                if line.strip():
                    last_record = json.loads(line)

        if not last_record:
            return ""

        return str(last_record.get("record_hash") or "")


_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Return the shared audit logger."""

    return _audit_logger