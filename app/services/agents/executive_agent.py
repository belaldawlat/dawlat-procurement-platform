"""Executive intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class ExecutiveAgent:
    name = "Executive Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        executive = payload.get("executive", {})
        score = int(executive.get("strategic_score", 0))
        exposure = float(executive.get("cash_exposure", 0))
        limit = float(executive.get("cash_exposure_limit", 0))
        findings: list[AgentFinding] = []

        if score >= 75:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Executive",
                title="Strategically attractive case",
                description="The case has strong strategic value.",
                severity=AgentSeverity.INFO,
                confidence_score=80,
                recommended_action="Escalate for executive commercial review.",
            ))

        if limit > 0 and exposure > limit:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Executive",
                title="Cash exposure exceeds limit",
                description="Projected cash exposure exceeds the approved limit.",
                severity=AgentSeverity.CRITICAL,
                confidence_score=95,
                blocking=True,
                recommended_action="Reduce exposure or obtain executive approval.",
            ))

        return tuple(findings)

_agent = ExecutiveAgent()

def get_executive_agent() -> ExecutiveAgent:
    return _agent