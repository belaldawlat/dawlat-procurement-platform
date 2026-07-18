"""Landed Cost Forecasting Engine for the Autonomous Procurement Brain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class LandedCostScenario:
    scenario_name: str
    product_cost: float
    freight_cost: float
    insurance_cost: float
    customs_cost: float
    port_charges: float
    biosecurity_cost: float
    handling_cost: float
    trucking_cost: float
    warehouse_cost: float
    other_cost: float
    exchange_rate: float
    quantity: float
    contingency_percent: float = 5.0
    probability: float = 1.0


@dataclass(frozen=True)
class LandedCostForecast:
    expected_total_cost: float
    expected_unit_cost: float
    minimum_total_cost: float
    maximum_total_cost: float
    confidence_score: int
    contingency_amount: float
    scenarios_evaluated: int
    warnings: tuple[str, ...]
    explanation: str
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class LandedCostForecastingEngine:
    def forecast(
        self,
        scenarios: Iterable[LandedCostScenario],
    ) -> LandedCostForecast:
        scenario_list = list(scenarios)

        if not scenario_list:
            raise ValueError(
                "At least one landed-cost scenario is required."
            )

        warnings: list[str] = []
        weighted_totals: list[tuple[float, float]] = []
        totals: list[float] = []
        contingencies: list[tuple[float, float]] = []

        total_probability = sum(
            max(0.0, scenario.probability)
            for scenario in scenario_list
        )

        if total_probability <= 0:
            raise ValueError(
                "Scenario probabilities must total more than zero."
            )

        weighted_quantity = 0.0

        for scenario in scenario_list:
            if scenario.quantity <= 0:
                raise ValueError(
                    f"Scenario '{scenario.scenario_name}' has invalid quantity."
                )

            if scenario.exchange_rate <= 0:
                raise ValueError(
                    f"Scenario '{scenario.scenario_name}' has invalid exchange rate."
                )

            subtotal = (
                scenario.product_cost
                + scenario.freight_cost
                + scenario.insurance_cost
                + scenario.customs_cost
                + scenario.port_charges
                + scenario.biosecurity_cost
                + scenario.handling_cost
                + scenario.trucking_cost
                + scenario.warehouse_cost
                + scenario.other_cost
            )

            local_subtotal = subtotal * scenario.exchange_rate
            contingency = (
                local_subtotal
                * max(0.0, scenario.contingency_percent)
                / 100.0
            )
            total = local_subtotal + contingency
            probability = (
                max(0.0, scenario.probability)
                / total_probability
            )

            weighted_totals.append((total, probability))
            contingencies.append((contingency, probability))
            totals.append(total)
            weighted_quantity += scenario.quantity * probability

            if scenario.contingency_percent < 3:
                warnings.append(
                    f"Scenario '{scenario.scenario_name}' has a low contingency."
                )

        expected_total = sum(
            total * probability
            for total, probability in weighted_totals
        )
        expected_unit = expected_total / weighted_quantity

        spread = max(totals) - min(totals)
        spread_ratio = (
            spread / expected_total
            if expected_total > 0
            else 1.0
        )

        confidence_score = max(
            0,
            min(
                100,
                round(
                    90
                    - spread_ratio * 100
                    + min(10, len(scenario_list) * 2)
                ),
            ),
        )

        expected_contingency = sum(
            contingency * probability
            for contingency, probability in contingencies
        )

        return LandedCostForecast(
            expected_total_cost=round(expected_total, 2),
            expected_unit_cost=round(expected_unit, 4),
            minimum_total_cost=round(min(totals), 2),
            maximum_total_cost=round(max(totals), 2),
            confidence_score=confidence_score,
            contingency_amount=round(expected_contingency, 2),
            scenarios_evaluated=len(scenario_list),
            warnings=tuple(dict.fromkeys(warnings)),
            explanation=(
                f"Forecast uses {len(scenario_list)} weighted scenario(s). "
                f"Expected landed cost is {expected_total:.2f}, with "
                f"expected unit cost {expected_unit:.2f}."
            ),
        )


_engine = LandedCostForecastingEngine()


def get_landed_cost_forecasting_engine() -> LandedCostForecastingEngine:
    return _engine