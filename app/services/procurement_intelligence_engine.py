"""
Dawlat Procurement Intelligence Engine.

Central orchestration layer for demand, sourcing, quotations, logistics,
warehousing, landed cost, shipment risk and executive recommendations.

The engine is intentionally read-only:
- it never invents suppliers, prices, certificates or buyer demand;
- it records evidence, assumptions, gaps and risks;
- it requires human approval before operational actions;
- it supports rice, cricket, automotive, medical and future categories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from services.ai_assistant_service import build_ai_context
from services.global_discovery_service import (
    DiscoveryRequest,
    prepare_discovery_search,
)
from services.supplier_ranking_engine import (
    RankedSupplierResult,
    rank_supplier_results,
)


class DecisionStatus(str, Enum):
    READY_FOR_APPROVAL = "Ready for Approval"
    RESEARCH_REQUIRED = "Research Required"
    QUOTATIONS_REQUIRED = "Quotations Required"
    COSTING_REQUIRED = "Costing Required"
    HIGH_RISK = "High Risk"
    NOT_RECOMMENDED = "Not Recommended"


@dataclass(frozen=True)
class ProcurementRequirement:
    product: str
    quantity: float
    unit: str
    destination: str
    buyer_name: str = ""
    origin_country_preference: str = ""
    required_delivery_date: str | None = None
    target_buy_price: float | None = None
    target_sell_price: float | None = None
    currency: str = "AUD"
    specifications: str = ""
    packaging: str = ""
    required_certificates: tuple[str, ...] = ()
    preferred_incoterms: tuple[str, ...] = ()
    payment_terms: str = ""
    maximum_lead_time_days: int | None = None
    notes: str = ""


@dataclass(frozen=True)
class EvidenceReference:
    source: str
    label: str
    details: str
    record_id: int | None = None
    url: str | None = None


@dataclass(frozen=True)
class RiskFinding:
    category: str
    severity: str
    description: str
    mitigation: str


@dataclass(frozen=True)
class ActionRecommendation:
    priority: int
    action: str
    owner_role: str
    approval_required: bool = False
    reason: str = ""


@dataclass
class ProcurementDecision:
    status: DecisionStatus
    title: str
    executive_summary: str
    confidence_score: int
    requirement: ProcurementRequirement
    commercial_summary: dict[str, Any] = field(default_factory=dict)
    fulfilment_summary: dict[str, Any] = field(default_factory=dict)
    risks: list[RiskFinding] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    recommendations: list[ActionRecommendation] = field(default_factory=list)
    evidence: list[EvidenceReference] = field(default_factory=list)
    live_supplier_results: list[RankedSupplierResult] = field(default_factory=list)
    matched_records: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class ProcurementIntelligenceEngine:
    """Governed end-to-end procurement decision orchestrator."""

    def evaluate(
        self,
        requirement: ProcurementRequirement,
        *,
        include_live_discovery: bool = False,
    ) -> ProcurementDecision:
        self._validate(requirement)
        context = build_ai_context(limit_per_domain=100)
        terms = self._terms(requirement)

        matched = {
            "customers": self._match(
                context.get("customers", []),
                terms,
                ("company_name", "products_of_interest", "estimated_demand", "notes"),
            ),
            "opportunities": self._match(
                context.get("opportunities", []),
                terms,
                ("title", "product", "buyer_company", "industry", "notes"),
            ),
            "suppliers": self._match(
                context.get("suppliers", []),
                terms,
                ("company_name", "category", "country", "notes"),
            ),
            "supplier_quotes": self._match(
                context.get("supplier_quotes", []),
                terms,
                (
                    "supplier_name",
                    "quote_reference",
                    "packaging",
                    "certificates",
                    "notes",
                ),
            ),
            "logistics_quotes": self._match(
                context.get("logistics_quotes", []),
                terms,
                (
                    "provider_name",
                    "cargo_description",
                    "origin_country",
                    "destination_city_port",
                    "notes",
                ),
            ),
            "warehouse_quotes": self._match(
                context.get("warehouse_quotes", []),
                terms,
                ("provider_name", "product_description", "city", "country", "notes"),
            ),
            "landed_costs": self._match(
                context.get("landed_costs", []),
                terms,
                (
                    "name",
                    "product_name",
                    "supplier_name",
                    "origin_country",
                    "destination",
                    "notes",
                ),
            ),
            "shipments": self._match(
                context.get("shipments", []),
                terms,
                (
                    "shipment_number",
                    "shipment_reference",
                    "shipment_name",
                    "product_name",
                    "supplier_name",
                    "origin_country",
                    "destination_country",
                    "notes",
                ),
            ),
            "inventory": self._match(
                context.get("inventory", []),
                terms,
                (
                    "product_name",
                    "sku",
                    "supplier_name",
                    "warehouse_name",
                    "country_of_origin",
                    "notes",
                ),
            ),
        }

        live_results = (
            self._discover(requirement)
            if include_live_discovery
            else []
        )

        commercial = self._commercial(
            requirement,
            matched["supplier_quotes"],
            matched["landed_costs"],
        )
        fulfilment = self._fulfilment(
            requirement,
            matched["inventory"],
            matched["supplier_quotes"],
            matched["logistics_quotes"],
            matched["shipments"],
        )
        gaps = self._gaps(requirement, matched, live_results)
        risks = self._risks(requirement, matched, live_results)
        confidence = self._confidence(matched, gaps, risks)
        status = self._status(
            matched["supplier_quotes"],
            matched["landed_costs"],
            risks,
            gaps,
            confidence,
        )
        actions = self._actions(status, matched, live_results)
        evidence = self._evidence(matched, live_results)

        return ProcurementDecision(
            status=status,
            title=f"Procurement Decision: {requirement.product}",
            executive_summary=(
                f"Requirement: {requirement.quantity:g} {requirement.unit} of "
                f"{requirement.product} to {requirement.destination}. "
                f"Decision status: {status.value}. Confidence: {confidence}/100. "
                f"Found {len(matched['suppliers'])} saved supplier(s), "
                f"{len(matched['supplier_quotes'])} supplier quotation(s), "
                f"{len(matched['landed_costs'])} landed-cost calculation(s), "
                f"and {len(risks)} material risk finding(s)."
            ),
            confidence_score=confidence,
            requirement=requirement,
            commercial_summary=commercial,
            fulfilment_summary=fulfilment,
            risks=risks,
            data_gaps=gaps,
            recommendations=actions,
            evidence=evidence,
            live_supplier_results=live_results,
            matched_records=matched,
            assumptions=[
                "Saved records are operational evidence, not independently audited truth.",
                "Live web results remain unverified until reviewed by a human.",
                "No purchase, payment, email, RFQ or supplier approval is executed automatically.",
            ],
        )

    def _discover(
        self,
        requirement: ProcurementRequirement,
    ) -> list[RankedSupplierResult]:
        request = DiscoveryRequest(
            partner_type="Supplier",
            product=requirement.product,
            country=requirement.origin_country_preference,
            destination=requirement.destination,
            requirements=" ".join(
                item
                for item in (
                    requirement.specifications,
                    requirement.packaging,
                    requirement.payment_terms,
                    requirement.notes,
                )
                if item
            ),
            required_certificates=requirement.required_certificates,
            preferred_incoterms=requirement.preferred_incoterms,
            maximum_lead_time_days=requirement.maximum_lead_time_days,
            minimum_confidence_score=60,
        )
        result = prepare_discovery_search(request)
        raw_results = [
            item
            for response in result.live_responses
            if response.success
            for item in response.results
        ]
        ranked = rank_supplier_results(
            raw_results,
            product=requirement.product,
            country=requirement.origin_country_preference,
            partner_type="Supplier",
        )
        return [
            item
            for item in ranked
            if item.overall_score >= request.minimum_confidence_score
        ][:20]

    @staticmethod
    def _commercial(
        requirement: ProcurementRequirement,
        quotes: list[dict[str, Any]],
        landed_costs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result = {
            "currency": requirement.currency,
            "best_unit_price": None,
            "best_supplier": None,
            "best_landed_cost_per_unit": None,
            "estimated_revenue": None,
            "estimated_gross_profit": None,
        }

        valid_quotes = [q for q in quotes if _number(q.get("unit_price")) > 0]
        if valid_quotes:
            best = min(valid_quotes, key=lambda q: _number(q.get("unit_price")))
            result["best_unit_price"] = _number(best.get("unit_price"))
            result["best_supplier"] = best.get("supplier_name")

        valid_costs = [
            c
            for c in landed_costs
            if _number(c.get("landed_cost_per_unit")) > 0
        ]
        if valid_costs:
            best_cost = min(
                valid_costs,
                key=lambda c: _number(c.get("landed_cost_per_unit")),
            )
            landed_per_unit = _number(best_cost.get("landed_cost_per_unit"))
            result["best_landed_cost_per_unit"] = landed_per_unit

            if requirement.target_sell_price is not None:
                result["estimated_revenue"] = round(
                    requirement.target_sell_price * requirement.quantity,
                    2,
                )
                result["estimated_gross_profit"] = round(
                    (
                        requirement.target_sell_price
                        - landed_per_unit
                    )
                    * requirement.quantity,
                    2,
                )

        return result

    @staticmethod
    def _fulfilment(
        requirement: ProcurementRequirement,
        inventory: list[dict[str, Any]],
        supplier_quotes: list[dict[str, Any]],
        logistics_quotes: list[dict[str, Any]],
        shipments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        available = sum(
            max(
                0,
                _number(item.get("quantity_on_hand"))
                - _number(item.get("quantity_reserved")),
            )
            for item in inventory
        )
        supplier_days = min(
            (
                int(_number(item.get("lead_time_days")))
                for item in supplier_quotes
                if _number(item.get("lead_time_days")) > 0
            ),
            default=None,
        )
        transit_days = min(
            (
                int(_number(item.get("transit_days")))
                for item in logistics_quotes
                if _number(item.get("transit_days")) > 0
            ),
            default=None,
        )
        return {
            "required_quantity": requirement.quantity,
            "unit": requirement.unit,
            "available_internal_inventory": round(available, 2),
            "inventory_gap": round(max(0, requirement.quantity - available), 2),
            "fastest_supplier_lead_time_days": supplier_days,
            "fastest_transit_days": transit_days,
            "estimated_fastest_total_days": (
                supplier_days + transit_days
                if supplier_days is not None and transit_days is not None
                else None
            ),
            "related_active_shipments": len(
                [
                    item
                    for item in shipments
                    if (
                        item.get("shipment_status")
                        or item.get("status")
                    )
                    not in {"Delivered", "Completed", "Cancelled"}
                ]
            ),
        }

    @staticmethod
    def _gaps(
        requirement: ProcurementRequirement,
        matched: dict[str, list[dict[str, Any]]],
        live_results: list[RankedSupplierResult],
    ) -> list[str]:
        gaps = []
        checks = (
            ("opportunities", "No verified market opportunity is linked."),
            ("suppliers", "No saved supplier matches the requirement."),
            ("supplier_quotes", "No supplier quotation is available."),
            ("logistics_quotes", "No matching freight quotation is available."),
            ("warehouse_quotes", "No destination warehouse quotation is available."),
            ("landed_costs", "No completed landed-cost calculation is available."),
        )
        for key, message in checks:
            if not matched[key]:
                if key == "suppliers" and live_results:
                    continue
                gaps.append(message)

        if not requirement.required_certificates:
            gaps.append("Required certificates are not defined.")
        if not requirement.required_delivery_date:
            gaps.append("Required delivery date is not defined.")
        if requirement.target_sell_price is None:
            gaps.append("Target selling price is missing; profit is unconfirmed.")
        return gaps

    @staticmethod
    def _risks(
        requirement: ProcurementRequirement,
        matched: dict[str, list[dict[str, Any]]],
        live_results: list[RankedSupplierResult],
    ) -> list[RiskFinding]:
        risks = []

        if not matched["suppliers"] and live_results:
            risks.append(
                RiskFinding(
                    "Supplier Verification",
                    "High",
                    "Only live web candidates are available.",
                    "Verify legal identity, factory, contacts, certificates, samples and references.",
                )
            )
        if not matched["logistics_quotes"]:
            risks.append(
                RiskFinding(
                    "Logistics",
                    "Medium",
                    "Delivery feasibility is not confirmed by a freight quote.",
                    "Obtain route, transit-time, inclusion and exclusion details.",
                )
            )
        if not matched["landed_costs"]:
            risks.append(
                RiskFinding(
                    "Commercial",
                    "High",
                    "Total landed cost and profit are not verified.",
                    "Complete duty, GST, customs, biosecurity, port, warehouse and local-delivery costing.",
                )
            )

        delayed = [
            item
            for item in matched["shipments"]
            if (
                item.get("shipment_status")
                or item.get("status")
            )
            in {"Delayed", "Biosecurity Hold", "Inspection Hold"}
            or item.get("delay_reason")
        ]
        if delayed:
            risks.append(
                RiskFinding(
                    "Historical Delivery",
                    "Medium",
                    f"{len(delayed)} related shipment(s) contain delay or hold indicators.",
                    "Review route, carrier, document, port and supplier causes.",
                )
            )

        if requirement.maximum_lead_time_days is not None:
            quotes = matched["supplier_quotes"]
            if quotes and all(
                _number(item.get("lead_time_days"))
                > requirement.maximum_lead_time_days
                for item in quotes
            ):
                risks.append(
                    RiskFinding(
                        "Lead Time",
                        "High",
                        "No recorded supplier quotation meets the maximum lead time.",
                        "Negotiate faster production or source an alternative supplier.",
                    )
                )
        return risks

    @staticmethod
    def _confidence(
        matched: dict[str, list[dict[str, Any]]],
        gaps: list[str],
        risks: list[RiskFinding],
    ) -> int:
        weights = {
            "customers": 8,
            "opportunities": 10,
            "suppliers": 12,
            "supplier_quotes": 18,
            "logistics_quotes": 12,
            "warehouse_quotes": 8,
            "landed_costs": 20,
        }
        score = 10 + sum(
            weight
            for key, weight in weights.items()
            if matched[key]
        )
        score -= min(30, len(gaps) * 3)
        score -= sum(
            {"Low": 2, "Medium": 5, "High": 10, "Critical": 18}.get(
                risk.severity,
                5,
            )
            for risk in risks
        )
        return max(0, min(100, score))

    @staticmethod
    def _status(
        quotes: list[dict[str, Any]],
        landed_costs: list[dict[str, Any]],
        risks: list[RiskFinding],
        gaps: list[str],
        confidence: int,
    ) -> DecisionStatus:
        if any(risk.severity == "Critical" for risk in risks):
            return DecisionStatus.NOT_RECOMMENDED
        if any(risk.severity == "High" for risk in risks) and confidence < 55:
            return DecisionStatus.HIGH_RISK
        if not quotes:
            return DecisionStatus.QUOTATIONS_REQUIRED
        if not landed_costs:
            return DecisionStatus.COSTING_REQUIRED
        if gaps or confidence < 70:
            return DecisionStatus.RESEARCH_REQUIRED
        return DecisionStatus.READY_FOR_APPROVAL

    @staticmethod
    def _actions(
        status: DecisionStatus,
        matched: dict[str, list[dict[str, Any]]],
        live_results: list[RankedSupplierResult],
    ) -> list[ActionRecommendation]:
        actions = []
        priority = 1

        def add(
            action: str,
            role: str,
            reason: str,
            approval: bool = False,
        ) -> None:
            nonlocal priority
            actions.append(
                ActionRecommendation(
                    priority,
                    action,
                    role,
                    approval,
                    reason,
                )
            )
            priority += 1

        if not matched["suppliers"] and live_results:
            add(
                "Verify and save the highest-ranked live supplier candidates.",
                "Global Sourcing Specialist",
                "Live search results are not approved suppliers.",
                True,
            )
        elif not matched["suppliers"]:
            add(
                "Run global supplier discovery.",
                "Global Sourcing Specialist",
                "No matching supplier is available.",
            )

        if not matched["supplier_quotes"]:
            add(
                "Issue a structured RFQ covering specifications, MOQ, pricing, Incoterms, lead time, payment terms, packaging, samples and certificates.",
                "Procurement Specialist",
                "Commercial supplier offers are missing.",
                True,
            )

        if not matched["logistics_quotes"]:
            add(
                "Request comparable freight and customs quotations.",
                "Logistics Coordinator",
                "Delivery feasibility and cost are unconfirmed.",
            )

        if not matched["warehouse_quotes"]:
            add(
                "Confirm destination warehouse capacity and charges.",
                "Warehouse Manager",
                "Storage and receiving costs are unconfirmed.",
            )

        if not matched["landed_costs"]:
            add(
                "Complete landed-cost and expected-margin analysis.",
                "Cost & Profit Analyst",
                "Profitability is not verified.",
                True,
            )

        if status == DecisionStatus.READY_FOR_APPROVAL:
            add(
                "Submit the procurement plan for management approval.",
                "Executive Advisor",
                "The evidence and commercial analysis meet the decision gate.",
                True,
            )
        return actions

    @staticmethod
    def _evidence(
        matched: dict[str, list[dict[str, Any]]],
        live_results: list[RankedSupplierResult],
    ) -> list[EvidenceReference]:
        evidence = []
        mapping = (
            ("customers", "Customers", "company_name"),
            ("opportunities", "Market Opportunities", "title"),
            ("suppliers", "Suppliers", "company_name"),
            ("supplier_quotes", "Supplier Quotations", "supplier_name"),
            ("logistics_quotes", "Logistics Quotations", "provider_name"),
            ("landed_costs", "Landed Costs", "name"),
            ("shipments", "Shipments", "shipment_number"),
        )
        for key, source, label_field in mapping:
            for item in matched[key][:3]:
                evidence.append(
                    EvidenceReference(
                        source=source,
                        record_id=item.get("id"),
                        label=item.get(label_field) or source,
                        details=str(item)[:500],
                    )
                )

        for item in live_results[:5]:
            evidence.append(
                EvidenceReference(
                    source="Live Global Discovery",
                    label=item.title,
                    url=item.url,
                    details=(
                        f"Score {item.overall_score}/100; "
                        f"{item.classification}; {item.recommendation}."
                    ),
                )
            )
        return evidence

    @staticmethod
    def _validate(requirement: ProcurementRequirement) -> None:
        if not requirement.product.strip():
            raise ValueError("Product is required.")
        if requirement.quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if not requirement.unit.strip():
            raise ValueError("Unit is required.")
        if not requirement.destination.strip():
            raise ValueError("Destination is required.")

    @staticmethod
    def _terms(requirement: ProcurementRequirement) -> list[str]:
        values = (
            requirement.product,
            requirement.origin_country_preference,
            requirement.destination,
            requirement.buyer_name,
        )
        terms = []
        for value in values:
            terms.extend(
                token
                for token in value.lower().replace(",", " ").replace("-", " ").split()
                if len(token) >= 3
            )
        return list(dict.fromkeys(terms))

    @staticmethod
    def _match(
        records: list[dict[str, Any]],
        terms: list[str],
        fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if not terms:
            return records
        return [
            record
            for record in records
            if any(
                term
                in " ".join(
                    str(record.get(field) or "")
                    for field in fields
                ).lower()
                for term in terms
            )
        ]


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


_engine = ProcurementIntelligenceEngine()


def evaluate_procurement_case(
    requirement: ProcurementRequirement,
    *,
    include_live_discovery: bool = False,
) -> ProcurementDecision:
    return _engine.evaluate(
        requirement,
        include_live_discovery=include_live_discovery,
    )