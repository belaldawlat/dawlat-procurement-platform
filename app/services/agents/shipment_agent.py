"""Shipment intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class ShipmentAgent:
    name = "Shipment Agent"

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        shipment = payload.get("shipment", {})
        findings: list[AgentFinding] = []

        if shipment.get("delayed"):
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Shipment",
                title="Shipment delay",
                description=str(
                    shipment.get("delay_reason")
                    or "Shipment delay requires attention."
                ),
                severity=AgentSeverity.HIGH,
                confidence_score=95,
                blocking=bool(shipment.get("delivery_commitment_at_risk")),
                recommended_action="Confirm revised ETA and mitigation plan.",
            ))

        if not shipment.get("documents_complete"):
            findings.append(AgentFinding(
                agent_name=self.name,
                category="Shipment",
                title="Shipment documents incomplete",
                description="Required shipment documents are incomplete.",
                severity=AgentSeverity.CRITICAL,
                confidence_score=95,
                blocking=True,
                recommended_action="Complete and verify shipment documents.",
            ))

        return tuple(findings)

_agent = ShipmentAgent()

def get_shipment_agent() -> ShipmentAgent:
    return _agent