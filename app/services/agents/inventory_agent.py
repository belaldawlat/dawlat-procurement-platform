"""Inventory intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class InventoryAgent:
    name = "Inventory Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        inventory = payload.get("inventory", {})
        findings: list[AgentFinding] = []

        available = float(inventory.get("available_quantity", 0))
        required = float(inventory.get("required_quantity", 0))

        if required > available:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Inventory",
                title="Inventory shortage",
                description="Available inventory cannot satisfy the required quantity.",
                severity=AgentSeverity.HIGH,
                confidence_score=95,
                blocking=True,
                recommended_action="Source the shortage or revise the delivery commitment.",
            ))

        if inventory.get("expiry_risk", 0) >= 60:
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Inventory",
                title="Expiry or ageing risk",
                description="Inventory ageing risk is elevated.",
                severity=AgentSeverity.HIGH,
                confidence_score=85,
                recommended_action="Prioritise allocation using FEFO controls.",
            ))

        return tuple(findings)

_agent = InventoryAgent()

def get_inventory_agent() -> InventoryAgent:
    return _agent