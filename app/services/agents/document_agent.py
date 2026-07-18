"""Trade document intelligence agent."""
from __future__ import annotations
from typing import Any
from services.agents.agent_coordinator import AgentFinding, AgentSeverity

class DocumentAgent:
    name = "Document Agent"

    REQUIRED_DOCUMENTS = (
        "commercial_invoice",
        "packing_list",
        "certificate_of_origin",
        "bill_of_lading",
    )

    def analyse(
        self,
        case_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentFinding, ...]:
        documents = payload.get("documents", {})
        missing = [
            document
            for document in self.REQUIRED_DOCUMENTS
            if not documents.get(document)
        ]

        if not missing:
            return ()

        return (
            AgentFinding(
                agent_name=self.name,
                category="Documents",
                title="Required documents missing",
                description="Missing documents: " + ", ".join(missing),
                severity=AgentSeverity.CRITICAL,
                confidence_score=100,
                blocking=True,
                recommended_action="Collect and verify all required documents.",
            ),
        )

_agent = DocumentAgent()

def get_document_agent() -> DocumentAgent:
    return _agent