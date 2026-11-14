"""Industrial & Manufacturing Cluster (Mesa multi-agent model).

Simulates the endogenous emergence and expansion of industrial factories,
manufacturing plants, and logistics parks following infrastructure delivery
(freight rail, expressways, STRR, PRR, highway corridors).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional

import mesa
from shapely.geometry import Point

from app.schemas import ProjectStatus

if TYPE_CHECKING:
    from app.agents.model import UrbanAlphaModel


class IndustryType(str, Enum):
    HEAVY_MANUFACTURING = "heavy_manufacturing"      # Auto, machinery, aerospace
    LOGISTICS_WAREHOUSING = "logistics_warehousing"  # E-commerce fulfillment, freight hubs
    LIGHT_INDUSTRIAL = "light_industrial"            # Clean assembly, electronics, hardware


class IndustrialStatus(str, Enum):
    SCOUTING = "scouting"
    LAND_ACQUISITION = "land_acquisition"
    CONSTRUCTION = "construction"
    OPERATIONAL = "operational"


class IndustrialAgent(mesa.Agent):
    """An industrial enterprise that scouts, acquires land, and operates facilities.

    Causal Chain:
    1. Infrastructure progress (STRR / PRR / Suburban Rail / Highways) unlocks logistics corridors.
    2. Viability Index evaluated:
           V = (FreightAccessibility + HighwayAccess) / (LandCostRatio) * CapitalAvailability
    3. If V > Threshold, acquires land -> constructs plant -> commissions factory.
    4. Operational factory generates jobs and spatial employment gravity for the parcel.
    """

    def __init__(
        self,
        model: "UrbanAlphaModel",
        industry_type: IndustryType = IndustryType.LIGHT_INDUSTRIAL,
        target_jobs: int = 1500,
        land_footprint_sqft: float = 300_000.0,
        max_land_budget_sqft: float = 6500.0,
        capex_cr: float = 120.0,
        distance_to_parcel_km: float = 3.5,
    ) -> None:
        super().__init__(model)
        self.industry_type = industry_type
        self.target_jobs = target_jobs
        self.land_footprint_sqft = land_footprint_sqft
        self.max_land_budget_sqft = max_land_budget_sqft
        self.capex_cr = capex_cr
        self.distance_to_parcel_km = distance_to_parcel_km

        self.status = IndustrialStatus.SCOUTING
        self.jobs_created = 0
        self.sqft_absorbed = 0.0
        self.operational_year = 0
        self.viability_score = 0.0

    def step(self) -> None:
        m = self.model

        # 1. Compute logistic viability from available regional infrastructure & land prices
        self.viability_score = self._compute_viability()

        # 2. Advance lifecycle
        if self.status == IndustrialStatus.SCOUTING:
            threshold = 0.70 if self.industry_type == IndustryType.LIGHT_INDUSTRIAL else 0.85
            if self.viability_score >= threshold and m.land_value_per_sqft <= self.max_land_budget_sqft:
                self.status = IndustrialStatus.LAND_ACQUISITION
                self.sqft_absorbed = self.land_footprint_sqft
                if hasattr(m, "_year_events"):
                    m._year_events.append({
                        "type": "industrial_land_acquisition",
                        "industry": self.industry_type.value,
                        "sqft": self.sqft_absorbed,
                        "year": m.current_year,
                    })

        elif self.status == IndustrialStatus.LAND_ACQUISITION:
            self.status = IndustrialStatus.CONSTRUCTION
            if hasattr(m, "_year_events"):
                m._year_events.append({
                    "type": "industrial_construction_start",
                    "industry": self.industry_type.value,
                    "capex_cr": self.capex_cr,
                    "year": m.current_year,
                })

        elif self.status == IndustrialStatus.CONSTRUCTION:
            self.status = IndustrialStatus.OPERATIONAL
            self.jobs_created = self.target_jobs
            self.operational_year = m.current_year
            if hasattr(m, "_year_events"):
                m._year_events.append({
                    "type": "factory_commissioned",
                    "industry": self.industry_type.value,
                    "jobs": self.jobs_created,
                    "year": m.current_year,
                })

        elif self.status == IndustrialStatus.OPERATIONAL:
            # Scaled workforce expansion if capital environment is favorable
            if m.capital_availability > 1.0:
                expansion = int(self.target_jobs * 0.06)
                self.jobs_created += expansion

    def _compute_viability(self) -> float:
        m = self.model
        infra_score = 0.0
        projects = getattr(m, "projects", [])

        for p in projects:
            p_type = (getattr(p, "type", "") or "").lower()
            p_name = (getattr(p, "name", "") or "").lower()
            status = getattr(p, "status", "")

            # Identify freight, highway, expressways, ring roads, suburban rail
            weight = 0.0
            if any(k in p_type or k in p_name for k in ("strr", "prr", "highway", "expressway", "road", "flyover")):
                weight = 1.3
            elif any(k in p_type or k in p_name for k in ("suburban_rail", "rail", "cargo")):
                weight = 1.1
            elif "metro" in p_type:
                weight = 0.5

            if weight > 0:
                if status == ProjectStatus.OPERATIONAL.value:
                    infra_score += weight * 1.0
                elif status == ProjectStatus.UNDER_CONSTRUCTION.value:
                    infra_score += weight * 0.60
                elif status == ProjectStatus.APPROVED.value:
                    infra_score += weight * 0.30

        # Freight viability: accessibility balanced against land rate
        land_cost_ratio = max(0.5, m.land_value_per_sqft / 3500.0)
        viability = (infra_score / land_cost_ratio) * m.capital_availability
        return round(viability, 4)

    def employment_gravity(self) -> float:
        """Gravity model contribution: Jobs / (1 + distance_km)^2."""
        if self.status != IndustrialStatus.OPERATIONAL or self.jobs_created <= 0:
            return 0.0
        d_km = max(0.5, self.distance_to_parcel_km)
        return round(self.jobs_created / ((1.0 + d_km) ** 2), 2)
