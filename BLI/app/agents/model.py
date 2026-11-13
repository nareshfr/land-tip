"""UrbanAlphaModel - the Mesa model coordinating all clusters.

Owns:
    * shared market state (interest rate, capital availability, risk multiplier,
      zoning, demand/supply pressure, land value per sqft and its index)
    * the infrastructure timeline (projects and per-year status transitions)
    * the per-year snapshot timeline consumed by the simulation engine

Step ordering each year (one Mesa step == one simulation year):
    1. advance infrastructure statuses for the new year
    2. Macroeconomic & Policy cluster
    3. Supply & Development cluster
    4. Demand cluster
    5. recompute demand/supply pressure and the land-value index
    6. record a snapshot
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import mesa
from shapely.geometry import Point

from app.agents.demand import HouseholdAgent
from app.agents.infrastructure_agent import InfrastructureDevelopmentAgent
from app.agents.macro import MacroeconomicAgent
from app.agents.supply import DeveloperAgent
from app.calibration.engine import CalibrationParams, calibrate_locality
from app.impact.engine import ImpactScores, InfrastructureImpactEngine
from app.market.dynamics import MarketDynamicsEngine, MarketState, YearGrowth
from app.schemas import (
    BaselineValuation,
    InfrastructureType,
    ProjectStatus,
)


# ---------------------------------------------------------------------------
# Per-project runtime record derived from validated InfrastructureSchema rows.
# ---------------------------------------------------------------------------

@dataclass
class RuntimeProject:
    project_id: str
    name: str
    source: str
    type: str
    status: str
    announcement_date: Optional[str] = None
    within_2km: bool = False
    # Years (relative to Year 0) at which the project transitions status.
    status_schedule: dict[int, str] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    # v1.1 constrained project progression state.
    funding: float = 0.5
    approved: bool = False
    land_acquisition: float = 0.5
    construction_progress: float = 0.0
    delay_years: int = 0

    def status_for_year(self, year: int) -> str:
        # Latest scheduled status at or before this year; fall back to current.
        latest = self.status
        for y in sorted(self.status_schedule):
            if y <= year:
                latest = self.status_schedule[y]
        return latest


class UrbanAlphaModel(mesa.Model):
    """Multi-cluster Mesa model for Bengaluru land valuation."""

    def __init__(
        self,
        baseline: BaselineValuation,
        infrastructure: list[dict],
        years: int = 5,
        households: int = 50,
        developers: int = 5,
        initial_interest_rate: float = 8.5,
        capital_availability: float = 1.0,
        seed: int = 42,
        parcel_centroid: Optional[Point] = None,
        locality: str = "",
        use_infrastructure_agent: bool = True,
        use_market_dynamics: bool = True,
        use_impact_engine: bool = True,
    ):
        super().__init__(rng=seed)
        self.baseline = baseline
        self.years = years
        self.current_year = 0
        self.locality = locality or getattr(baseline, "location_used", "")

        # Optional centroid resolution.
        if parcel_centroid is None and self.locality:
            try:
                from app.spatial.localities import locality_centroid
                parcel_centroid = locality_centroid(self.locality)
            except Exception:
                parcel_centroid = None
        self.parcel_centroid = parcel_centroid

        # Feature flags.
        self.use_infrastructure_agent = use_infrastructure_agent
        self.use_market_dynamics = use_market_dynamics
        self.use_impact_engine = use_impact_engine

        # Shared market state.
        self.interest_rate = float(initial_interest_rate)
        self.capital_availability = float(capital_availability)
        self.risk_multiplier = 1.0
        self.zoning_factor = 1.0
        self.demand_pressure = 0.0  # mean utility delta vs Year 0
        self.supply_pressure = 0.0  # mean developer margin
        self.baseline_ppsqft = float(baseline.price_per_sqft_inr)
        self.land_value_per_sqft = float(baseline.price_per_sqft_inr)
        self.land_value_index = 1.0  # Year 0 == 1.0
        self._baseline_utility: float = 0.0

        # Demand / supply accumulators reset each step.
        self._demand_utils: list[float] = []
        self._developer_margins: list[float] = []
        self._developed_units: int = 0

        # Infrastructure runtime state.
        self.projects: list[RuntimeProject] = [
            self._to_runtime(p) for p in infrastructure
        ]
        # Buffer membership (within 2km) is set by the engine after construction.
        # Events that changed status this year.
        self._year_events: list[dict] = []

        # Engines.
        self.impact_engine = InfrastructureImpactEngine(self.parcel_centroid) if self.use_impact_engine else None
        self.impact_scores: Optional[ImpactScores] = (
            self.impact_engine.compute(self.projects) if self.impact_engine else None
        )
        self.calibration: CalibrationParams = calibrate_locality(self.locality)
        self.market_engine = MarketDynamicsEngine(self.calibration) if self.use_market_dynamics else None
        self._current_market_state: Optional[MarketState] = None
        self._current_growth: Optional[YearGrowth] = None

        # Build the timeline snapshots list and seed Year 0.
        self.timeline: list[dict] = []

        # --- create agents ---
        self.macro = MacroeconomicAgent(
            self, initial_interest_rate=initial_interest_rate,
            initial_capital_availability=capital_availability,
        )
        for _ in range(max(1, households)):
            HouseholdAgent(self, baseline_price_per_sqft=self.baseline_ppsqft)
        for _ in range(max(1, developers)):
            DeveloperAgent(self, baseline_price_per_sqft=self.baseline_ppsqft)
        self.infra_agent = InfrastructureDevelopmentAgent(self) if self.use_infrastructure_agent else None

        # Capture Year-0 demand baseline utility (one demand pass without side effects).
        self._compute_baseline_utility()

        self.timeline.append(self._snapshot(year=0))

    # ------------------------------------------------------------------
    # Infrastructure helpers
    # ------------------------------------------------------------------
    def _to_runtime(self, p: dict) -> RuntimeProject:
        status = p.get("status", ProjectStatus.PROPOSED.value)
        schedule: dict[int, str] = {}
        ann = p.get("announcement_date")
        start_year = 1
        if isinstance(ann, str) and ann[:4].isdigit():
            try:
                start_year = max(1, 2024 - int(ann[:4]))
            except ValueError:
                pass
        order = [
            ProjectStatus.PROPOSED.value,
            ProjectStatus.APPROVED.value,
            ProjectStatus.UNDER_CONSTRUCTION.value,
            ProjectStatus.OPERATIONAL.value,
        ]
        try:
            start_idx = order.index(status)
        except ValueError:
            start_idx = 0
        for offset, st in enumerate(order[start_idx:], start=1):
            schedule[start_year + offset - 1] = st

        # Progression state defaults based on initial status.
        if status == ProjectStatus.OPERATIONAL.value:
            funding = 1.0
            approved = True
            land_acq = 1.0
            progress = 1.0
        elif status == ProjectStatus.UNDER_CONSTRUCTION.value:
            funding = float(p.get("funding", 0.8))
            approved = True
            land_acq = float(p.get("land_acquisition", 0.9))
            progress = float(p.get("construction_progress", 0.35))
        elif status == ProjectStatus.APPROVED.value:
            funding = float(p.get("funding", 0.6))
            approved = True
            land_acq = float(p.get("land_acquisition", 0.5))
            progress = 0.0
        else:
            funding = float(p.get("funding", 0.35))
            approved = False
            land_acq = float(p.get("land_acquisition", 0.1))
            progress = 0.0

        return RuntimeProject(
            project_id=p.get("project_id", ""),
            name=p.get("name", ""),
            source=p.get("source", ""),
            type=p.get("type", InfrastructureType.OTHER.value),
            status=status,
            announcement_date=ann,
            within_2km=bool(p.get("within_2km", False)),
            status_schedule=schedule,
            raw=p,
            funding=funding,
            approved=approved,
            land_acquisition=land_acq,
            construction_progress=progress,
            delay_years=int(p.get("delay_years", 0)),
        )

    def set_within_2km(self, project_ids: set[str]) -> None:
        ids = set(project_ids)
        for proj in self.projects:
            proj.within_2km = proj.project_id in ids
        if self.use_impact_engine and self.impact_engine is not None:
            self.impact_scores = self.impact_engine.compute(self.projects)
            self._compute_baseline_utility()
            if self.timeline and self.timeline[0]["year"] == 0:
                self.timeline[0] = self._snapshot(year=0)

    def set_infrastructure_events(self, events: list[dict]) -> None:
        self._year_events.extend(events)

    def events_for_year(self) -> list[dict]:
        """Policy/macro events scheduled for the current year."""
        return [e for e in self._year_events if e.get("type") == "policy"]

    def count_infrastructure_by_status(self, status) -> int:
        target = status.value if isinstance(status, ProjectStatus) else status
        return sum(1 for p in self.projects if p.status == target)

    def active_nearby_projects(self, types, status) -> list[RuntimeProject]:
        type_set = {t.value if isinstance(t, InfrastructureType) else t for t in types}
        target = status.value if isinstance(status, ProjectStatus) else status
        return [
            p for p in self.projects
            if p.within_2km and p.type in type_set and p.status == target
        ]

    def _advance_infrastructure(self, year: int) -> None:
        """Promote each project to its scheduled status for this year."""
        self._year_events = []
        for proj in self.projects:
            new_status = proj.status_schedule.get(year)
            if new_status and new_status != proj.status:
                proj.status = new_status
                self._year_events.append({
                    "project_id": proj.project_id,
                    "name": proj.name,
                    "type": proj.type,
                    "status": new_status,
                    "year": year,
                })

    # ------------------------------------------------------------------
    # Demand / supply aggregation
    # ------------------------------------------------------------------
    def add_demand_utility(self, u: float) -> None:
        self._demand_utils.append(u)

    def add_developer_margin(self, margin: float, units: int) -> None:
        self._developer_margins.append(margin)
        self._developed_units += units

    def _compute_baseline_utility(self) -> None:
        """One demand evaluation pass at Year 0 to anchor demand pressure."""
        utils: list[float] = []
        for a in self.agents_by_type.get(HouseholdAgent, []):
            a.step()  # computes utility and would call add_demand_utility
            utils.append(a.utility)
        self._baseline_utility = (sum(utils) / len(utils)) if utils else 0.0
        # Discard the side effects used only to measure the baseline.
        self._demand_utils = []
        self._developer_margins = []
        self._developed_units = 0

    # ------------------------------------------------------------------
    # Per-year snapshot
    # ------------------------------------------------------------------
    def _snapshot(self, year: int) -> dict:
        active = sum(
            1 for p in self.projects
            if p.status in (
                ProjectStatus.OPERATIONAL.value,
                ProjectStatus.UNDER_CONSTRUCTION.value,
            )
        )
        return {
            "year": year,
            "interest_rate": round(self.interest_rate, 3),
            "capital_availability": round(self.capital_availability, 4),
            "risk_multiplier": round(self.risk_multiplier, 4),
            "zoning_factor": round(self.zoning_factor, 4),
            "mean_demand_utility": round(self._mean(self._demand_utils), 4),
            "mean_developer_profit_margin": round(self._mean(self._developer_margins), 4),
            "developed_units": self._developed_units,
            "demand_pressure": round(self.demand_pressure, 4),
            "supply_pressure": round(self.supply_pressure, 4),
            "land_value_per_sqft": round(self.land_value_per_sqft, 2),
            "land_value_index": round(self.land_value_index, 4),
            "active_infrastructure": active,
            "impact": self.impact_scores.as_dict() if self.impact_scores else {},
            "market": self._current_market_state.__dict__ if self._current_market_state else {},
            "growth": self._current_growth.as_dict() if self._current_growth else {},
            "events": list(self._year_events),
        }

    @staticmethod
    def _mean(xs: list[float]) -> float:
        return (sum(xs) / len(xs)) if xs else 0.0

    # ------------------------------------------------------------------
    # Land-value index update
    # ------------------------------------------------------------------
    def _update_land_value_index(self) -> None:
        # Demand pressure: normalised delta of mean utility vs Year-0 baseline.
        mean_u = self._mean(self._demand_utils)
        denom = max(0.5, abs(self._baseline_utility))
        self.demand_pressure = (mean_u - self._baseline_utility) / denom
        self.demand_pressure = max(-1.0, min(2.0, self.demand_pressure))

        # Supply pressure: mean developer margin.
        self.supply_pressure = self._mean(self._developer_margins)

        if self.use_market_dynamics and self.market_engine is not None:
            infra_inf = self.impact_scores.infrastructure_influence if self.impact_scores else 0.0
            comm_demand = self.impact_scores.commercial if self.impact_scores else 0.0
            state = MarketState(
                residential_demand=self.demand_pressure,
                commercial_demand=comm_demand,
                developer_demand=self.supply_pressure,
                zoning_factor=self.zoning_factor,
                developed_units=self._developed_units,
                interest_rate=self.interest_rate,
                base_interest_rate=self.macro.initial_interest_rate,
                risk_multiplier=self.risk_multiplier,
                infrastructure_influence=infra_inf,
            )
            growth = self.market_engine.compute_growth(state)
            self._current_growth = growth
            self._current_market_state = state
            self.land_value_index = round(max(0.3, self.land_value_index * (1.0 + growth.g_total)), 4)
            self.land_value_per_sqft = round(self.baseline_ppsqft * self.land_value_index, 2)
        else:
            # Accessibility / amenity gains from newly operational nearby projects.
            transit = len(self.active_nearby_projects(
                types=(InfrastructureType.METRO, InfrastructureType.ROAD,
                       InfrastructureType.SUBURBAN_RAIL, InfrastructureType.FLYOVER),
                status=ProjectStatus.OPERATIONAL,
            ))
            amenity = len(self.active_nearby_projects(
                types=(InfrastructureType.PARK, InfrastructureType.LAKE_RESTORATION),
                status=ProjectStatus.OPERATIONAL,
            ))
            access_gain = 0.04 * transit
            amenity_gain = 0.03 * amenity

            # Risk discount from elevated rates.
            risk_discount = max(0.0, (self.interest_rate - self.macro.initial_interest_rate) / 100.0)
            # Supply overhang: large margins (oversupply) dampen appreciation.
            supply_drag = max(0.0, (self.supply_pressure - 0.4)) * 0.05

            growth = (
                0.05 * self.demand_pressure
                + access_gain
                + amenity_gain
                - risk_discount
                - supply_drag
            )
            self.land_value_index = round(max(0.3, self.land_value_index * (1.0 + growth)), 4)
            self.land_value_per_sqft = round(self.baseline_ppsqft * self.land_value_index, 2)

    # ------------------------------------------------------------------
    # The Mesa step == one simulation year
    # ------------------------------------------------------------------
    def step(self) -> None:
        self.current_year += 1
        self._year_events = []

        if self.use_infrastructure_agent and self.infra_agent is not None:
            self.infra_agent.step()
        else:
            self._advance_infrastructure(self.current_year)

        if self.use_impact_engine and self.impact_engine is not None:
            self.impact_scores = self.impact_engine.compute(self.projects)

        self._demand_utils = []
        self._developer_margins = []
        self._developed_units = 0

        # Cluster ordering: Macro -> Supply -> Demand.
        macro = self.agents_by_type.get(MacroeconomicAgent, [])
        developers = self.agents_by_type.get(DeveloperAgent, [])
        households = self.agents_by_type.get(HouseholdAgent, [])
        macro.do("step")
        developers.do("step")
        households.do("step")

        self._update_land_value_index()
        self.timeline.append(self._snapshot(self.current_year))
        if self.current_year >= self.years:
            self.running = False
