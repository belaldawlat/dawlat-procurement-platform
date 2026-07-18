"""Procurement workflow agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class ProcurementAgent:
    name = "Procurement Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        procurement = payload.get("procurement", {})
        findings: list[AgentFinding] = []

        if int(procurement.get("quotation_count", 0)) < 2:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Procurement",
                title="Insufficient quotation competition",
                description="Fewer than two comparable supplier quotations are available.",
                severity=AgentSeverity.MEDIUM,
                confidence_score=95,
                recommended_action="Obtain additional comparable quotations.",
            ))

        if not procurement.get("landed_cost_validated"):
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Procurement",
                title="Landed cost not validated",
                description="The complete landed cost has not been independently validated.",
                severity=AgentSeverity.CRITICAL,
                confidence_score=95,
                blocking=True,
                recommended_action="Complete landed-cost validation.",
            ))

        if not procurement.get("quotation_comparison_complete"):
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Procurement",
                title="Comparison incomplete",
                description="Supplier quotations have not been compared consistently.",
                severity=AgentSeverity.HIGH,
                confidence_score=90,
                blocking=True,
                recommended_action="Complete structured quotation comparison.",
            ))

        return tuple(findings)

_agent = ProcurementAgent()

def get_procurement_agent() -> ProcurementAgent:
    return _agent