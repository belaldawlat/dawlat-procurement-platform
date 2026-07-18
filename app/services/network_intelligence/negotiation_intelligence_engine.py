"""Negotiation Intelligence Engine for GPNI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class NegotiationParty(str, Enum):
    BUYER = "Buyer"
    SUPPLIER = "Supplier"
    LOGISTICS = "Logistics"
    INTERNAL = "Internal"


class NegotiationStatus(str, Enum):
    DRAFT = "Draft"
    WAITING_FOR_APPROVAL = "Waiting for Approval"
    APPROVED_TO_SEND = "Approved to Send"
    SENT = "Sent"
    RESPONSE_RECEIVED = "Response Received"
    CLOSED = "Closed"
    CANCELLED = "Cancelled"


@dataclass(frozen=True)
class NegotiationConstraint:
    name: str
    minimum: float | None = None
    maximum: float | None = None
    required_value: str | None = None
    mandatory: bool = True


@dataclass(frozen=True)
class NegotiationPlan:
    subject: str
    counterparty: str
    party_type: NegotiationParty
    objectives: tuple[str, ...]
    constraints: tuple[NegotiationConstraint, ...]
    opening_position: dict[str, Any]
    target_position: dict[str, Any]
    walk_away_position: dict[str, Any]
    required_approvals: tuple[str, ...]
    prohibited_commitments: tuple[str, ...]
    evidence_required: tuple[str, ...]
    status: NegotiationStatus = NegotiationStatus.DRAFT
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


@dataclass(frozen=True)
class NegotiationRecommendation:
    approved_to_send: bool
    requires_human_approval: bool
    draft_message: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    strategy_notes: tuple[str, ...]


class NegotiationIntelligenceEngine:
    """Evaluate proposed negotiation terms against protected constraints."""

    def evaluate(
        self,
        plan: NegotiationPlan,
        proposed_terms: dict[str, Any],
    ) -> NegotiationRecommendation:
        blockers: list[str] = []
        warnings: list[str] = []
        strategy_notes: list[str] = []

        for constraint in plan.constraints:
            value = proposed_terms.get(constraint.name)

            if (
                constraint.required_value is not None
                and value != constraint.required_value
            ):
                message = (
                    f"{constraint.name} must equal "
                    f"{constraint.required_value}."
                )
                if constraint.mandatory:
                    blockers.append(message)
                else:
                    warnings.append(message)

            if constraint.minimum is not None:
                try:
                    if value is None or float(value) < constraint.minimum:
                        message = (
                            f"{constraint.name} is below the minimum "
                            f"{constraint.minimum}."
                        )
                        if constraint.mandatory:
                            blockers.append(message)
                        else:
                            warnings.append(message)
                except (TypeError, ValueError):
                    blockers.append(
                        f"{constraint.name} is not a valid number."
                    )

            if constraint.maximum is not None:
                try:
                    if value is None or float(value) > constraint.maximum:
                        message = (
                            f"{constraint.name} exceeds the maximum "
                            f"{constraint.maximum}."
                        )
                        if constraint.mandatory:
                            blockers.append(message)
                        else:
                            warnings.append(message)
                except (TypeError, ValueError):
                    blockers.append(
                        f"{constraint.name} is not a valid number."
                    )

        for prohibited_commitment in plan.prohibited_commitments:
            if bool(proposed_terms.get(prohibited_commitment)):
                blockers.append(
                    f"Prohibited commitment detected: "
                    f"{prohibited_commitment}."
                )

        missing_evidence = [
            evidence_name
            for evidence_name in plan.evidence_required
            if not proposed_terms.get(f"evidence:{evidence_name}")
        ]

        if missing_evidence:
            blockers.append(
                "Required evidence is missing: "
                + ", ".join(missing_evidence)
            )

        if plan.required_approvals:
            warnings.append(
                "Human approval is required before sending "
                "or accepting terms."
            )

        approved_to_send = (
            not blockers
            and not plan.required_approvals
        )
        requires_human_approval = bool(
            plan.required_approvals
        ) or bool(blockers)

        strategy_notes.extend(
            [
                (
                    "Protect buyer and supplier relationships "
                    "with evidence-based terms."
                ),
                (
                    "Do not disclose protected counterparty "
                    "pricing or margin details."
                ),
                (
                    "Do not create a binding commitment until "
                    "safeguards and approvals pass."
                ),
            ]
        )

        terms_text = "\n".join(
            f"- {key}: {value}"
            for key, value in proposed_terms.items()
            if not key.startswith("evidence:")
        )

        draft_message = (
            f"Subject: {plan.subject}\n\n"
            f"Dear {plan.counterparty},\n\n"
            "Thank you for your cooperation. Based on the current "
            "commercial review, please confirm the following proposed "
            f"terms:\n\n{terms_text}\n\n"
            "These terms remain subject to final internal approval, "
            "verification of required documents, compliance review, "
            "and confirmation of the agreed payment and delivery "
            "milestones.\n\n"
            "Kind regards,\n"
            "Dawlat Global Imports & Trading"
        )

        return NegotiationRecommendation(
            approved_to_send=approved_to_send,
            requires_human_approval=requires_human_approval,
            draft_message=draft_message,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            strategy_notes=tuple(strategy_notes),
        )


_engine = NegotiationIntelligenceEngine()


def get_negotiation_intelligence_engine() -> NegotiationIntelligenceEngine:
    return _engine