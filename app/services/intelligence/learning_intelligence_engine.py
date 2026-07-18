"""
Learning Intelligence Engine.

Creates governed organisational learning for the Dawlat AI Procurement &
Global Trade Intelligence Platform.

The engine learns from completed or materially progressed business outcomes:
- supplier delivery and quality performance;
- buyer payment and conversion behaviour;
- shipment delay and route performance;
- quotation and landed-cost accuracy;
- realised versus expected margin;
- opportunity conversion;
- recommendation outcome quality;
- recurring risk and trust failures.

Important governance principles:
- learning records are evidence-based and auditable;
- historical data influences future decisions but never replaces controls;
- no model may reduce mandatory compliance, trust or payment safeguards;
- learning recommendations remain explainable and human-reviewable;
- poor-quality or incomplete observations receive lower confidence;
- the engine does not autonomously modify commercial records or execute deals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from statistics import mean
from typing import Any, Iterable
from uuid import uuid4

from database.connection import get_connection
from services.ai_assistant_service import build_ai_context


class LearningSubjectType(str, Enum):
    SUPPLIER = "Supplier"
    BUYER = "Buyer"
    PRODUCT = "Product"
    COUNTRY = "Country"
    ROUTE = "Route"
    SHIPPING_LINE = "Shipping Line"
    WAREHOUSE = "Warehouse"
    OPPORTUNITY = "Opportunity"
    RECOMMENDATION = "Recommendation"
    WORKFLOW = "Workflow"


class LearningSignalType(str, Enum):
    DELIVERY = "Delivery Performance"
    QUALITY = "Quality Performance"
    PAYMENT = "Payment Performance"
    COST_ACCURACY = "Cost Accuracy"
    MARGIN_ACCURACY = "Margin Accuracy"
    QUOTATION = "Quotation Performance"
    CONVERSION = "Conversion Performance"
    RISK = "Risk Outcome"
    TRUST = "Trust Outcome"
    COMPLIANCE = "Compliance Outcome"
    RECOMMENDATION = "Recommendation Outcome"
    RELATIONSHIP = "Relationship Outcome"


class LearningDirection(str, Enum):
    POSITIVE = "Positive"
    NEGATIVE = "Negative"
    NEUTRAL = "Neutral"


@dataclass(frozen=True)
class LearningObservation:
    observation_id: str
    subject_type: LearningSubjectType
    subject_id: str
    subject_name: str
    signal_type: LearningSignalType
    direction: LearningDirection
    score: float
    weight: float
    confidence_score: int
    evidence_summary: str
    source_type: str
    source_id: str | None = None
    workflow_id: str | None = None
    occurred_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearnedMetric:
    subject_type: LearningSubjectType
    subject_id: str
    subject_name: str
    signal_type: LearningSignalType
    observation_count: int
    weighted_score: float
    confidence_score: int
    trend: str
    last_observed_at: str


@dataclass(frozen=True)
class LearningRecommendation:
    priority: int
    title: str
    action: str
    reason: str
    owner_role: str
    approval_required: bool = False


@dataclass
class LearningReport:
    generated_at: str
    observations_created: int
    learned_metrics: list[LearnedMetric] = field(default_factory=list)
    recommendations: list[LearningRecommendation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""


def create_learning_tables() -> None:
    """Create learning observation and metric tables."""

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id TEXT NOT NULL UNIQUE,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                subject_name TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                score REAL NOT NULL,
                weight REAL NOT NULL,
                confidence_score INTEGER NOT NULL,
                evidence_summary TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT,
                workflow_id TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                occurred_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                subject_name TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                observation_count INTEGER NOT NULL,
                weighted_score REAL NOT NULL,
                confidence_score INTEGER NOT NULL,
                trend TEXT NOT NULL,
                last_observed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(subject_type, subject_id, signal_type)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                subject_type TEXT,
                subject_id TEXT,
                details_json TEXT NOT NULL DEFAULT '{}',
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_learning_subject
            ON learning_observations(subject_type, subject_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_learning_signal
            ON learning_observations(signal_type, occurred_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_learning_workflow
            ON learning_observations(workflow_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_learning_metric_score
            ON learning_metrics(signal_type, weighted_score DESC)
            """
        )

        connection.commit()


class LearningIntelligenceEngine:
    """Evidence-based organisational learning engine."""

    def __init__(self) -> None:
        create_learning_tables()

    def run_learning_cycle(
        self,
        *,
        actor: str = "Learning Intelligence Engine",
        limit_per_domain: int = 1000,
    ) -> LearningReport:
        context = build_ai_context(
            limit_per_domain=limit_per_domain
        )

        observations: list[LearningObservation] = []
        warnings: list[str] = []

        observations.extend(
            self._supplier_observations(
                context.get("suppliers", []),
                context.get("supplier_quotes", []),
                context.get("shipments", []),
            )
        )
        observations.extend(
            self._buyer_observations(
                context.get("customers", []),
                context.get("opportunities", []),
            )
        )
        observations.extend(
            self._shipment_observations(
                context.get("shipments", [])
            )
        )
        observations.extend(
            self._commercial_observations(
                context.get("landed_costs", [])
            )
        )
        observations.extend(
            self._opportunity_observations(
                context.get("opportunities", [])
            )
        )

        observations = self._deduplicate(observations)
        created_count = self._persist_observations(
            observations,
            actor=actor,
        )

        metrics = self.rebuild_metrics(actor=actor)
        recommendations = self._recommendations(metrics)

        if not observations:
            warnings.append(
                "No new learning observations were generated. More completed "
                "deal, shipment, payment and margin history is required."
            )

        if metrics and all(
            item.confidence_score < 60
            for item in metrics
        ):
            warnings.append(
                "Current learned metrics have limited confidence and should "
                "not materially override expert judgement."
            )

        summary = (
            f"Created {created_count} new learning observation(s) and "
            f"maintained {len(metrics)} learned metric(s). "
            f"Generated {len(recommendations)} improvement recommendation(s)."
        )

        self._audit(
            action="Learning Cycle Completed",
            actor=actor,
            details={
                "observations_created": created_count,
                "metrics_count": len(metrics),
                "recommendations_count": len(recommendations),
                "warnings": warnings,
            },
        )

        return LearningReport(
            generated_at=_now(),
            observations_created=created_count,
            learned_metrics=metrics,
            recommendations=recommendations,
            warnings=warnings,
            summary=summary,
        )

    def record_observation(
        self,
        observation: LearningObservation,
        *,
        actor: str = "System",
    ) -> bool:
        """Persist one externally supplied observation."""

        created = self._persist_observations(
            [observation],
            actor=actor,
        )
        return created == 1

    def rebuild_metrics(
        self,
        *,
        actor: str = "Learning Intelligence Engine",
    ) -> list[LearnedMetric]:
        """Recalculate all aggregate learned metrics."""

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM learning_observations
                ORDER BY occurred_at ASC, id ASC
                """
            ).fetchall()

        grouped: dict[
            tuple[str, str, str],
            list[dict[str, Any]],
        ] = {}

        for row in rows:
            record = dict(row)
            key = (
                record["subject_type"],
                record["subject_id"],
                record["signal_type"],
            )
            grouped.setdefault(key, []).append(record)

        metrics: list[LearnedMetric] = []

        with get_connection() as connection:
            for key, items in grouped.items():
                subject_type_value, subject_id, signal_type_value = key

                total_weight = sum(
                    max(0.01, float(item["weight"]))
                    for item in items
                )
                weighted_score = sum(
                    float(item["score"])
                    * max(0.01, float(item["weight"]))
                    for item in items
                ) / total_weight

                confidence = self._metric_confidence(items)
                trend = self._trend(items)
                last = items[-1]
                subject_name = last["subject_name"]

                connection.execute(
                    """
                    INSERT INTO learning_metrics (
                        subject_type,
                        subject_id,
                        subject_name,
                        signal_type,
                        observation_count,
                        weighted_score,
                        confidence_score,
                        trend,
                        last_observed_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(
                        subject_type,
                        subject_id,
                        signal_type
                    )
                    DO UPDATE SET
                        subject_name = excluded.subject_name,
                        observation_count = excluded.observation_count,
                        weighted_score = excluded.weighted_score,
                        confidence_score = excluded.confidence_score,
                        trend = excluded.trend,
                        last_observed_at = excluded.last_observed_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        subject_type_value,
                        subject_id,
                        subject_name,
                        signal_type_value,
                        len(items),
                        round(weighted_score, 2),
                        confidence,
                        trend,
                        last["occurred_at"],
                        _now(),
                    ),
                )

                metrics.append(
                    LearnedMetric(
                        subject_type=LearningSubjectType(
                            subject_type_value
                        ),
                        subject_id=subject_id,
                        subject_name=subject_name,
                        signal_type=LearningSignalType(
                            signal_type_value
                        ),
                        observation_count=len(items),
                        weighted_score=round(
                            weighted_score,
                            2,
                        ),
                        confidence_score=confidence,
                        trend=trend,
                        last_observed_at=last["occurred_at"],
                    )
                )

            connection.commit()

        metrics.sort(
            key=lambda item: (
                item.subject_type.value,
                item.subject_name.lower(),
                item.signal_type.value,
            )
        )

        self._audit(
            action="Learning Metrics Rebuilt",
            actor=actor,
            details={
                "metrics_count": len(metrics),
            },
        )

        return metrics

    def get_subject_metrics(
        self,
        *,
        subject_type: LearningSubjectType,
        subject_id: str,
    ) -> list[LearnedMetric]:
        """Return learned metrics for one subject."""

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM learning_metrics
                WHERE subject_type = ?
                  AND subject_id = ?
                ORDER BY signal_type
                """,
                (
                    subject_type.value,
                    subject_id,
                ),
            ).fetchall()

        return [
            _row_to_metric(row)
            for row in rows
        ]

    def rank_subjects(
        self,
        *,
        subject_type: LearningSubjectType,
        signal_type: LearningSignalType,
        minimum_confidence: int = 50,
        limit: int = 20,
    ) -> list[LearnedMetric]:
        """Rank subjects using a selected learned metric."""

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM learning_metrics
                WHERE subject_type = ?
                  AND signal_type = ?
                  AND confidence_score >= ?
                ORDER BY
                    weighted_score DESC,
                    confidence_score DESC,
                    observation_count DESC
                LIMIT ?
                """,
                (
                    subject_type.value,
                    signal_type.value,
                    minimum_confidence,
                    max(1, min(limit, 1000)),
                ),
            ).fetchall()

        return [
            _row_to_metric(row)
            for row in rows
        ]

    def learning_adjustment(
        self,
        *,
        subject_type: LearningSubjectType,
        subject_id: str,
        signal_types: Iterable[LearningSignalType],
        maximum_adjustment: float = 15.0,
    ) -> dict[str, Any]:
        """
        Return a bounded learning adjustment for future scoring engines.

        The adjustment is deliberately limited and may never bypass mandatory
        risk, trust, compliance, approval or payment controls.
        """

        requested = {
            item.value
            for item in signal_types
        }

        metrics = [
            item
            for item in self.get_subject_metrics(
                subject_type=subject_type,
                subject_id=subject_id,
            )
            if item.signal_type.value in requested
        ]

        eligible = [
            item
            for item in metrics
            if item.confidence_score >= 60
        ]

        if not eligible:
            return {
                "adjustment": 0.0,
                "confidence_score": 0,
                "metrics_used": [],
                "explanation": (
                    "No sufficiently reliable historical learning is available."
                ),
            }

        average_score = mean(
            item.weighted_score
            for item in eligible
        )
        average_confidence = round(
            mean(
                item.confidence_score
                for item in eligible
            )
        )

        normalized = (
            (average_score - 50.0) / 50.0
        ) * maximum_adjustment
        adjustment = max(
            -maximum_adjustment,
            min(maximum_adjustment, normalized),
        )

        return {
            "adjustment": round(adjustment, 2),
            "confidence_score": average_confidence,
            "metrics_used": [
                {
                    "signal_type": item.signal_type.value,
                    "score": item.weighted_score,
                    "confidence": item.confidence_score,
                    "observations": item.observation_count,
                }
                for item in eligible
            ],
            "explanation": (
                "Bounded historical adjustment only. Mandatory controls "
                "remain authoritative."
            ),
        }

    @staticmethod
    def _supplier_observations(
        suppliers: list[dict[str, Any]],
        quotes: list[dict[str, Any]],
        shipments: list[dict[str, Any]],
    ) -> list[LearningObservation]:
        results: list[LearningObservation] = []

        supplier_by_name = {
            str(item.get("company_name") or "").strip().lower(): item
            for item in suppliers
            if item.get("company_name")
        }

        for shipment in shipments:
            supplier_name = str(
                shipment.get("supplier_name") or ""
            ).strip()

            if not supplier_name:
                continue

            supplier = supplier_by_name.get(
                supplier_name.lower(),
                {},
            )
            supplier_id = str(
                supplier.get("id")
                or supplier_name.lower()
            )

            status = str(
                shipment.get("shipment_status")
                or shipment.get("status")
                or ""
            )
            delay_days = _number(
                shipment.get("delay_days")
            )
            delayed = bool(
                delay_days > 0
                or shipment.get("delay_reason")
                or status
                in {
                    "Delayed",
                    "Biosecurity Hold",
                    "Inspection Hold",
                }
            )

            if status in {
                "Delivered",
                "Completed",
            }:
                score = max(
                    0.0,
                    min(
                        100.0,
                        100.0 - delay_days * 8.0,
                    ),
                )
                direction = (
                    LearningDirection.POSITIVE
                    if not delayed
                    else LearningDirection.NEGATIVE
                )

                results.append(
                    _observation(
                        subject_type=LearningSubjectType.SUPPLIER,
                        subject_id=supplier_id,
                        subject_name=supplier_name,
                        signal_type=LearningSignalType.DELIVERY,
                        direction=direction,
                        score=score,
                        weight=1.0,
                        confidence_score=85,
                        evidence_summary=(
                            f"Shipment {shipment.get('shipment_number') or shipment.get('id')} "
                            f"completed with {delay_days:g} delay day(s)."
                        ),
                        source_type="Shipment",
                        source_id=_optional_string(
                            shipment.get("id")
                        ),
                        workflow_id=_optional_string(
                            shipment.get("workflow_id")
                        ),
                    )
                )

            quality_status = str(
                shipment.get("quality_status")
                or shipment.get("inspection_status")
                or ""
            ).lower()

            if quality_status:
                passed = quality_status in {
                    "passed",
                    "approved",
                    "accepted",
                    "compliant",
                }
                results.append(
                    _observation(
                        subject_type=LearningSubjectType.SUPPLIER,
                        subject_id=supplier_id,
                        subject_name=supplier_name,
                        signal_type=LearningSignalType.QUALITY,
                        direction=(
                            LearningDirection.POSITIVE
                            if passed
                            else LearningDirection.NEGATIVE
                        ),
                        score=100.0 if passed else 20.0,
                        weight=1.2,
                        confidence_score=80,
                        evidence_summary=(
                            f"Recorded quality or inspection status: "
                            f"{quality_status}."
                        ),
                        source_type="Shipment",
                        source_id=_optional_string(
                            shipment.get("id")
                        ),
                    )
                )

        for quote in quotes:
            supplier_name = str(
                quote.get("supplier_name") or ""
            ).strip()
            if not supplier_name:
                continue

            supplier = supplier_by_name.get(
                supplier_name.lower(),
                {},
            )
            supplier_id = str(
                supplier.get("id")
                or supplier_name.lower()
            )

            risk_score = _number(
                quote.get("risk_score")
            )
            valid_price = _number(
                quote.get("unit_price")
            ) > 0
            lead_time = _number(
                quote.get("lead_time_days")
            )

            score = 40.0
            score += 30.0 if valid_price else 0.0
            score += 15.0 if lead_time > 0 else 0.0
            score += max(
                0.0,
                15.0 - risk_score * 0.15,
            )

            results.append(
                _observation(
                    subject_type=LearningSubjectType.SUPPLIER,
                    subject_id=supplier_id,
                    subject_name=supplier_name,
                    signal_type=LearningSignalType.QUOTATION,
                    direction=(
                        LearningDirection.POSITIVE
                        if score >= 70
                        else LearningDirection.NEUTRAL
                    ),
                    score=min(100.0, score),
                    weight=0.6,
                    confidence_score=60,
                    evidence_summary=(
                        "Quotation completeness and recorded risk were assessed."
                    ),
                    source_type="Supplier Quotation",
                    source_id=_optional_string(
                        quote.get("id")
                    ),
                )
            )

        return results

    @staticmethod
    def _buyer_observations(
        customers: list[dict[str, Any]],
        opportunities: list[dict[str, Any]],
    ) -> list[LearningObservation]:
        results: list[LearningObservation] = []

        opportunity_by_buyer: dict[str, list[dict[str, Any]]] = {}
        for item in opportunities:
            buyer = str(
                item.get("buyer_company") or ""
            ).strip().lower()
            if buyer:
                opportunity_by_buyer.setdefault(
                    buyer,
                    [],
                ).append(item)

        for customer in customers:
            customer_id = str(
                customer.get("id")
                or customer.get("company_name")
                or "unknown"
            )
            name = str(
                customer.get("company_name")
                or customer_id
            )
            lead_status = str(
                customer.get("lead_status") or ""
            )
            credit_status = str(
                customer.get("credit_status") or ""
            )

            conversion_score = {
                "Prospect": 20.0,
                "Contacted": 35.0,
                "Qualified": 55.0,
                "Quotation Sent": 65.0,
                "Accepted": 85.0,
                "Customer": 100.0,
            }.get(lead_status, 30.0)

            results.append(
                _observation(
                    subject_type=LearningSubjectType.BUYER,
                    subject_id=customer_id,
                    subject_name=name,
                    signal_type=LearningSignalType.CONVERSION,
                    direction=(
                        LearningDirection.POSITIVE
                        if conversion_score >= 70
                        else LearningDirection.NEUTRAL
                    ),
                    score=conversion_score,
                    weight=0.8,
                    confidence_score=65,
                    evidence_summary=(
                        f"Current recorded buyer lifecycle status: {lead_status or 'Unknown'}."
                    ),
                    source_type="Customer",
                    source_id=_optional_string(
                        customer.get("id")
                    ),
                )
            )

            payment_score = {
                "Approved": 90.0,
                "Good": 90.0,
                "Assessed": 75.0,
                "Pending": 45.0,
                "Rejected": 10.0,
                "Bad": 10.0,
            }.get(credit_status, 40.0)

            results.append(
                _observation(
                    subject_type=LearningSubjectType.BUYER,
                    subject_id=customer_id,
                    subject_name=name,
                    signal_type=LearningSignalType.PAYMENT,
                    direction=(
                        LearningDirection.POSITIVE
                        if payment_score >= 70
                        else LearningDirection.NEGATIVE
                        if payment_score < 30
                        else LearningDirection.NEUTRAL
                    ),
                    score=payment_score,
                    weight=1.0,
                    confidence_score=60,
                    evidence_summary=(
                        f"Recorded buyer credit status: {credit_status or 'Unknown'}."
                    ),
                    source_type="Customer",
                    source_id=_optional_string(
                        customer.get("id")
                    ),
                )
            )

        return results

    @staticmethod
    def _shipment_observations(
        shipments: list[dict[str, Any]],
    ) -> list[LearningObservation]:
        results: list[LearningObservation] = []

        for shipment in shipments:
            origin = str(
                shipment.get("origin_port")
                or shipment.get("origin_country")
                or "Unknown Origin"
            )
            destination = str(
                shipment.get("destination_port")
                or shipment.get("destination_country")
                or "Unknown Destination"
            )
            route_name = f"{origin} → {destination}"
            route_id = route_name.lower()

            status = str(
                shipment.get("shipment_status")
                or shipment.get("status")
                or ""
            )
            delay_days = _number(
                shipment.get("delay_days")
            )
            completed = status in {
                "Delivered",
                "Completed",
            }

            if completed:
                score = max(
                    0.0,
                    min(
                        100.0,
                        100.0 - delay_days * 10.0,
                    ),
                )

                results.append(
                    _observation(
                        subject_type=LearningSubjectType.ROUTE,
                        subject_id=route_id,
                        subject_name=route_name,
                        signal_type=LearningSignalType.DELIVERY,
                        direction=(
                            LearningDirection.POSITIVE
                            if delay_days <= 1
                            else LearningDirection.NEGATIVE
                        ),
                        score=score,
                        weight=1.0,
                        confidence_score=80,
                        evidence_summary=(
                            f"Completed shipment with {delay_days:g} delay day(s)."
                        ),
                        source_type="Shipment",
                        source_id=_optional_string(
                            shipment.get("id")
                        ),
                        workflow_id=_optional_string(
                            shipment.get("workflow_id")
                        ),
                    )
                )

            shipping_line = str(
                shipment.get("shipping_line") or ""
            ).strip()

            if shipping_line and completed:
                results.append(
                    _observation(
                        subject_type=LearningSubjectType.SHIPPING_LINE,
                        subject_id=shipping_line.lower(),
                        subject_name=shipping_line,
                        signal_type=LearningSignalType.DELIVERY,
                        direction=(
                            LearningDirection.POSITIVE
                            if delay_days <= 1
                            else LearningDirection.NEGATIVE
                        ),
                        score=max(
                            0.0,
                            min(
                                100.0,
                                100.0 - delay_days * 10.0,
                            ),
                        ),
                        weight=1.0,
                        confidence_score=80,
                        evidence_summary=(
                            f"Shipping-line delivery result recorded for route {route_name}."
                        ),
                        source_type="Shipment",
                        source_id=_optional_string(
                            shipment.get("id")
                        ),
                    )
                )

        return results

    @staticmethod
    def _commercial_observations(
        landed_costs: list[dict[str, Any]],
    ) -> list[LearningObservation]:
        results: list[LearningObservation] = []

        for item in landed_costs:
            product_name = str(
                item.get("product_name")
                or item.get("name")
                or "Unknown Product"
            )
            product_id = str(
                item.get("product_id")
                or product_name.lower()
            )

            expected_margin = _number(
                item.get("gross_margin_percent")
            )
            actual_margin = _number(
                item.get("actual_margin_percent")
                or item.get("realised_margin_percent")
            )

            if actual_margin:
                difference = abs(
                    actual_margin - expected_margin
                )
                score = max(
                    0.0,
                    100.0 - difference * 5.0,
                )

                results.append(
                    _observation(
                        subject_type=LearningSubjectType.PRODUCT,
                        subject_id=product_id,
                        subject_name=product_name,
                        signal_type=LearningSignalType.MARGIN_ACCURACY,
                        direction=(
                            LearningDirection.POSITIVE
                            if difference <= 2
                            else LearningDirection.NEGATIVE
                        ),
                        score=score,
                        weight=1.3,
                        confidence_score=90,
                        evidence_summary=(
                            f"Expected margin {expected_margin:.2f}% versus "
                            f"actual margin {actual_margin:.2f}%."
                        ),
                        source_type="Landed Cost",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

            estimated_cost = _number(
                item.get("landed_cost_per_unit")
            )
            actual_cost = _number(
                item.get("actual_landed_cost_per_unit")
            )

            if estimated_cost > 0 and actual_cost > 0:
                variance_percent = abs(
                    actual_cost - estimated_cost
                ) / estimated_cost * 100.0
                score = max(
                    0.0,
                    100.0 - variance_percent * 4.0,
                )

                results.append(
                    _observation(
                        subject_type=LearningSubjectType.PRODUCT,
                        subject_id=product_id,
                        subject_name=product_name,
                        signal_type=LearningSignalType.COST_ACCURACY,
                        direction=(
                            LearningDirection.POSITIVE
                            if variance_percent <= 3
                            else LearningDirection.NEGATIVE
                        ),
                        score=score,
                        weight=1.2,
                        confidence_score=90,
                        evidence_summary=(
                            f"Estimated versus actual landed cost variance: "
                            f"{variance_percent:.2f}%."
                        ),
                        source_type="Landed Cost",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

        return results

    @staticmethod
    def _opportunity_observations(
        opportunities: list[dict[str, Any]],
    ) -> list[LearningObservation]:
        results: list[LearningObservation] = []

        for item in opportunities:
            status = str(
                item.get("status") or ""
            )
            opportunity_id = str(
                item.get("id")
                or item.get("title")
                or "unknown"
            )
            title = str(
                item.get("title")
                or opportunity_id
            )

            score = {
                "Won": 100.0,
                "Converted": 100.0,
                "Approved": 85.0,
                "In Progress": 60.0,
                "Researching": 40.0,
                "Rejected": 20.0,
                "Lost": 0.0,
                "Cancelled": 0.0,
            }.get(status, 40.0)

            results.append(
                _observation(
                    subject_type=LearningSubjectType.OPPORTUNITY,
                    subject_id=opportunity_id,
                    subject_name=title,
                    signal_type=LearningSignalType.CONVERSION,
                    direction=(
                        LearningDirection.POSITIVE
                        if score >= 80
                        else LearningDirection.NEGATIVE
                        if score <= 20
                        else LearningDirection.NEUTRAL
                    ),
                    score=score,
                    weight=1.0,
                    confidence_score=70,
                    evidence_summary=(
                        f"Recorded opportunity status: {status or 'Unknown'}."
                    ),
                    source_type="Market Opportunity",
                    source_id=_optional_string(
                        item.get("id")
                    ),
                )
            )

        return results

    def _persist_observations(
        self,
        observations: list[LearningObservation],
        *,
        actor: str,
    ) -> int:
        created = 0

        with get_connection() as connection:
            for item in observations:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO learning_observations (
                        observation_id,
                        subject_type,
                        subject_id,
                        subject_name,
                        signal_type,
                        direction,
                        score,
                        weight,
                        confidence_score,
                        evidence_summary,
                        source_type,
                        source_id,
                        workflow_id,
                        metadata_json,
                        occurred_at,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.observation_id,
                        item.subject_type.value,
                        item.subject_id,
                        item.subject_name,
                        item.signal_type.value,
                        item.direction.value,
                        item.score,
                        item.weight,
                        item.confidence_score,
                        item.evidence_summary,
                        item.source_type,
                        item.source_id,
                        item.workflow_id,
                        json.dumps(
                            item.metadata,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        item.occurred_at,
                        _now(),
                    ),
                )
                created += cursor.rowcount

            connection.commit()

        if created:
            self._audit(
                action="Learning Observations Persisted",
                actor=actor,
                details={
                    "created_count": created,
                },
            )

        return created

    @staticmethod
    def _deduplicate(
        observations: list[LearningObservation],
    ) -> list[LearningObservation]:
        unique: dict[
            tuple[str, str, str, str, str | None],
            LearningObservation,
        ] = {}

        for item in observations:
            key = (
                item.subject_type.value,
                item.subject_id,
                item.signal_type.value,
                item.source_type,
                item.source_id,
            )

            current = unique.get(key)

            if (
                current is None
                or item.confidence_score > current.confidence_score
            ):
                unique[key] = item

        return list(unique.values())

    @staticmethod
    def _metric_confidence(
        items: list[dict[str, Any]],
    ) -> int:
        count_score = min(
            45,
            len(items) * 9,
        )
        average_observation_confidence = mean(
            int(item["confidence_score"])
            for item in items
        )
        consistency = _consistency_score(
            [
                float(item["score"])
                for item in items
            ]
        )

        score = (
            count_score
            + average_observation_confidence * 0.35
            + consistency * 0.20
        )

        return max(
            0,
            min(100, round(score)),
        )

    @staticmethod
    def _trend(
        items: list[dict[str, Any]],
    ) -> str:
        if len(items) < 3:
            return "Insufficient History"

        recent = [
            float(item["score"])
            for item in items[-3:]
        ]
        earlier = [
            float(item["score"])
            for item in items[:-3]
        ]

        if not earlier:
            return "Stable"

        difference = mean(recent) - mean(earlier)

        if difference >= 8:
            return "Improving"
        if difference <= -8:
            return "Declining"
        return "Stable"

    @staticmethod
    def _recommendations(
        metrics: list[LearnedMetric],
    ) -> list[LearningRecommendation]:
        recommendations: list[LearningRecommendation] = []
        priority = 1

        for item in sorted(
            metrics,
            key=lambda metric: (
                metric.weighted_score,
                -metric.confidence_score,
            ),
        ):
            if item.confidence_score < 60:
                continue

            if item.weighted_score < 45:
                recommendations.append(
                    LearningRecommendation(
                        priority=priority,
                        title=(
                            f"Review {item.subject_name}"
                        ),
                        action=(
                            f"Review {item.subject_type.value.lower()} "
                            f"{item.subject_name} because "
                            f"{item.signal_type.value.lower()} scored "
                            f"{item.weighted_score:.1f}/100."
                        ),
                        reason=(
                            f"Historical trend: {item.trend}; "
                            f"confidence: {item.confidence_score}/100."
                        ),
                        owner_role=_owner_for_metric(
                            item.signal_type
                        ),
                        approval_required=True,
                    )
                )
                priority += 1

            elif (
                item.weighted_score >= 85
                and item.observation_count >= 3
            ):
                recommendations.append(
                    LearningRecommendation(
                        priority=priority,
                        title=(
                            f"Prefer proven {item.subject_type.value.lower()}"
                        ),
                        action=(
                            f"Consider {item.subject_name} as a preferred "
                            f"option for {item.signal_type.value.lower()}, "
                            "subject to current verification and deal controls."
                        ),
                        reason=(
                            f"Historical score: {item.weighted_score:.1f}/100; "
                            f"observations: {item.observation_count}; "
                            f"confidence: {item.confidence_score}/100."
                        ),
                        owner_role=_owner_for_metric(
                            item.signal_type
                        ),
                        approval_required=False,
                    )
                )
                priority += 1

        return recommendations[:30]

    def _audit(
        self,
        *,
        action: str,
        actor: str,
        details: dict[str, Any],
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO learning_audit (
                    action,
                    subject_type,
                    subject_id,
                    details_json,
                    actor,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    action,
                    subject_type,
                    subject_id,
                    json.dumps(
                        details,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    actor,
                    _now(),
                ),
            )
            connection.commit()


def _observation(
    *,
    subject_type: LearningSubjectType,
    subject_id: str,
    subject_name: str,
    signal_type: LearningSignalType,
    direction: LearningDirection,
    score: float,
    weight: float,
    confidence_score: int,
    evidence_summary: str,
    source_type: str,
    source_id: str | None = None,
    workflow_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LearningObservation:
    deterministic_key = (
        f"{subject_type.value}|{subject_id}|{signal_type.value}|"
        f"{source_type}|{source_id or 'none'}"
    )

    return LearningObservation(
        observation_id=(
            f"LRN-{uuid4().hex[:8].upper()}-"
            f"{abs(hash(deterministic_key)) % 10_000_000:07d}"
        ),
        subject_type=subject_type,
        subject_id=subject_id,
        subject_name=subject_name,
        signal_type=signal_type,
        direction=direction,
        score=max(0.0, min(100.0, score)),
        weight=max(0.01, weight),
        confidence_score=max(
            0,
            min(100, confidence_score),
        ),
        evidence_summary=evidence_summary,
        source_type=source_type,
        source_id=source_id,
        workflow_id=workflow_id,
        metadata=metadata or {},
    )


def _row_to_metric(
    row: Any,
) -> LearnedMetric:
    return LearnedMetric(
        subject_type=LearningSubjectType(
            row["subject_type"]
        ),
        subject_id=row["subject_id"],
        subject_name=row["subject_name"],
        signal_type=LearningSignalType(
            row["signal_type"]
        ),
        observation_count=int(
            row["observation_count"]
        ),
        weighted_score=float(
            row["weighted_score"]
        ),
        confidence_score=int(
            row["confidence_score"]
        ),
        trend=row["trend"],
        last_observed_at=row["last_observed_at"],
    )


def _consistency_score(
    values: list[float],
) -> float:
    if len(values) <= 1:
        return 50.0

    average = mean(values)
    deviation = mean(
        abs(value - average)
        for value in values
    )

    return max(
        0.0,
        min(
            100.0,
            100.0 - deviation * 2.0,
        ),
    )


def _owner_for_metric(
    signal_type: LearningSignalType,
) -> str:
    return {
        LearningSignalType.DELIVERY: "Logistics Manager",
        LearningSignalType.QUALITY: "Quality Manager",
        LearningSignalType.PAYMENT: "Finance Manager",
        LearningSignalType.COST_ACCURACY: "Cost & Profit Analyst",
        LearningSignalType.MARGIN_ACCURACY: "Commercial Manager",
        LearningSignalType.QUOTATION: "Procurement Specialist",
        LearningSignalType.CONVERSION: "Sales Manager",
        LearningSignalType.RISK: "Risk Manager",
        LearningSignalType.TRUST: "Compliance Manager",
        LearningSignalType.COMPLIANCE: "Compliance Manager",
        LearningSignalType.RECOMMENDATION: "Executive Advisor",
        LearningSignalType.RELATIONSHIP: "Commercial Manager",
    }.get(
        signal_type,
        "Executive Advisor",
    )


def _number(
    value: Any,
) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _optional_string(
    value: Any,
) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _now() -> str:
    return datetime.now().isoformat(
        timespec="seconds"
    )


_learning_engine = LearningIntelligenceEngine()


def get_learning_intelligence_engine() -> LearningIntelligenceEngine:
    """Return the learning intelligence singleton."""

    return _learning_engine


def run_learning_cycle(
    *,
    actor: str = "Learning Intelligence Engine",
    limit_per_domain: int = 1000,
) -> LearningReport:
    """Run one organisational learning cycle."""

    return _learning_engine.run_learning_cycle(
        actor=actor,
        limit_per_domain=limit_per_domain,
    )


def get_learning_adjustment(
    *,
    subject_type: LearningSubjectType,
    subject_id: str,
    signal_types: Iterable[LearningSignalType],
    maximum_adjustment: float = 15.0,
) -> dict[str, Any]:
    """Return a bounded historical scoring adjustment."""

    return _learning_engine.learning_adjustment(
        subject_type=subject_type,
        subject_id=subject_id,
        signal_types=signal_types,
        maximum_adjustment=maximum_adjustment,
    )