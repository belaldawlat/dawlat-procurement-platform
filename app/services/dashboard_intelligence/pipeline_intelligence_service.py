"""Procurement pipeline intelligence and bottleneck detection."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable

class PipelineStatus(str, Enum):
    HEALTHY = "Healthy"
    ATTENTION = "Attention"
    BLOCKED = "Blocked"
    OVERDUE = "Overdue"

@dataclass(frozen=True)
class PipelineCase:
    case_id: str
    stage: str
    value: float
    owner: str
    created_at: str
    updated_at: str
    deadline_date: str | None
    approval_pending: bool
    quotation_expired: bool
    documents_complete: bool
    landed_cost_validated: bool
    blocked: bool
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PipelineCaseAssessment:
    case_id: str
    stage: str
    status: PipelineStatus
    age_days: int
    days_since_update: int
    days_to_deadline: int | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    next_action: str

@dataclass(frozen=True)
class PipelineSnapshot:
    total_cases: int
    total_pipeline_value: float
    healthy_cases: int
    attention_cases: int
    blocked_cases: int
    overdue_cases: int
    stage_counts: dict[str, int]
    stage_values: dict[str, float]
    cases: tuple[PipelineCaseAssessment, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

class PipelineIntelligenceService:
    def assess_case(
        self,
        item: PipelineCase,
    ) -> PipelineCaseAssessment:
        today = date.today()
        created = _parse_date(item.created_at) or today
        updated = _parse_date(item.updated_at) or created
        deadline = _parse_date(item.deadline_date)

        age_days = max(0, (today - created).days)
        days_since_update = max(0, (today - updated).days)
        days_to_deadline = (
            (deadline - today).days
            if deadline is not None
            else None
        )

        blockers: list[str] = []
        warnings: list[str] = []

        if item.blocked:
            blockers.append("Case is explicitly blocked.")
        if item.quotation_expired:
            blockers.append("Supplier quotation has expired.")
        if not item.documents_complete:
            blockers.append("Required documents are incomplete.")
        if not item.landed_cost_validated:
            blockers.append("Landed cost is not validated.")
        if item.approval_pending:
            warnings.append("Required approval is pending.")
        if days_since_update >= 7:
            warnings.append(
                "Case has not been updated for seven or more days."
            )

        if days_to_deadline is not None and days_to_deadline < 0:
            status = PipelineStatus.OVERDUE
        elif blockers:
            status = PipelineStatus.BLOCKED
        elif warnings or (
            days_to_deadline is not None
            and days_to_deadline <= 3
        ):
            status = PipelineStatus.ATTENTION
        else:
            status = PipelineStatus.HEALTHY

        next_action = (
            "Resolve blockers immediately."
            if blockers
            else "Complete pending approval."
            if item.approval_pending
            else "Refresh owner update."
            if days_since_update >= 7
            else "Continue workflow."
        )

        return PipelineCaseAssessment(
            case_id=item.case_id,
            stage=item.stage,
            status=status,
            age_days=age_days,
            days_since_update=days_since_update,
            days_to_deadline=days_to_deadline,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            next_action=next_action,
        )

    def snapshot(
        self,
        cases: Iterable[PipelineCase],
    ) -> PipelineSnapshot:
        records = list(cases)
        assessments = tuple(
            self.assess_case(item)
            for item in records
        )
        stage_counts: dict[str, int] = {}
        stage_values: dict[str, float] = {}

        for item in records:
            stage_counts[item.stage] = stage_counts.get(item.stage, 0) + 1
            stage_values[item.stage] = stage_values.get(item.stage, 0.0) + item.value

        return PipelineSnapshot(
            total_cases=len(records),
            total_pipeline_value=round(
                sum(item.value for item in records),
                2,
            ),
            healthy_cases=sum(
                1
                for item in assessments
                if item.status == PipelineStatus.HEALTHY
            ),
            attention_cases=sum(
                1
                for item in assessments
                if item.status == PipelineStatus.ATTENTION
            ),
            blocked_cases=sum(
                1
                for item in assessments
                if item.status == PipelineStatus.BLOCKED
            ),
            overdue_cases=sum(
                1
                for item in assessments
                if item.status == PipelineStatus.OVERDUE
            ),
            stage_counts=stage_counts,
            stage_values={
                key: round(value, 2)
                for key, value in stage_values.items()
            },
            cases=tuple(
                sorted(
                    assessments,
                    key=lambda item: (
                        item.status == PipelineStatus.HEALTHY,
                        item.days_to_deadline
                        if item.days_to_deadline is not None
                        else 999999,
                        -item.days_since_update,
                    ),
                )
            ),
        )

def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None

_service = PipelineIntelligenceService()

def get_pipeline_intelligence_service() -> PipelineIntelligenceService:
    return _service