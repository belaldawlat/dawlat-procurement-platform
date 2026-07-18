"""Controlled GPNI workflow state machine."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4
from database.connection import get_connection

class GPNIWorkflowStage(str, Enum):
    DEMAND_CAPTURE = "Demand Capture"
    BUYER_QUALIFICATION = "Buyer Qualification"
    SUPPLY_DISCOVERY = "Supply Discovery"
    SUPPLIER_QUALIFICATION = "Supplier Qualification"
    MATCHING = "Demand-Supply Matching"
    QUOTATION = "Quotation"
    COMMERCIAL_REVIEW = "Commercial Review"
    BUYER_APPROVAL = "Buyer Approval"
    FUNDS_CLEARANCE = "Funds Clearance"
    CONTRACT_READINESS = "Contract Readiness"
    EXECUTION_READY = "Execution Ready"
    EXECUTING = "Executing"
    COMPLETED = "Completed"
    BLOCKED = "Blocked"
    CANCELLED = "Cancelled"

@dataclass(frozen=True)
class WorkflowTransition:
    transition_id: str
    case_id: str
    previous_stage: GPNIWorkflowStage
    new_stage: GPNIWorkflowStage
    actor: str
    reason: str
    approved: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

def create_gpni_workflow_tables() -> None:
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS gpni_workflow_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL UNIQUE,
                current_stage TEXT NOT NULL,
                status TEXT NOT NULL,
                assigned_owner TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS gpni_workflow_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transition_id TEXT NOT NULL UNIQUE,
                case_id TEXT NOT NULL,
                previous_stage TEXT NOT NULL,
                new_stage TEXT NOT NULL,
                actor TEXT NOT NULL,
                reason TEXT NOT NULL,
                approved INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)
        connection.commit()

class GPNIWorkflowService:
    ALLOWED = {
        GPNIWorkflowStage.DEMAND_CAPTURE: {GPNIWorkflowStage.BUYER_QUALIFICATION, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.BUYER_QUALIFICATION: {GPNIWorkflowStage.SUPPLY_DISCOVERY, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.SUPPLY_DISCOVERY: {GPNIWorkflowStage.SUPPLIER_QUALIFICATION, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.SUPPLIER_QUALIFICATION: {GPNIWorkflowStage.MATCHING, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.MATCHING: {GPNIWorkflowStage.QUOTATION, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.QUOTATION: {GPNIWorkflowStage.COMMERCIAL_REVIEW, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.COMMERCIAL_REVIEW: {GPNIWorkflowStage.BUYER_APPROVAL, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.BUYER_APPROVAL: {GPNIWorkflowStage.FUNDS_CLEARANCE, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.FUNDS_CLEARANCE: {GPNIWorkflowStage.CONTRACT_READINESS, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.CONTRACT_READINESS: {GPNIWorkflowStage.EXECUTION_READY, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.EXECUTION_READY: {GPNIWorkflowStage.EXECUTING, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.EXECUTING: {GPNIWorkflowStage.COMPLETED, GPNIWorkflowStage.BLOCKED, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.BLOCKED: {GPNIWorkflowStage.BUYER_QUALIFICATION, GPNIWorkflowStage.SUPPLIER_QUALIFICATION, GPNIWorkflowStage.MATCHING, GPNIWorkflowStage.COMMERCIAL_REVIEW, GPNIWorkflowStage.FUNDS_CLEARANCE, GPNIWorkflowStage.CONTRACT_READINESS, GPNIWorkflowStage.CANCELLED},
        GPNIWorkflowStage.COMPLETED: set(),
        GPNIWorkflowStage.CANCELLED: set(),
    }

    def __init__(self) -> None:
        create_gpni_workflow_tables()

    def create_case(self, case_id: str, *, assigned_owner: str | None = None,
                    metadata: dict[str, Any] | None = None) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with get_connection() as connection:
            connection.execute("""
                INSERT OR IGNORE INTO gpni_workflow_cases (
                    case_id, current_stage, status, assigned_owner,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                case_id, GPNIWorkflowStage.DEMAND_CAPTURE.value,
                "Active", assigned_owner,
                json.dumps(metadata or {}, ensure_ascii=False),
                now, now,
            ))
            connection.commit()

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute("""
                SELECT * FROM gpni_workflow_cases
                WHERE case_id = ? LIMIT 1
            """, (case_id,)).fetchone()
        return dict(row) if row else None

    def transition(self, *, case_id: str, new_stage: GPNIWorkflowStage,
                   actor: str, reason: str, approved: bool,
                   metadata: dict[str, Any] | None = None) -> WorkflowTransition:
        current = self.get_case(case_id)
        if current is None:
            raise LookupError(f"GPNI case '{case_id}' was not found.")
        previous_stage = GPNIWorkflowStage(current["current_stage"])
        if new_stage not in self.ALLOWED.get(previous_stage, set()):
            raise ValueError(
                f"Transition from {previous_stage.value} to "
                f"{new_stage.value} is not allowed."
            )
        if not approved:
            raise PermissionError("Workflow transition requires explicit approval.")
        transition = WorkflowTransition(
            transition_id=f"GPT-{uuid4().hex[:16].upper()}",
            case_id=case_id,
            previous_stage=previous_stage,
            new_stage=new_stage,
            actor=actor,
            reason=reason,
            approved=True,
            metadata=metadata or {},
        )
        status = (
            "Completed" if new_stage == GPNIWorkflowStage.COMPLETED
            else "Cancelled" if new_stage == GPNIWorkflowStage.CANCELLED
            else "Blocked" if new_stage == GPNIWorkflowStage.BLOCKED
            else "Active"
        )
        with get_connection() as connection:
            connection.execute("""
                UPDATE gpni_workflow_cases
                SET current_stage = ?, status = ?, updated_at = ?
                WHERE case_id = ?
            """, (new_stage.value, status, transition.created_at, case_id))
            connection.execute("""
                INSERT INTO gpni_workflow_transitions (
                    transition_id, case_id, previous_stage, new_stage,
                    actor, reason, approved, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transition.transition_id, transition.case_id,
                transition.previous_stage.value, transition.new_stage.value,
                transition.actor, transition.reason, 1,
                json.dumps(transition.metadata, ensure_ascii=False, sort_keys=True),
                transition.created_at,
            ))
            connection.commit()
        return transition

_service = GPNIWorkflowService()

def get_gpni_workflow_service() -> GPNIWorkflowService:
    return _service