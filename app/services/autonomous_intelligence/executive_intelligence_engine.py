"""Board-level executive intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ExecutiveSnapshot:
    top_opportunities: tuple[str, ...]
    biggest_risks: tuple[str, ...]
    margin_leakage_amount: float
    supplier_concentration_percent: float
    cash_exposure_amount: float
    growth_forecast_percent: float
    procurement_kpis: dict[str, Any]
    summary: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class ExecutiveIntelligenceEngine:
    def generate(
        self,
        *,
        opportunities: list[dict[str, Any]],
        risks: list[dict[str, Any]],
        margin_leakage_amount: float,
        supplier_concentration_percent: float,
        cash_exposure_amount: float,
        growth_forecast_percent: float,
        procurement_kpis: dict[str, Any],
    ) -> ExecutiveSnapshot:
        ranked_opportunities = sorted(
            opportunities,
            key=lambda item: item.get(
                "score",
                0,
            ),
            reverse=True,
        )

        ranked_risks = sorted(
            risks,
            key=lambda item: item.get(
                "score",
                0,
            ),
            reverse=True,
        )

        top_opportunities = tuple(
            str(item.get("title", "Unnamed opportunity"))
            for item in ranked_opportunities[:5]
        )

        biggest_risks = tuple(
            str(item.get("title", "Unnamed risk"))
            for item in ranked_risks[:5]
        )

        summary = (
            f"{len(top_opportunities)} priority opportunity(s), "
            f"{len(biggest_risks)} major risk(s), "
            f"margin leakage {margin_leakage_amount:.2f}, "
            f"cash exposure {cash_exposure_amount:.2f}, and "
            f"growth forecast {growth_forecast_percent:.2f}%."
        )

        return ExecutiveSnapshot(
            top_opportunities=top_opportunities,
            biggest_risks=biggest_risks,
            margin_leakage_amount=round(
                margin_leakage_amount,
                2,
            ),
            supplier_concentration_percent=round(
                supplier_concentration_percent,
                2,
            ),
            cash_exposure_amount=round(
                cash_exposure_amount,
                2,
            ),
            growth_forecast_percent=round(
                growth_forecast_percent,
                2,
            ),
            procurement_kpis=procurement_kpis,
            summary=summary,
        )


_engine = ExecutiveIntelligenceEngine()


def get_executive_intelligence_engine() -> ExecutiveIntelligenceEngine:
    return _engine