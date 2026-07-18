"""Procurement Network Engine for GPNI.

Coordinates the end-to-end Global Procurement Network Intelligence workflow.
This engine is intentionally non-binding: it evaluates readiness and produces
controlled next actions, but never contacts parties, signs contracts, releases
payments, or commits suppliers without explicit authorised approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from services.network_intelligence.buyer_qualification_engine import (
    BuyerQualificationResult,
    get_buyer_qualification_engine,
)
from services.network_intelligence.commercial_safeguards_engine import (
    CommercialSafeguardResult,
    SafeguardDecision,
    get_commercial_safeguards_engine,
)
from services.network_intelligence.contract_readiness_engine import (
    ContractReadinessDecision,
    ContractReadinessResult,
    get_contract_readiness_engine,
)
from services.network_intelligence.demand_supply_matching_engine import (
    MatchAssessment,
    MatchCandidate,
    get_demand_supply_matching_engine,
)
from services.network_intelligence.payment_protection_engine import (
    PaymentDecision,
    PaymentProtectionResult,
    get_payment_protection_engine,
)
from services.network_intelligence.supplier_qualification_engine import (
    SupplierQualificationResult,
    get_supplier_qualification_engine,
)


class NetworkStage(str, Enum):
    DEMAND_CAPTURE = "Demand Capture"
    BUYER_QUALIFICATION = "Buyer Qualification"
    SUPPLY_DISCOVERY = "Supply Discovery"
    SUPPLIER_QUALIFICATION = "Supplier Qualification"
    MATCHING = "Demand-Supply Matching"
    COMMERCIAL_REVIEW = "Commercial Review"
    BUYER_APPROVAL = "Buyer Approval"
    PAYMENT_PROTECTION = "Payment Protection"
    CONTRACT_READINESS = "Contract Readiness"
    EXECUTION_READY = "Execution Ready"
    BLOCKED = "Blocked"


class NetworkDecision(str, Enum):
    BLOCK = "Block"
    HOLD = "Hold"
    REVIEW = "Review"
    PROCEED = "Proceed"
    READY_FOR_EXECUTION = "Ready for Execution"


@dataclass(frozen=True)
class ProcurementNetworkCase:
    case_id: str
    buyer: dict[str, Any]
    supplier: dict[str, Any]
    match_candidate: MatchCandidate
    commercial_case: dict[str, Any]
    payment_case: dict[str, Any]
    contract_case: dict[str, Any]
    actor: str = "GPNI"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcurementNetworkAssessment:
    case_id: str
    stage: NetworkStage
    decision: NetworkDecision
    overall_score: int
    buyer_qualification: BuyerQualificationResult
    supplier_qualification: SupplierQualificationResult
    match_assessment: MatchAssessment
    commercial_safeguards: CommercialSafeguardResult
    payment_protection: PaymentProtectionResult
    contract_readiness: ContractReadinessResult
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    required_actions: tuple[str, ...]
    execution_allowed: bool
    explanation: str
    assessed_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


class ProcurementNetworkEngine:
    """Coordinate all protected GPNI decision gates."""

    def __init__(self) -> None:
        self._buyer_engine = get_buyer_qualification_engine()
        self._supplier_engine = get_supplier_qualification_engine()
        self._matching_engine = get_demand_supply_matching_engine()
        self._commercial_engine = get_commercial_safeguards_engine()
        self._payment_engine = get_payment_protection_engine()
        self._contract_engine = get_contract_readiness_engine()

    def assess(
        self,
        case: ProcurementNetworkCase,
    ) -> ProcurementNetworkAssessment:
        buyer_result = self._buyer_engine.qualify(
            case.buyer
        )
        supplier_result = self._supplier_engine.qualify(
            case.supplier
        )

        match_candidate = MatchCandidate(
            **{
                **case.match_candidate.__dict__,
                "buyer_qualification_score": (
                    buyer_result.score
                ),
                "supplier_qualification_score": (
                    supplier_result.score
                ),
                "buyer_approved_for_matching": (
                    buyer_result.approved_for_matching
                ),
                "supplier_approved_for_matching": (
                    supplier_result.approved_for_matching
                ),
            }
        )

        match_result = self._matching_engine.assess(
            match_candidate
        )
        commercial_result = self._commercial_engine.evaluate(
            case.commercial_case
        )
        payment_result = self._payment_engine.evaluate(
            case.payment_case
        )
        contract_result = self._contract_engine.evaluate(
            case.contract_case
        )

        blockers = list(
            dict.fromkeys(
                [
                    *buyer_result.blockers,
                    *supplier_result.blockers,
                    *match_result.blockers,
                    *commercial_result.blockers,
                    *payment_result.blockers,
                    *contract_result.blockers,
                ]
            )
        )

        warnings = list(
            dict.fromkeys(
                [
                    *buyer_result.warnings,
                    *supplier_result.warnings,
                    *match_result.warnings,
                    *commercial_result.warnings,
                    *commercial_result.conditions,
                    *payment_result.conditions,
                    *contract_result.conditions,
                ]
            )
        )

        required_actions = self._required_actions(
            buyer_result=buyer_result,
            supplier_result=supplier_result,
            match_result=match_result,
            commercial_result=commercial_result,
            payment_result=payment_result,
            contract_result=contract_result,
        )

        stage, decision = self._resolve_stage_and_decision(
            buyer_result=buyer_result,
            supplier_result=supplier_result,
            match_result=match_result,
            commercial_result=commercial_result,
            payment_result=payment_result,
            contract_result=contract_result,
            blockers=blockers,
        )

        execution_allowed = (
            decision == NetworkDecision.READY_FOR_EXECUTION
            and contract_result.activation_allowed
            and payment_result.decision
            == PaymentDecision.RELEASE_APPROVED
            and commercial_result.decision
            in {
                SafeguardDecision.PROCEED,
                SafeguardDecision.PROCEED_WITH_CONDITIONS,
            }
            and not blockers
        )

        overall_score = round(
            buyer_result.score * 0.15
            + supplier_result.score * 0.15
            + match_result.risk_adjusted_score * 0.20
            + commercial_result.score * 0.20
            + contract_result.score * 0.20
            + (
                100
                if payment_result.decision
                == PaymentDecision.RELEASE_APPROVED
                else 60
                if payment_result.decision
                == PaymentDecision.PARTIAL_RELEASE
                else 20
            )
            * 0.10
        )

        explanation = (
            f"Case {case.case_id} is at stage {stage.value}. "
            f"Decision: {decision.value}. Overall readiness score: "
            f"{overall_score}/100. Execution is "
            f"{'allowed' if execution_allowed else 'not allowed'}."
        )

        return ProcurementNetworkAssessment(
            case_id=case.case_id,
            stage=stage,
            decision=decision,
            overall_score=max(
                0,
                min(100, overall_score),
            ),
            buyer_qualification=buyer_result,
            supplier_qualification=supplier_result,
            match_assessment=match_result,
            commercial_safeguards=commercial_result,
            payment_protection=payment_result,
            contract_readiness=contract_result,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            required_actions=tuple(required_actions),
            execution_allowed=execution_allowed,
            explanation=explanation,
        )

    @staticmethod
    def _required_actions(
        *,
        buyer_result: BuyerQualificationResult,
        supplier_result: SupplierQualificationResult,
        match_result: MatchAssessment,
        commercial_result: CommercialSafeguardResult,
        payment_result: PaymentProtectionResult,
        contract_result: ContractReadinessResult,
    ) -> list[str]:
        actions: list[str] = []

        if not buyer_result.approved_for_matching:
            actions.append(
                "Complete buyer identity, authority and credit qualification."
            )

        if not supplier_result.approved_for_matching:
            actions.append(
                "Complete supplier verification, sanctions and export-readiness checks."
            )

        if not match_result.eligible:
            actions.extend(
                match_result.next_actions
            )

        if commercial_result.decision == SafeguardDecision.BLOCK:
            actions.append(
                "Resolve all commercial safeguard blockers."
            )

        if payment_result.decision in {
            PaymentDecision.BLOCKED,
            PaymentDecision.HOLD,
        }:
            actions.append(
                "Confirm cleared buyer funds and required payment milestones."
            )

        if contract_result.decision != ContractReadinessDecision.ACTIVE:
            actions.append(
                "Complete contract terms, approvals, signatures and activation conditions."
            )

        return list(
            dict.fromkeys(actions)
        )

    @staticmethod
    def _resolve_stage_and_decision(
        *,
        buyer_result: BuyerQualificationResult,
        supplier_result: SupplierQualificationResult,
        match_result: MatchAssessment,
        commercial_result: CommercialSafeguardResult,
        payment_result: PaymentProtectionResult,
        contract_result: ContractReadinessResult,
        blockers: list[str],
    ) -> tuple[NetworkStage, NetworkDecision]:
        if blockers:
            return (
                NetworkStage.BLOCKED,
                NetworkDecision.BLOCK,
            )

        if not buyer_result.approved_for_matching:
            return (
                NetworkStage.BUYER_QUALIFICATION,
                NetworkDecision.HOLD,
            )

        if not supplier_result.approved_for_matching:
            return (
                NetworkStage.SUPPLIER_QUALIFICATION,
                NetworkDecision.HOLD,
            )

        if not match_result.eligible:
            return (
                NetworkStage.MATCHING,
                NetworkDecision.REVIEW,
            )

        if commercial_result.decision in {
            SafeguardDecision.BLOCK,
            SafeguardDecision.REVIEW,
        }:
            return (
                NetworkStage.COMMERCIAL_REVIEW,
                NetworkDecision.REVIEW,
            )

        if payment_result.decision in {
            PaymentDecision.BLOCKED,
            PaymentDecision.HOLD,
        }:
            return (
                NetworkStage.PAYMENT_PROTECTION,
                NetworkDecision.HOLD,
            )

        if contract_result.decision != ContractReadinessDecision.ACTIVE:
            return (
                NetworkStage.CONTRACT_READINESS,
                NetworkDecision.REVIEW,
            )

        return (
            NetworkStage.EXECUTION_READY,
            NetworkDecision.READY_FOR_EXECUTION,
        )


_engine = ProcurementNetworkEngine()


def get_procurement_network_engine() -> ProcurementNetworkEngine:
    return _engine