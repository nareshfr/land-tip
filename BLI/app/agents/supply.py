"""Supply & Development cluster (landowners & developers).

Each DeveloperAgent owns a capital pool and a reservation price anchored to the
Year-0 baseline valuation. Each year it evaluates feasibility:

    Expected Revenue - Land Cost - Construction Cost - Financing Cost

A positive margin above a threshold triggers development, depleting capital.
The macro cluster's interest rate and risk multiplier feed the financing cost.
The model aggregates mean margins into a supply pressure term.
"""

from __future__ import annotations

import mesa

from app.schemas import ProjectStatus


class DeveloperAgent(mesa.Agent):
    """A developer with a capital pool and a reservation price."""

    # Construction cost per sqft (INR). Bengaluru ballpark.
    CONSTRUCTION_RATE_PER_SQFT = 2500.0
    LEVERAGE = 0.6  # share of project financed by debt
    MARGIN_THRESHOLD = 0.12  # develop only if expected margin exceeds this

    def __init__(self, model: "mesa.Model", baseline_price_per_sqft: float,
                 capital: float = 1.0e8):
        super().__init__(model)
        self.baseline_ppsqft = float(baseline_price_per_sqft)
        self.reservation_ppsqft = float(baseline_price_per_sqft)
        self.capital = float(capital)
        self.margin = 0.0
        self.developed_units = 0

    # ------------------------------------------------------------------
    def step(self) -> None:
        m = self.model
        rng = m.random

        land_cost = self.reservation_ppsqft  # INR/sqft anchored to baseline
        construction_cost = self.CONSTRUCTION_RATE_PER_SQFT

        # Financing cost scales with the macro interest rate and risk multiplier.
        financing_rate = (m.interest_rate / 100.0) * m.risk_multiplier
        financing_cost = (land_cost + construction_cost) * self.LEVERAGE * financing_rate

        # Expected revenue/sqft: baseline * demand pressure * zoning allowance.
        demand_pressure = max(0.5, min(2.0, 1.0 + m.demand_pressure))
        comm_boost = (1.0 + 0.10 * m.impact_scores.commercial) if getattr(m, "impact_scores", None) else 1.0
        expected_revenue = self.baseline_ppsqft * demand_pressure * m.zoning_factor * comm_boost

        # Reservation price rises with land value so future land cost tracks the market.
        self.reservation_ppsqft = max(
            self.baseline_ppsqft,
            0.7 * self.reservation_ppsqft + 0.3 * m.land_value_per_sqft,
        )

        total_cost = land_cost + construction_cost + financing_cost
        self.margin = (expected_revenue - total_cost) / max(1.0, expected_revenue)

        # Develop if feasible and capital allows; capital scales with availability.
        effective_capital = self.capital * m.capital_availability
        if self.margin > self.MARGIN_THRESHOLD and effective_capital > 0:
            units = max(1, int(effective_capital / (total_cost * 1000.0)))
            self.developed_units += units
            self.capital = max(0.0, effective_capital - units * total_cost * 1000.0)
        else:
            # Idle developers slowly replenish capital.
            self.capital *= 1.0 + 0.02 * rng.random()

        m.add_developer_margin(self.margin, self.developed_units)
