"""Governed coordination primitives for enterprise AI agents."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

class AgentSeverity(str, Enum):
    INFO = "Info"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

@dataclass(frozen=True)
class AgentFinding:
    agent_name: str
    category: str
    title: str
    description: str
    severity: AgentSeverity
    confidence_score: int
    blocking: bool = False
    recommended_action: str = ""
    evidence: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class AgentReport:
    case_id: str
    findings: tuple[AgentFinding, ...]
    overall_confidence_score: int
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    execution_allowed: bool
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

class EnterpriseAgent(Protocol):
    name: str
    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        ...

class AgentCoordinator:
    def __init__(self) -> None:
        self._agents: dict[str, EnterpriseAgent] = {}

    def register(self, agent: EnterpriseAgent) -> None:
        self._agents[agent.name] = agent

    def list_agents(self) -> tuple[str, ...]:
        return tuple(sorted(self._agents))

    def run(
        self,
        *,
        case_id: str,
        payload: dict[str, Any],
        selected_agents: tuple[str, ...] | None = None,
    ) -> AgentReport:
        names = selected_agents if selected_agents is not None else tuple(self._agents)
        findings: list[AgentFinding] = []

        for name in names:
            agent = self._agents.get(name)
            if agent is None:
                findings.append(
                    AgentFinding(
                        agent_name="Agent Coordinator",
                        category="Platform",
                        title="Agent unavailable",
                        description=f"Agent '{name}' is not registered.",
                        severity=AgentSeverity.HIGH,
                        confidence_score=100,
                        blocking=True,
                        recommended_action="Register or restore the missing agent.",
                    )
                )
                continue
            findings.extend(agent.analyse(case_id, payload))

        blockers = tuple(dict.fromkeys(
            finding.description for finding in findings if finding.blocking
        ))
        warnings = tuple(dict.fromkeys(
            finding.description
            for finding in findings
            if not finding.blocking
            and finding.severity in {
                AgentSeverity.MEDIUM,
                AgentSeverity.HIGH,
                AgentSeverity.CRITICAL,
            }
        ))
        actions = tuple(dict.fromkeys(
            finding.recommended_action
            for finding in findings
            if finding.recommended_action
        ))
        confidence = (
            round(sum(
                max(0, min(100, finding.confidence_score))
                for finding in findings
            ) / len(findings))
            if findings else 0
        )

        return AgentReport(
            case_id=case_id,
            findings=tuple(findings),
            overall_confidence_score=confidence,
            blockers=blockers,
            warnings=warnings,
            recommended_actions=actions,
            execution_allowed=False,
        )

_coordinator = AgentCoordinator()

def get_agent_coordinator() -> AgentCoordinator:
    return _coordinator