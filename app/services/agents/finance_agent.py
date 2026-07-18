"""Finance intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class FinanceAgent:
    name = "Finance Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        finance = payload.get("finance", {})
        findings: list[AgentFinding] = []

        if not finance.get("buyer_funds_cleared"):
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Finance",
                title="Buyer funds not cleared",
                description="Verified cleared buyer funds are not available.",
                severity=AgentSeverity.CRITICAL,
                confidence_score=100,
                blocking=True,
                recommended_action="Do not commit or pay the supplier.",
            ))

        margin = float(finance.get("margin_percent", 0))
        minimum = float(finance.get("minimum_margin_percent", 15))

        if margin < minimum:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Finance",
                title="Protected margin breached",
                description="Projected margin is below the protected minimum.",
                severity=AgentSeverity.CRITICAL,
                confidence_score=95,
                blocking=True,
                recommended_action="Renegotiate costs or buyer pricing.",
            ))

        if finance.get("currency_risk", 0) >= 60:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Finance",
                title="Currency exposure elevated",
                description="Foreign-exchange exposure may materially affect margin.",
                severity=AgentSeverity.HIGH,
                confidence_score=80,
                recommended_action="Refresh pricing validity and FX protection.",
            ))

        return tuple(findings)

_agent = FinanceAgent()

def get_finance_agent() -> FinanceAgent:
    return _agent