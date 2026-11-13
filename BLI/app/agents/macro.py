"""Macroeconomic & Policy cluster.

A single agent monitors city-wide shifts - interest rates, zoning revisions,
capital availability - and propagates them as multipliers the Supply cluster
reads. The agent both follows a random walk and reacts to policy/infrastructure
events scheduled for the current year (e.g. a metro becoming operational can
loosen capital availability for nearby development).
"""

from __future__ import annotations

import mesa

from app.schemas import ProjectStatus


class MacroeconomicAgent(mesa.Agent):
    """Owns city-wide financial regime state read by the rest of the model."""

    def __init__(self, model: "mesa.Model", initial_interest_rate: float = 8.5,
                 initial_capital_availability: float = 1.0):
        super().__init__(model)
        self.interest_rate = float(initial_interest_rate)
        self.initial_interest_rate = float(initial_interest_rate)
        self.capital_availability = float(initial_capital_availability)
        self.initial_capital_availability = float(initial_capital_availability)
        # Risk multiplier applied to developer financing cost. >1 => riskier.
        self.risk_multiplier = 1.0
        self.zoning_factor = 1.0  # >1 => zoning relaxed (more developable supply)

    # ------------------------------------------------------------------
    def step(self) -> None:
        rng = self.model.random
        # Interest rate: small mean-reverting random walk around the initial rate.
        drift = (self.initial_interest_rate - self.interest_rate) * 0.2
        shock = self.model.random.gauss(0.0, 0.15)
        self.interest_rate = round(max(3.0, min(15.0, self.interest_rate + drift + shock)), 3)

        # Capital availability: tightens when rates rise, eases when policy events fire.
        rate_pressure = (self.interest_rate - self.initial_interest_rate) / 10.0
        self.capital_availability = round(
            max(0.4, min(1.5, self.capital_availability * (1.0 - rate_pressure))), 4
        )

        # Risk multiplier: rises with rates and with delayed projects.
        delayed = self.model.count_infrastructure_by_status(ProjectStatus.DELAYED)
        self.risk_multiplier = round(max(0.8, min(2.0, 1.0 + rate_pressure + 0.02 * delayed)), 4)

        # Zoning: a POLICY event in this year relaxes zoning; otherwise reverts slowly.
        policy_events = [e for e in self.model.events_for_year() if e.get("type") == "policy"]
        if policy_events:
            self.zoning_factor = round(min(1.5, self.zoning_factor + 0.05 * len(policy_events)), 4)
        else:
            self.zoning_factor = round(max(0.9, self.zoning_factor * 0.995), 4)

        # Publish to the model so other agents read a single source of truth.
        self.model.interest_rate = self.interest_rate
        self.model.capital_availability = self.capital_availability
        self.model.risk_multiplier = self.risk_multiplier
        self.model.zoning_factor = self.zoning_factor
