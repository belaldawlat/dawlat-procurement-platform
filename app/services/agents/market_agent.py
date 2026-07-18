"""Market intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class MarketAgent:
    name = "Market Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        market = payload.get("market", {})
        findings: list[AgentFinding] = []

        demand_score = int(market.get("demand_score", 0))
        opportunity_score = int(market.get("opportunity_score", 0))

        if demand_score >= 75 and opportunity_score >= 70:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Market",
                title="Strong market opportunity",
                description="Verified demand and opportunity indicators are strong.",
                severity=AgentSeverity.INFO,
                confidence_score=int(market.get("confidence_score", 70)),
                recommended_action="Proceed to controlled commercial validation.",
            ))

        if market.get("shortage_risk", 0) >= 70:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Market",
                title="Market shortage risk",
                description="Supply shortage risk may affect availability or pricing.",
                severity=AgentSeverity.HIGH,
                confidence_score=80,
                recommended_action="Secure backup supply and refresh quotation validity.",
            ))

        return tuple(findings)

_agent = MarketAgent()

def get_market_agent() -> MarketAgent:
    return _agent