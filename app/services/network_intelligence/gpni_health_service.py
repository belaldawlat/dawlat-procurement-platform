"""Health diagnostics for GPNI."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from database.connection import get_connection

@dataclass(frozen=True)
class GPNIHealthResult:
    healthy: bool
    database_ready: bool
    engines_ready: bool
    workflow_ready: bool
    audit_ready: bool
    failures: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

class GPNIHealthService:
    REQUIRED_TABLES = {
        "global_demand_records",
        "global_supply_records",
        "gpni_workflow_cases",
        "gpni_workflow_transitions",
        "gpni_audit_log",
    }

    def check(self) -> GPNIHealthResult:
        failures: list[str] = []
        table_names: set[str] = set()
        database_ready = False
        engines_ready = False
        try:
            with get_connection() as connection:
                rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            table_names = {str(row["name"]) for row in rows}
            database_ready = True
        except Exception as error:
            failures.append(f"Database health check failed: {error}")
        missing = self.REQUIRED_TABLES - table_names
        if missing:
            failures.append("Missing GPNI tables: " + ", ".join(sorted(missing)))
        try:
            from services.network_intelligence import get_procurement_network_engine
            engines_ready = get_procurement_network_engine() is not None
        except Exception as error:
            failures.append(f"GPNI engine import failed: {error}")
        workflow_ready = {
            "gpni_workflow_cases", "gpni_workflow_transitions"
        }.issubset(table_names)
        audit_ready = "gpni_audit_log" in table_names
        healthy = (
            database_ready and engines_ready and workflow_ready
            and audit_ready and not failures
        )
        return GPNIHealthResult(
            healthy=healthy,
            database_ready=database_ready,
            engines_ready=engines_ready,
            workflow_ready=workflow_ready,
            audit_ready=audit_ready,
            failures=tuple(failures),
            details={"tables_found": sorted(table_names)},
        )

_service = GPNIHealthService()

def get_gpni_health_service() -> GPNIHealthService:
    return _service