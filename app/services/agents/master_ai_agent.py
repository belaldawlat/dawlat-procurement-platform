"""Master AI agent for enterprise procurement coordination."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.agents.agent_coordinator import AgentReport, get_agent_coordinator
from services.agents.buyer_agent import get_buyer_agent
from services.agents.compliance_agent import get_compliance_agent
from services.agents.document_agent import get_document_agent
from services.agents.executive_agent import get_executive_agent
from services.agents.finance_agent import get_finance_agent
from services.agents.inventory_agent import get_inventory_agent
from services.agents.logistics_agent import get_logistics_agent
from services.agents.market_agent import get_market_agent
from services.agents.negotiation_agent import get_negotiation_agent
from services.agents.procurement_agent import get_procurement_agent
from services.agents.risk_agent import get_risk_agent
from services.agents.shipment_agent import get_shipment_agent
from services.agents.supplier_agent import get_supplier_agent

@dataclass(frozen=True)
class MasterAgentDecision:
    case_id: str
    report: AgentReport
    decision: str
    execution_allowed: bool
    permitted_actions: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

class MasterAIAgent:
    def __init__(self) -> None:
        self._coordinator = get_agent_coordinator()

        for agent in (
            get_supplier_agent(),
            get_buyer_agent(),
            get_procurement_agent(),
            get_logistics_agent(),
            get_inventory_agent(),
            get_finance_agent(),
            get_compliance_agent(),
            get_risk_agent(),
            get_market_agent(),
            get_negotiation_agent(),
            get_shipment_agent(),
            get_document_agent(),
            get_executive_agent(),
        ):
            self._coordinator.register(agent)

    def evaluate(
        self,
        *,
        case_id: str,
        payload: dict[str, Any],
    ) -> MasterAgentDecision:
        report = self._coordinator.run(
            case_id=case_id,
            payload=payload,
        )

        if report.blockers:
            decision = "Blocked"
        elif report.warnings:
            decision = "Senior Review Required"
        else:
            decision = "Ready for Authorised Review"

        permitted = (
            "Analyse evidence",
            "Prepare comparisons",
            "Generate non-binding drafts",
            "Create review tasks",
            "Raise alerts",
        )

        prohibited = (
            "No supplier commitment",
            "No binding buyer quotation",
            "No purchase order",
            "No payment release",
            "No shipment booking",
            "No contract activation",
            "No protected relationship disclosure",
        )

        return MasterAgentDecision(
            case_id=case_id,
            report=report,
            decision=decision,
            execution_allowed=False,
            permitted_actions=permitted,
            prohibited_actions=prohibited,
            explanation=(
                f"{len(report.findings)} specialist finding(s) were "
                f"consolidated. Decision: {decision}. Final execution "
                "authority remains with authorised users."
            ),
        )

_master = MasterAIAgent()

def get_master_ai_agent() -> MasterAIAgent:
    return _master