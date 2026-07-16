"""
Dawlat AI Procurement Intelligence Engine.

This module is the central read-only intelligence layer for the Dawlat
Procurement Platform. It connects operational data across customers,
suppliers, products, opportunities, RFQs, quotations, logistics,
warehouses, landed costs, shipments and inventory.

The first production stage is deterministic and database-grounded:
- no invented suppliers, prices or certificates;
- every answer is generated from saved platform records;
- missing information is reported clearly;
- the service is ready for a future LLM provider without changing the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from database.connection import get_connection


@dataclass(frozen=True)
class EvidenceItem:
    """One grounded record used to support an AI response."""

    source: str
    label: str
    details: str
    record_id: int | None = None


@dataclass
class AIResponse:
    """Structured response returned to the Streamlit AI Assistant."""

    success: bool
    title: str
    summary: str
    recommendations: list[str] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    intent: str = "general"


class AIProcurementEngine:
    """
    Central procurement intelligence engine.

    The engine currently provides grounded operational intelligence using
    the platform database. A future LLM adapter can use ``build_context()``
    and the same AIResponse contract.
    """

    def answer(self, question: str) -> AIResponse:
        cleaned = " ".join((question or "").strip().split())

        if not cleaned:
            return AIResponse(
                success=False,
                title="Question required",
                summary="Enter a business question for the AI Assistant.",
                recommendations=[
                    "Ask for today's priorities.",
                    "Ask which opportunity should be pursued first.",
                    "Ask about suppliers, quotations, shipments or inventory.",
                ],
            )

        intent = self._detect_intent(cleaned)
        handlers = {
            "executive": self._answer_executive,
            "supplier": self._answer_suppliers,
            "customer": self._answer_customers,
            "opportunity": self._answer_opportunities,
            "quotation": self._answer_quotations,
            "shipment": self._answer_shipments,
            "inventory": self._answer_inventory,
            "product": self._answer_products,
        }

        handler = handlers.get(intent, self._answer_general)
        response = handler(cleaned)
        response.intent = intent
        response.data["question"] = cleaned
        response.data["generated_at"] = datetime.now().isoformat(
            timespec="seconds"
        )
        return response

    def build_context(self, limit_per_domain: int = 25) -> dict[str, Any]:
        """
        Build a safe, structured snapshot for a future LLM provider.

        The returned object contains only records already stored in the
        platform database.
        """

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "metrics": self._platform_metrics(),
            "opportunities": self._rows(
                """
                SELECT *
                FROM market_opportunities
                ORDER BY
                    CASE urgency
                        WHEN 'Critical' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        ELSE 4
                    END,
                    confidence_score DESC,
                    demand_score DESC,
                    id DESC
                LIMIT ?
                """,
                (limit_per_domain,),
                table="market_opportunities",
            ),
            "customers": self._rows(
                """
                SELECT *
                FROM customers
                ORDER BY
                    CASE lead_status
                        WHEN 'Qualified' THEN 1
                        WHEN 'Contacted' THEN 2
                        WHEN 'Prospect' THEN 3
                        ELSE 4
                    END,
                    company_name
                LIMIT ?
                """,
                (limit_per_domain,),
                table="customers",
            ),
            "suppliers": self._rows(
                """
                SELECT *
                FROM suppliers
                ORDER BY company_name
                LIMIT ?
                """,
                (limit_per_domain,),
                table="suppliers",
            ),
            "supplier_quotes": self._rows(
                """
                SELECT *
                FROM supplier_quotes
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit_per_domain,),
                table="supplier_quotes",
            ),
            "logistics_quotes": self._rows(
                """
                SELECT *
                FROM logistics_quotes
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit_per_domain,),
                table="logistics_quotes",
            ),
            "warehouse_quotes": self._rows(
                """
                SELECT *
                FROM warehouse_quotes
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit_per_domain,),
                table="warehouse_quotes",
            ),
            "landed_costs": self._rows(
                """
                SELECT *
                FROM landed_costs
                ORDER BY gross_margin_percent DESC, id DESC
                LIMIT ?
                """,
                (limit_per_domain,),
                table="landed_costs",
            ),
            "shipments": self._rows(
                """
                SELECT *
                FROM shipments
                WHERE COALESCE(is_deleted, 0) = 0
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit_per_domain,),
                table="shipments",
            ),
            "inventory": self._rows(
                """
                SELECT *
                FROM inventory_items
                ORDER BY product_name, id DESC
                LIMIT ?
                """,
                (limit_per_domain,),
                table="inventory_items",
            ),
        }

    def _answer_executive(self, question: str) -> AIResponse:
        metrics = self._platform_metrics()
        opportunities = self._ranked_opportunities(limit=5)
        shipment_exceptions = self._shipment_exceptions(limit=5)
        expiring_quotes = self._expiring_quotes(limit=5)

        recommendations: list[str] = []
        evidence: list[EvidenceItem] = []
        warnings: list[str] = []

        if opportunities:
            best = opportunities[0]
            recommendations.append(
                "Prioritise the highest-ranked opportunity: "
                f"{best.get('title', 'Untitled')}."
            )
            evidence.append(
                EvidenceItem(
                    source="Market Opportunities",
                    record_id=best.get("id"),
                    label=best.get("title") or "Opportunity",
                    details=(
                        f"Product: {best.get('product') or 'Not recorded'}; "
                        f"buyer: {best.get('buyer_company') or 'Not confirmed'}; "
                        f"priority score: {best.get('ai_score')}."
                    ),
                )
            )
        else:
            recommendations.append(
                "Create and verify market opportunities so the AI can rank demand."
            )
            warnings.append("No market opportunities are currently recorded.")

        if shipment_exceptions:
            recommendations.append(
                f"Resolve {len(shipment_exceptions)} shipment exception(s) "
                "before they affect customer delivery."
            )
            for item in shipment_exceptions[:3]:
                evidence.append(
                    EvidenceItem(
                        source="Shipments",
                        record_id=item.get("id"),
                        label=item.get("shipment_number")
                        or item.get("shipment_reference")
                        or "Shipment",
                        details=(
                            item.get("delay_reason")
                            or item.get("customs_status")
                            or item.get("status")
                            or "Operational exception"
                        ),
                    )
                )
        elif metrics["shipments_total"]:
            recommendations.append(
                "Shipment portfolio currently has no recorded critical exception."
            )

        if expiring_quotes:
            recommendations.append(
                f"Review {len(expiring_quotes)} supplier quotation(s) "
                "that are expired or approaching expiry."
            )

        if metrics["customers_total"] == 0:
            recommendations.append(
                "Add buyer and customer demand records to enable demand-to-supply matching."
            )

        if metrics["suppliers_total"] == 0:
            recommendations.append(
                "Add or discover verified suppliers with products, certificates and capacity."
            )

        summary = (
            f"The platform contains {metrics['opportunities_total']} opportunity(s), "
            f"{metrics['customers_total']} customer(s), "
            f"{metrics['suppliers_total']} supplier(s), "
            f"{metrics['supplier_quotes_total']} supplier quotation(s), and "
            f"{metrics['shipments_total']} shipment(s)."
        )

        return AIResponse(
            success=True,
            title="Executive Procurement Brief",
            summary=summary,
            recommendations=recommendations,
            evidence=evidence,
            metrics=metrics,
            warnings=warnings,
            data={
                "top_opportunities": opportunities,
                "shipment_exceptions": shipment_exceptions,
                "expiring_quotes": expiring_quotes,
            },
        )

    def _answer_suppliers(self, question: str) -> AIResponse:
        terms = self._business_terms(question)
        suppliers = self._search_suppliers(terms)
        quotes = self._search_supplier_quotes(terms)

        evidence = [
            EvidenceItem(
                source="Suppliers",
                record_id=item.get("id"),
                label=item.get("company_name") or "Supplier",
                details=(
                    f"Category: {item.get('category') or 'Not recorded'}; "
                    f"country: {item.get('country') or 'Not recorded'}; "
                    f"contact: {item.get('contact_name') or 'Not recorded'}."
                ),
            )
            for item in suppliers[:8]
        ]

        recommendations: list[str] = []
        warnings: list[str] = []

        if not suppliers:
            recommendations.extend(
                [
                    "Use Global Discovery to find candidate manufacturers and exporters.",
                    "Capture company identity, factory location, products, capacity and contacts.",
                    "Request quotation, MOQ, Incoterm, lead time, payment terms and samples.",
                    "Verify certificates, licences, test reports and export history before approval.",
                ]
            )
            warnings.append(
                "No matching saved supplier was found. The engine will not invent companies."
            )
        else:
            recommendations.append(
                "Shortlist suppliers only after product, certificate, capacity and lead-time verification."
            )
            if quotes:
                best_quote = min(
                    quotes,
                    key=lambda item: self._number(item.get("unit_price")),
                )
                recommendations.append(
                    "Review the lowest recorded unit price from "
                    f"{best_quote.get('supplier_name') or 'the selected supplier'} "
                    "together with quality, compliance and risk scores."
                )
                evidence.append(
                    EvidenceItem(
                        source="Supplier Quotations",
                        record_id=best_quote.get("id"),
                        label=best_quote.get("supplier_name") or "Quotation",
                        details=(
                            f"{best_quote.get('currency') or ''} "
                            f"{self._number(best_quote.get('unit_price')):,.2f} per unit; "
                            f"lead time {best_quote.get('lead_time_days') or 0} days; "
                            f"Incoterm {best_quote.get('incoterm') or 'Not recorded'}."
                        ),
                    )
                )
            else:
                recommendations.append(
                    "Request structured quotations from the matching suppliers."
                )

        product_label = ", ".join(terms) if terms else "the requested category"
        return AIResponse(
            success=True,
            title="Supplier Intelligence",
            summary=(
                f"Found {len(suppliers)} saved supplier(s) and "
                f"{len(quotes)} matching quotation(s) for {product_label}."
            ),
            recommendations=recommendations,
            evidence=evidence,
            metrics={
                "matching_suppliers": len(suppliers),
                "matching_quotations": len(quotes),
            },
            warnings=warnings,
            data={"suppliers": suppliers, "quotations": quotes},
        )

    def _answer_customers(self, question: str) -> AIResponse:
        terms = self._business_terms(question)
        customers = self._search_customers(terms)
        opportunities = self._search_opportunities(terms)

        evidence = [
            EvidenceItem(
                source="Customers",
                record_id=item.get("id"),
                label=item.get("company_name") or "Customer",
                details=(
                    f"Type: {item.get('customer_type') or 'Not recorded'}; "
                    f"interest: {item.get('products_of_interest') or 'Not recorded'}; "
                    f"demand: {item.get('estimated_demand') or 'Not recorded'}; "
                    f"lead status: {item.get('lead_status') or 'Not recorded'}."
                ),
            )
            for item in customers[:8]
        ]

        recommendations = []
        warnings = []

        if customers:
            recommendations.extend(
                [
                    "Confirm quantity, specifications, target price and required delivery date.",
                    "Obtain written demand confirmation before committing supplier or freight capacity.",
                    "Match each qualified buyer with verified suppliers and calculate expected margin.",
                ]
            )
        else:
            recommendations.extend(
                [
                    "Research Australian importers, wholesalers, retailers, supermarkets and institutional buyers.",
                    "Record the buyer's product, quantity, specification, budget and delivery deadline.",
                ]
            )
            warnings.append("No matching saved buyer demand was found.")

        return AIResponse(
            success=True,
            title="Buyer and Demand Intelligence",
            summary=(
                f"Found {len(customers)} matching customer(s) and "
                f"{len(opportunities)} related market opportunity record(s)."
            ),
            recommendations=recommendations,
            evidence=evidence,
            metrics={
                "matching_customers": len(customers),
                "related_opportunities": len(opportunities),
            },
            warnings=warnings,
            data={"customers": customers, "opportunities": opportunities},
        )

    def _answer_opportunities(self, question: str) -> AIResponse:
        terms = self._business_terms(question)
        opportunities = (
            self._search_opportunities(terms)
            if terms
            else self._ranked_opportunities(limit=20)
        )

        ranked = sorted(
            [self._enrich_opportunity(item) for item in opportunities],
            key=lambda item: item["ai_score"],
            reverse=True,
        )

        evidence = [
            EvidenceItem(
                source="Market Opportunities",
                record_id=item.get("id"),
                label=item.get("title") or "Opportunity",
                details=(
                    f"Product: {item.get('product') or 'Not recorded'}; "
                    f"buyer: {item.get('buyer_company') or 'Not confirmed'}; "
                    f"score: {item.get('ai_score')}; "
                    f"expected margin: {item.get('expected_margin') or 'Not calculated'}."
                ),
            )
            for item in ranked[:8]
        ]

        recommendations = []
        warnings = []

        if ranked:
            best = ranked[0]
            recommendations.extend(
                [
                    f"Verify buyer demand for {best.get('title') or 'the highest-ranked opportunity'}.",
                    "Confirm quantity, target price, delivery deadline and payment terms.",
                    "Match local and international supply options before issuing RFQs.",
                    "Complete landed-cost, gross-margin and risk analysis before approval.",
                ]
            )
        else:
            recommendations.append(
                "Create a market opportunity with buyer, product, quantity, urgency and source."
            )
            warnings.append("No matching opportunity was found.")

        return AIResponse(
            success=True,
            title="Opportunity Intelligence",
            summary=f"Analysed {len(ranked)} opportunity record(s).",
            recommendations=recommendations,
            evidence=evidence,
            metrics={"opportunities_analysed": len(ranked)},
            warnings=warnings,
            data={"opportunities": ranked},
        )

    def _answer_quotations(self, question: str) -> AIResponse:
        terms = self._business_terms(question)
        quotes = self._search_supplier_quotes(terms)

        ranked = sorted(
            quotes,
            key=lambda item: (
                self._number(item.get("unit_price")),
                self._number(item.get("risk_score")),
                -self._number(item.get("quality_score")),
            ),
        )

        evidence = [
            EvidenceItem(
                source="Supplier Quotations",
                record_id=item.get("id"),
                label=item.get("supplier_name") or "Supplier quotation",
                details=(
                    f"{item.get('currency') or ''} "
                    f"{self._number(item.get('unit_price')):,.2f} per unit; "
                    f"quantity {self._number(item.get('quantity')):,.2f}; "
                    f"lead time {item.get('lead_time_days') or 0} days; "
                    f"Incoterm {item.get('incoterm') or 'Not recorded'}; "
                    f"quality {item.get('quality_score') or 0}/100; "
                    f"risk {item.get('risk_score') or 0}/100."
                ),
            )
            for item in ranked[:10]
        ]

        recommendations = []
        warnings = []

        if ranked:
            recommendations.extend(
                [
                    "Do not select on price alone; compare compliance, quality, reliability and documents.",
                    "Confirm quotation validity, MOQ, payment terms, packaging and sample availability.",
                    "Add freight, customs, biosecurity, warehouse and local delivery before approving the deal.",
                ]
            )
        else:
            recommendations.append(
                "Issue structured RFQs and record supplier quotations before comparison."
            )
            warnings.append("No matching supplier quotation was found.")

        return AIResponse(
            success=True,
            title="Quotation Comparison Intelligence",
            summary=f"Found and ranked {len(ranked)} supplier quotation(s).",
            recommendations=recommendations,
            evidence=evidence,
            metrics={"matching_quotations": len(ranked)},
            warnings=warnings,
            data={"quotations": ranked},
        )

    def _answer_shipments(self, question: str) -> AIResponse:
        terms = self._business_terms(question)
        shipments = self._search_shipments(terms)
        exceptions = [
            item
            for item in shipments
            if self._shipment_is_exception(item)
        ]

        evidence = [
            EvidenceItem(
                source="Shipments",
                record_id=item.get("id"),
                label=(
                    item.get("shipment_number")
                    or item.get("shipment_reference")
                    or "Shipment"
                ),
                details=(
                    f"Product: {item.get('product_name') or 'Not recorded'}; "
                    f"route: {item.get('origin_location') or item.get('origin_port') or ''} "
                    f"to {item.get('destination_location') or item.get('destination_port') or ''}; "
                    f"status: {item.get('status') or item.get('shipment_status') or ''}; "
                    f"ETA: {item.get('eta') or 'Not recorded'}."
                ),
            )
            for item in shipments[:10]
        ]

        recommendations = []
        warnings = []

        if exceptions:
            recommendations.extend(
                [
                    "Confirm revised ETA and the cause of each exception.",
                    "Check customs, biosecurity, document and port-release dependencies.",
                    "Assess customer delivery and inventory impact immediately.",
                ]
            )
        elif shipments:
            recommendations.append(
                "Continue monitoring ETA, documents, customs and milestone completion."
            )
        else:
            warnings.append("No matching shipment record was found.")

        return AIResponse(
            success=True,
            title="Shipment Intelligence",
            summary=(
                f"Found {len(shipments)} shipment(s), including "
                f"{len(exceptions)} exception(s)."
            ),
            recommendations=recommendations,
            evidence=evidence,
            metrics={
                "matching_shipments": len(shipments),
                "shipment_exceptions": len(exceptions),
            },
            warnings=warnings,
            data={"shipments": shipments, "exceptions": exceptions},
        )

    def _answer_inventory(self, question: str) -> AIResponse:
        terms = self._business_terms(question)
        items = self._search_inventory(terms)
        low_stock = [
            item
            for item in items
            if self._number(item.get("quantity_on_hand"))
            - self._number(item.get("quantity_reserved"))
            <= self._number(item.get("reorder_level"))
        ]

        evidence = [
            EvidenceItem(
                source="Inventory",
                record_id=item.get("id"),
                label=item.get("product_name") or "Inventory item",
                details=(
                    f"On hand: {self._number(item.get('quantity_on_hand')):,.2f} "
                    f"{item.get('unit') or ''}; "
                    f"reserved: {self._number(item.get('quantity_reserved')):,.2f}; "
                    f"warehouse: {item.get('warehouse_name') or 'Not recorded'}."
                ),
            )
            for item in items[:10]
        ]

        recommendations = []
        warnings = []

        if low_stock:
            recommendations.append(
                f"Review replenishment for {len(low_stock)} low-stock item(s)."
            )
        elif items:
            recommendations.append(
                "Inventory levels do not currently show a reorder exception for the matched records."
            )
        else:
            warnings.append("No matching inventory record was found.")

        return AIResponse(
            success=True,
            title="Inventory Intelligence",
            summary=(
                f"Found {len(items)} inventory item(s); "
                f"{len(low_stock)} require reorder review."
            ),
            recommendations=recommendations,
            evidence=evidence,
            metrics={
                "matching_inventory_items": len(items),
                "low_stock_items": len(low_stock),
            },
            warnings=warnings,
            data={"inventory": items, "low_stock": low_stock},
        )

    def _answer_products(self, question: str) -> AIResponse:
        terms = self._business_terms(question)
        products = self._search_products(terms)

        evidence = [
            EvidenceItem(
                source="Products",
                record_id=item.get("id"),
                label=item.get("name") or "Product",
                details=(
                    f"Category: {item.get('category') or 'Not recorded'}; "
                    f"origin: {item.get('country_of_origin') or 'Not recorded'}; "
                    f"packaging: {item.get('packaging') or 'Not recorded'}; "
                    f"certificates: {item.get('required_certificates') or 'Not recorded'}."
                ),
            )
            for item in products[:10]
        ]

        warnings = []
        if not products:
            warnings.append("No matching saved product was found.")

        return AIResponse(
            success=True,
            title="Product Intelligence",
            summary=f"Found {len(products)} matching product record(s).",
            recommendations=[
                "Maintain complete specifications, packaging and certificate requirements.",
                "Use the product record as the standard for buyer demand and supplier qualification.",
            ],
            evidence=evidence,
            metrics={"matching_products": len(products)},
            warnings=warnings,
            data={"products": products},
        )

    def _answer_general(self, question: str) -> AIResponse:
        response = self._answer_executive(question)
        response.title = "Dawlat AI Procurement Assistant"
        response.summary = (
            "I interpreted this as a general business question. "
            + response.summary
        )
        response.recommendations.insert(
            0,
            "Ask a more specific question about buyers, suppliers, quotations, opportunities, shipments or inventory for a focused answer.",
        )
        return response

    def _platform_metrics(self) -> dict[str, Any]:
        return {
            "opportunities_total": self._count("market_opportunities"),
            "customers_total": self._count("customers"),
            "suppliers_total": self._count("suppliers"),
            "products_total": self._count("products"),
            "rfqs_total": self._count("rfqs"),
            "supplier_quotes_total": self._count("supplier_quotes"),
            "logistics_quotes_total": self._count("logistics_quotes"),
            "warehouse_quotes_total": self._count("warehouse_quotes"),
            "landed_costs_total": self._count("landed_costs"),
            "shipments_total": self._count(
                "shipments",
                "COALESCE(is_deleted, 0) = 0",
            ),
            "inventory_items_total": self._count("inventory_items"),
        }

    def _ranked_opportunities(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._rows(
            """
            SELECT *
            FROM market_opportunities
            ORDER BY id DESC
            """,
            table="market_opportunities",
        )
        ranked = [self._enrich_opportunity(item) for item in rows]
        ranked.sort(key=lambda item: item["ai_score"], reverse=True)
        return ranked[:limit]

    def _enrich_opportunity(self, item: dict[str, Any]) -> dict[str, Any]:
        urgency_bonus = {
            "Low": 0,
            "Medium": 5,
            "High": 10,
            "Critical": 15,
        }.get(item.get("urgency"), 0)

        score = round(
            self._number(item.get("demand_score")) * 0.40
            + self._number(item.get("confidence_score")) * 0.35
            + (100 - self._number(item.get("competition_score"))) * 0.25
            + urgency_bonus
        )
        enriched = dict(item)
        enriched["ai_score"] = max(0, min(100, score))
        return enriched

    def _shipment_exceptions(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._rows(
            """
            SELECT *
            FROM shipments
            WHERE COALESCE(is_deleted, 0) = 0
            ORDER BY id DESC
            """,
            table="shipments",
        )
        return [item for item in rows if self._shipment_is_exception(item)][
            :limit
        ]

    def _shipment_is_exception(self, item: dict[str, Any]) -> bool:
        status = (
            item.get("shipment_status")
            or item.get("status")
            or ""
        )
        eta = self._parse_date(item.get("eta"))
        terminal = status in {"Delivered", "Completed", "Cancelled"}
        overdue = bool(eta and eta < date.today() and not terminal)

        return bool(
            status in {
                "Delayed",
                "Biosecurity Hold",
                "Inspection Hold",
            }
            or item.get("delay_reason")
            or self._number(item.get("delay_days")) > 0
            or overdue
        )

    def _expiring_quotes(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._rows(
            """
            SELECT *
            FROM supplier_quotes
            ORDER BY id DESC
            """,
            table="supplier_quotes",
        )
        today = date.today()
        result = []
        for item in rows:
            expiry = self._parse_date(item.get("quotation_valid_until"))
            if expiry and (expiry - today).days <= 14:
                result.append(item)
        return result[:limit]

    def _search_suppliers(self, terms: list[str]) -> list[dict[str, Any]]:
        return self._search_table(
            "suppliers",
            ["company_name", "category", "country", "notes"],
            terms,
            order_by="company_name",
        )

    def _search_customers(self, terms: list[str]) -> list[dict[str, Any]]:
        return self._search_table(
            "customers",
            [
                "company_name",
                "customer_type",
                "country",
                "city",
                "products_of_interest",
                "estimated_demand",
                "notes",
            ],
            terms,
            order_by="company_name",
        )

    def _search_products(self, terms: list[str]) -> list[dict[str, Any]]:
        return self._search_table(
            "products",
            [
                "name",
                "category",
                "description",
                "specifications",
                "packaging",
                "required_certificates",
            ],
            terms,
            order_by="name",
        )

    def _search_opportunities(self, terms: list[str]) -> list[dict[str, Any]]:
        return self._search_table(
            "market_opportunities",
            [
                "title",
                "product",
                "industry",
                "country",
                "city",
                "buyer_company",
                "opportunity_type",
                "notes",
            ],
            terms,
            order_by="id DESC",
        )

    def _search_supplier_quotes(
        self,
        terms: list[str],
    ) -> list[dict[str, Any]]:
        return self._search_table(
            "supplier_quotes",
            [
                "supplier_name",
                "quote_reference",
                "incoterm",
                "packaging",
                "certificates",
                "payment_terms",
                "notes",
            ],
            terms,
            order_by="id DESC",
        )

    def _search_shipments(self, terms: list[str]) -> list[dict[str, Any]]:
        return self._search_table(
            "shipments",
            [
                "shipment_number",
                "shipment_reference",
                "shipment_name",
                "supplier_name",
                "customer_name",
                "product_name",
                "origin_country",
                "origin_location",
                "origin_port",
                "destination_country",
                "destination_location",
                "destination_port",
                "status",
                "shipment_status",
                "booking_number",
                "container_number",
                "tracking_number",
                "notes",
            ],
            terms,
            extra_condition="COALESCE(is_deleted, 0) = 0",
            order_by="id DESC",
        )

    def _search_inventory(self, terms: list[str]) -> list[dict[str, Any]]:
        return self._search_table(
            "inventory_items",
            [
                "product_name",
                "sku",
                "warehouse_name",
                "warehouse_location",
                "country_of_origin",
                "supplier_name",
                "status",
                "notes",
            ],
            terms,
            order_by="id DESC",
        )

    def _search_table(
        self,
        table: str,
        columns: list[str],
        terms: list[str],
        *,
        extra_condition: str | None = None,
        order_by: str = "id DESC",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self._table_exists(table):
            return []

        available = self._table_columns(table)
        searchable = [column for column in columns if column in available]

        conditions = []
        parameters: list[Any] = []

        if extra_condition:
            conditions.append(extra_condition)

        if terms and searchable:
            for term in terms:
                conditions.append(
                    "("
                    + " OR ".join(
                        f"LOWER(COALESCE({column}, '')) LIKE ?"
                        for column in searchable
                    )
                    + ")"
                )
                parameters.extend(
                    [f"%{term.lower()}%"] * len(searchable)
                )

        where_clause = (
            " WHERE " + " AND ".join(conditions)
            if conditions
            else ""
        )

        safe_order = order_by if order_by else "id DESC"
        query = (
            f"SELECT * FROM {table}"
            f"{where_clause} ORDER BY {safe_order} LIMIT ?"
        )
        parameters.append(limit)
        return self._rows(query, tuple(parameters), table=table)

    def _detect_intent(self, question: str) -> str:
        text = question.lower()

        groups = {
            "shipment": (
                "shipment",
                "shipping",
                "container",
                "vessel",
                "eta",
                "etd",
                "customs",
                "biosecurity",
                "tracking",
                "delivery",
            ),
            "quotation": (
                "quotation",
                "quote",
                "price",
                "compare",
                "moq",
                "incoterm",
                "payment term",
                "lead time",
            ),
            "supplier": (
                "supplier",
                "manufacturer",
                "factory",
                "exporter",
                "source",
                "sourcing",
                "certificate",
            ),
            "customer": (
                "customer",
                "buyer",
                "wholesaler",
                "retailer",
                "supermarket",
                "hospital",
                "hotel",
                "restaurant",
                "school",
                "university",
                "tender",
                "demand",
                "needs",
            ),
            "opportunity": (
                "opportunity",
                "profit",
                "margin",
                "gap",
                "shortage",
                "pursue",
                "market",
            ),
            "inventory": (
                "inventory",
                "stock",
                "warehouse stock",
                "reorder",
                "available quantity",
            ),
            "product": (
                "product",
                "rice",
                "cricket",
                "automotive",
                "medical",
                "st25",
                "basmati",
                "jasmine",
            ),
            "executive": (
                "today",
                "priority",
                "priorities",
                "summary",
                "overview",
                "executive",
                "what should",
                "next action",
                "business status",
            ),
        }

        scores = {
            intent: sum(1 for keyword in keywords if keyword in text)
            for intent, keywords in groups.items()
        }
        best_intent = max(scores, key=scores.get)
        return best_intent if scores[best_intent] else "general"

    def _business_terms(self, question: str) -> list[str]:
        text = question.lower()
        known_terms = (
            "st25",
            "rice",
            "basmati",
            "jasmine",
            "cricket",
            "automotive",
            "auto parts",
            "medical",
            "hospital",
            "pharmaceutical",
            "food",
            "vietnam",
            "pakistan",
            "india",
            "china",
            "australia",
            "melbourne",
            "supplier",
            "customer",
            "buyer",
        )
        matched = [term for term in known_terms if term in text]
        return self._unique(matched)

    def _count(
        self,
        table: str,
        condition: str | None = None,
    ) -> int:
        if not self._table_exists(table):
            return 0
        where = f" WHERE {condition}" if condition else ""
        with get_connection() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS total FROM {table}{where}"
            ).fetchone()
        return int(row["total"]) if row else 0

    def _rows(
        self,
        query: str,
        parameters: tuple[Any, ...] = (),
        *,
        table: str | None = None,
    ) -> list[dict[str, Any]]:
        if table and not self._table_exists(table):
            return []
        try:
            with get_connection() as connection:
                rows = connection.execute(query, parameters).fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []

    def _table_exists(self, table: str) -> bool:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = ?
                """,
                (table,),
            ).fetchone()
        return row is not None

    def _table_columns(self, table: str) -> set[str]:
        if not self._table_exists(table):
            return set()
        with get_connection() as connection:
            rows = connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        return {str(row["name"]) for row in rows}

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if not value:
            return None
        text = str(value).strip()[:10]
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _number(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _unique(values: Iterable[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))


_engine = AIProcurementEngine()


def answer_question(question: str) -> AIResponse:
    """Public service function used by the Streamlit AI Assistant."""

    return _engine.answer(question)


def build_ai_context(limit_per_domain: int = 25) -> dict[str, Any]:
    """Public context builder for future external AI model integration."""

    return _engine.build_context(limit_per_domain=limit_per_domain)