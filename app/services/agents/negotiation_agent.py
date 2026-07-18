"""Negotiation intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class NegotiationAgent:
    name = "Negotiation Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        negotiation = payload.get("negotiation", {})
        findings: list[AgentFinding] = []

        if negotiation.get("prohibited_commitment_detected"):
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Negotiation",
                title="Prohibited commitment detected",
                description="Proposed terms exceed authorised negotiation limits.",
                severity=AgentSeverity.CRITICAL,
                confidence_score=100,
                blocking=True,
                recommended_action="Remove the prohibited commitment.",
            ))

        if not negotiation.get("walk_away_position_defined"):
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Negotiation",
                title="Walk-away position undefined",
                description="Negotiation limits are not fully defined.",
                severity=AgentSeverity.HIGH,
                confidence_score=90,
                blocking=True,
                recommended_action="Define target and walk-away positions.",
            ))

        return tuple(findings)

_agent = NegotiationAgent()

def get_negotiation_agent() -> NegotiationAgent:
    return _agent