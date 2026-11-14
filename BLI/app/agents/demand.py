"""Demand cluster (households & commercial buyers).

Each HouseholdAgent evaluates location utility for the analysis parcel using:

    Utility = Accessibility Score + Employment Score + Amenity Score - Housing Cost Score

Scores are derived from the shared model state (operational infrastructure near
the parcel, baseline price) so the demand cluster reacts to the same scraped
events the Supply cluster sees. The model aggregates mean utility into a demand
pressure term that drives the land-value index.
"""

from __future__ import annotations

import mesa

from app.schemas import InfrastructureType, ProjectStatus


class HouseholdAgent(mesa.Agent):
    """A household (or commercial buyer) evaluating the analysis parcel."""

    # Score weights - kept explicit and small for traceability.
    W_ACCESS = 1.0
    W_EMPLOY = 0.6
    W_AMENITY = 0.5
    W_COST = 1.0

    def __init__(self, model: "mesa.Model", baseline_price_per_sqft: float,
                 income_multiplier: float = 1.0):
        super().__init__(model)
        self.baseline_ppsqft = float(baseline_price_per_sqft)
        self.income_multiplier = float(income_multiplier)
        self.utility = 0.0

    # ------------------------------------------------------------------
    def step(self) -> None:
        m = self.model
        rng = m.random

        # v1.1: Use continuous distance-decayed Impact Engine scores if available.
        if getattr(m, "impact_scores", None) is not None:
            accessibility = min(1.5, 0.20 + m.impact_scores.accessibility)
            employment = min(1.5, 0.25 + m.impact_scores.employment)
            amenity = min(1.5, 0.10 + m.impact_scores.amenity)
        else:
            # Fallback legacy buffer counts.
            access_projects = m.active_nearby_projects(types=(
                InfrastructureType.METRO, InfrastructureType.ROAD,
                InfrastructureType.SUBURBAN_RAIL, InfrastructureType.FLYOVER,
            ), status=ProjectStatus.OPERATIONAL)
            accessibility = min(1.0, 0.2 + 0.15 * len(access_projects))

            employ_projects = m.active_nearby_projects(types=(
                InfrastructureType.COMMERCIAL, InfrastructureType.METRO,
            ), status=ProjectStatus.OPERATIONAL)
            employment = min(1.0, 0.25 + 0.12 * len(employ_projects))

            amenity_projects = m.active_nearby_projects(types=(
                InfrastructureType.PARK, InfrastructureType.LAKE_RESTORATION,
            ), status=ProjectStatus.OPERATIONAL)
            amenity = min(1.0, 0.1 + 0.10 * len(amenity_projects))

        # Industrial employment accessibility boost from operational factories
        ind_gravity = getattr(m, "industrial_employment_gravity", 0.0)
        if ind_gravity > 0:
            employment = min(1.8, employment + min(0.35, (ind_gravity / 500.0) * 0.15))

        # Housing cost: current land value per sqft normalised against baseline.
        current_ppsqft = m.land_value_per_sqft or self.baseline_ppsqft
        cost_ratio = current_ppsqft / max(1.0, self.baseline_ppsqft)
        housing_cost = min(1.2, max(0.0, (cost_ratio - 1.0) * 0.40))

        # Add idiosyncratic preference noise scaled by income.
        noise = rng.gauss(0.0, 0.05) * self.income_multiplier

        self.utility = (
            self.W_ACCESS * accessibility
            + self.W_EMPLOY * employment
            + self.W_AMENITY * amenity
            - self.W_COST * housing_cost
            + noise
        )

        # Aggregate into the model's demand stream.
        m.add_demand_utility(self.utility)
