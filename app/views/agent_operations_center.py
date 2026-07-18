"""AI Agent Operations Center view."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable

import pandas as pd
import streamlit as st


PAGE_TITLE = "Agent Operations Center"


class AgentOperationalState(str, Enum):
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    FAILED = "Failed"
    PAUSED = "Paused"


@dataclass(frozen=True)
class AgentOperationRecord:
    agent_id: str
    agent_name: str
    agent_type: str
    state: AgentOperationalState
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    confidence_score: int
    disagreement_count: int
    pending_recommendations: int
    pending_approvals: int
    human_overrides: int
    average_latency_ms: float
    last_activity_at: str | None
    current_task: str | None
    evidence_count: int = 0


@dataclass(frozen=True)
class AgentOperationsSnapshot:
    total_agents: int
    healthy_agents: int
    degraded_agents: int
    failed_agents: int
    paused_agents: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    average_confidence: int
    pending_recommendations: int
    pending_approvals: int
    disagreements: int
    human_overrides: int
    records: tuple[AgentOperationRecord, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


def build_snapshot(
    agents: Iterable[AgentOperationRecord],
) -> AgentOperationsSnapshot:
    """Build an immutable agent operations snapshot."""

    records = tuple(agents)

    average_confidence = (
        round(
            sum(
                max(0, min(100, item.confidence_score))
                for item in records
            )
            / len(records)
        )
        if records
        else 0
    )

    return AgentOperationsSnapshot(
        total_agents=len(records),
        healthy_agents=sum(
            1
            for item in records
            if item.state == AgentOperationalState.HEALTHY
        ),
        degraded_agents=sum(
            1
            for item in records
            if item.state == AgentOperationalState.DEGRADED
        ),
        failed_agents=sum(
            1
            for item in records
            if item.state == AgentOperationalState.FAILED
        ),
        paused_agents=sum(
            1
            for item in records
            if item.state == AgentOperationalState.PAUSED
        ),
        running_tasks=sum(item.running_tasks for item in records),
        completed_tasks=sum(item.completed_tasks for item in records),
        failed_tasks=sum(item.failed_tasks for item in records),
        average_confidence=average_confidence,
        pending_recommendations=sum(
            item.pending_recommendations
            for item in records
        ),
        pending_approvals=sum(
            item.pending_approvals
            for item in records
        ),
        disagreements=sum(
            item.disagreement_count
            for item in records
        ),
        human_overrides=sum(
            item.human_overrides
            for item in records
        ),
        records=records,
    )


def render(
    agents: tuple[AgentOperationRecord, ...] = (),
) -> None:
    """Render enterprise AI agent health and governance operations."""

    st.title(PAGE_TITLE)
    st.caption(
        "Operational supervision for autonomous and specialist AI agents, "
        "including health, confidence, approvals, disagreement and audit."
    )

    snapshot = build_snapshot(agents)

    _render_metrics(snapshot)
    _render_agent_health(snapshot)
    _render_task_operations(snapshot)
    _render_governance_queue(snapshot)
    _render_agent_table(snapshot)
    _render_audit(snapshot)


def _render_metrics(
    snapshot: AgentOperationsSnapshot,
) -> None:
    first = st.columns(4)
    first[0].metric(
        "Total Agents",
        snapshot.total_agents,
    )
    first[1].metric(
        "Healthy",
        snapshot.healthy_agents,
    )
    first[2].metric(
        "Degraded",
        snapshot.degraded_agents,
    )
    first[3].metric(
        "Failed",
        snapshot.failed_agents,
    )

    second = st.columns(4)
    second[0].metric(
        "Running Tasks",
        snapshot.running_tasks,
    )
    second[1].metric(
        "Average Confidence",
        f"{snapshot.average_confidence}/100",
    )
    second[2].metric(
        "Pending Approvals",
        snapshot.pending_approvals,
    )
    second[3].metric(
        "Human Overrides",
        snapshot.human_overrides,
    )


def _render_agent_health(
    snapshot: AgentOperationsSnapshot,
) -> None:
    st.subheader("Agent Health")

    health_df = pd.DataFrame(
        {
            "Agents": {
                "Healthy": snapshot.healthy_agents,
                "Degraded": snapshot.degraded_agents,
                "Failed": snapshot.failed_agents,
                "Paused": snapshot.paused_agents,
            }
        }
    )

    st.bar_chart(
        health_df,
        use_container_width=True,
    )


def _render_task_operations(
    snapshot: AgentOperationsSnapshot,
) -> None:
    st.subheader("Task Operations")

    task_df = pd.DataFrame(
        {
            "Tasks": {
                "Running": snapshot.running_tasks,
                "Completed": snapshot.completed_tasks,
                "Failed": snapshot.failed_tasks,
                "Pending Recommendations": (
                    snapshot.pending_recommendations
                ),
            }
        }
    )

    st.bar_chart(
        task_df,
        use_container_width=True,
    )


def _render_governance_queue(
    snapshot: AgentOperationsSnapshot,
) -> None:
    st.subheader("AI Governance Queue")

    metrics = st.columns(3)
    metrics[0].metric(
        "Pending Recommendations",
        snapshot.pending_recommendations,
    )
    metrics[1].metric(
        "Agent Disagreements",
        snapshot.disagreements,
    )
    metrics[2].metric(
        "Pending Human Approvals",
        snapshot.pending_approvals,
    )

    if snapshot.failed_agents > 0:
        st.error(
            "One or more agents have failed and require operational review."
        )
    elif snapshot.degraded_agents > 0:
        st.warning(
            "One or more agents are degraded and should be monitored."
        )
    else:
        st.success("All reported agents are operationally healthy.")


def _render_agent_table(
    snapshot: AgentOperationsSnapshot,
) -> None:
    st.subheader("Agent Registry")

    if not snapshot.records:
        st.info("No AI agent telemetry was supplied.")
        return

    dataframe = pd.DataFrame(
        [
            {
                "Agent": item.agent_name,
                "Type": item.agent_type,
                "State": item.state.value,
                "Current Task": item.current_task or "-",
                "Running": item.running_tasks,
                "Completed": item.completed_tasks,
                "Failed": item.failed_tasks,
                "Confidence": item.confidence_score,
                "Disagreements": item.disagreement_count,
                "Pending Approvals": item.pending_approvals,
                "Human Overrides": item.human_overrides,
                "Latency ms": item.average_latency_ms,
                "Evidence": item.evidence_count,
                "Last Activity": item.last_activity_at or "-",
            }
            for item in snapshot.records
        ]
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )


def _render_audit(
    snapshot: AgentOperationsSnapshot,
) -> None:
    with st.expander("Agent audit metadata"):
        st.json(
            {
                "generated_at": snapshot.generated_at,
                "total_agents": snapshot.total_agents,
                "completed_tasks": snapshot.completed_tasks,
                "failed_tasks": snapshot.failed_tasks,
                "disagreements": snapshot.disagreements,
                "human_overrides": snapshot.human_overrides,
            }
        )

    st.caption(
        "The Agent Operations Center is supervisory and read-only. "
        "Recommendations requiring commercial, payment or compliance action "
        "must pass through human approval and the enterprise audit pipeline."
    )


if __name__ == "__main__":
    render()