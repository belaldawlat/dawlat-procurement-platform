"""Buyer intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class BuyerAgent:
    name = "Buyer Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        buyer = payload.get("buyer", {})
        findings: list[AgentFinding] = []

        checks = (
            (
                buyer.get("verified"),
                "Buyer verification incomplete",
                "Buyer identity and authority are not fully verified.",
                "Complete buyer verification.",
            ),
            (
                buyer.get("requirements_confirmed"),
                "Buyer requirements incomplete",
                "Final product specifications or quantity are not confirmed.",
                "Obtain signed buyer requirements.",
            ),
            (
                buyer.get("commercial_commitment"),
                "Commercial commitment missing",
                "Buyer has not provided sufficient commercial commitment.",
                "Confirm quotation acceptance process and purchase intent.",
            ),
        )

        for passed, title, description, action in checks:
            if not passed:
                findings.append(AgentFinding(
                    agent_name=self.name,
                    category="Buyer",
                    title=title,
                    description=description,
                    severity=AgentSeverity.HIGH,
                    confidence_score=95,
                    blocking=True,
                    recommended_action=action,
                ))

        if buyer.get("payment_reliability_score", 0) < 60:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Buyer",
                title="Payment reliability weak",
                description="Buyer payment reliability is below threshold.",
                severity=AgentSeverity.CRITICAL,
                confidence_score=90,
                blocking=True,
                recommended_action="Require cleared funds or approved credit protection.",
            ))

        return tuple(findings)

_agent = BuyerAgent()

def get_buyer_agent() -> BuyerAgent:
    return _agent