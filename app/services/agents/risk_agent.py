"""Enterprise risk intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class RiskAgent:
    name = "Risk Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        risk = payload.get("risk", {})
        score = int(risk.get("overall_score", 0))
        compound = int(risk.get("compound_score", 0))
        findings: list[AgentFinding] = []

        if score >= 80 or compound >= 80:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Risk",
                title="Critical enterprise risk",
                description="Overall or compound risk exceeds the execution threshold.",
                severity=AgentSeverity.CRITICAL,
                confidence_score=90,
                blocking=True,
                recommended_action="Stop progression and implement risk mitigation.",
            ))
        elif score >= 60 or compound >= 60:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Risk",
                title="Enhanced risk review required",
                description="Risk exposure requires senior review.",
                severity=AgentSeverity.HIGH,
                confidence_score=85,
                recommended_action="Complete enhanced risk review.",
            ))

        return tuple(findings)

_agent = RiskAgent()

def get_risk_agent() -> RiskAgent:
    return _agent