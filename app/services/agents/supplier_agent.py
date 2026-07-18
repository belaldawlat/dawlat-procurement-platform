"""Supplier intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class SupplierAgent:
    name = "Supplier Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        supplier = payload.get("supplier", {})
        findings: list[AgentFinding] = []

        if not supplier.get("verified"):
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Supplier",
                title="Supplier verification incomplete",
                description="Supplier identity and legal status are not verified.",
                severity=AgentSeverity.CRITICAL,
                confidence_score=95,
                blocking=True,
                recommended_action="Complete supplier verification.",
            ))

        if not supplier.get("capacity_confirmed"):
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Supplier",
                title="Capacity evidence missing",
                description="Supplier production or allocation capacity is unconfirmed.",
                severity=AgentSeverity.HIGH,
                confidence_score=90,
                blocking=True,
                recommended_action="Obtain current capacity evidence.",
            ))

        if supplier.get("quality_score", 0) < 60:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Supplier",
                title="Quality performance weak",
                description="Supplier quality score is below the protected threshold.",
                severity=AgentSeverity.HIGH,
                confidence_score=85,
                blocking=True,
                recommended_action="Require samples, inspection and corrective evidence.",
            ))

        return tuple(findings)

_agent = SupplierAgent()

def get_supplier_agent() -> SupplierAgent:
    return _agent