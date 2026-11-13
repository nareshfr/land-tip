"""Market Dynamics Engine.

Connects household demand, developer decisions and available land supply into a
single market-pressure term, then turns that pressure — together with the
calibrated locality baseline growth, scarcity and rate risk — into the annual
land-price growth rate:

    g_t = g_market + g_demand + g_scarity - g_risk

where every term except ``g_market`` is a **deviation** from the locality's
normal state (measured against Year-0 baselines captured by the model), so the
components do not double-count. Infrastructure influence is *not* added on top;
it is the portion of demand-driven growth attributable to the Impact Engine's
influence score, reported separately via ``g_infra`` for explainability only.

The engine is stateless per call: the Mesa model assembles a
:class:`MarketState` snapshot each year and calls :meth:`compute_growth`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.calibration.engine import CalibrationParams, calibrate_locality


@dataclass
class MarketState:
    """One-year snapshot of the market inputs the engine needs."""

    # Demand side.
    residential_demand: float = 0.0   # demand pressure (delta vs Year-0 utility)
    commercial_demand: float = 0.0   # commercial attractiveness from Impact Engine
    developer_demand: float = 0.0   # developer margin delta vs Year-0 baseline
    # Supply side.
    zoning_factor: float = 1.0       # >1 = zoning relaxed (more developable land)
    developed_units: int = 0
    # Macro.
    interest_rate: float = 8.5
    base_interest_rate: float = 8.5
    risk_multiplier: float = 1.0
    # Impact Engine aggregate influence (for infrastructure attribution only).
    infrastructure_influence: float = 0.0


@dataclass
class YearGrowth:
    """Decomposed annual growth rate (all fractions, e.g. 0.08 == 8%)."""

    g_market: float = 0.0
    g_demand: float = 0.0
    g_infra: float = 0.0     # attribution only; already inside g_demand
    g_scarity: float = 0.0
    g_risk: float = 0.0
    g_total: float = 0.0
    market_pressure: float = 0.0
    land_scarity: float = 0.0
    total_demand: float = 0.0
    available_supply: float = 1.0

    def as_dict(self) -> dict:
        return {
            "g_market": round(self.g_market, 5),
            "g_demand": round(self.g_demand, 5),
            "g_infra": round(self.g_infra, 5),
            "g_scarity": round(self.g_scarity, 5),
            "g_risk": round(self.g_risk, 5),
            "g_total": round(self.g_total, 5),
            "market_pressure": round(self.market_pressure, 5),
            "land_scarity": round(self.land_scarity, 5),
            "total_demand": round(self.total_demand, 5),
            "available_supply": round(self.available_supply, 5),
        }


class MarketDynamicsEngine:
    """Compute annual land-price growth from market state + calibration."""

    # Demand-side composition weights.
    W_RESIDENTIAL = 0.50
    W_COMMERCIAL = 0.30
    W_DEVELOPER = 0.20
    # Supply release: how much a zoning relaxation (supply up) dampens pressure.
    SUPPLY_RESPONSE = 0.40

    def __init__(self, calibration: Optional[CalibrationParams] = None) -> None:
        self.calibration = calibration

    def for_locality(self, locality: str) -> "MarketDynamicsEngine":
        """Return an engine bound to a locality's calibrated parameters."""
        return MarketDynamicsEngine(calibrate_locality(locality))

    # ------------------------------------------------------------------
    def compute_growth(self, state: MarketState, calibration: Optional[CalibrationParams] = None) -> YearGrowth:
        cal = calibration or self.calibration or calibrate_locality("")

        # --- demand / supply balance ------------------------------------
        total_demand = (
            self.W_RESIDENTIAL * state.residential_demand
            + self.W_COMMERCIAL * max(0.0, state.commercial_demand)
            + self.W_DEVELOPER * state.developer_demand
        )
        # Available developable supply: more zoning => more supply; more
        # developer activity (developed units) slowly depletes the easy supply.
        supply_depletion = min(0.5, 0.01 * state.developed_units)
        available_supply = _clamp(state.zoning_factor - supply_depletion, 0.4, 1.6)

        # Market pressure = demand minus the supply response. Positive =>
        # upward price pressure; an oversupply (supply > 1) pushes it negative.
        market_pressure = total_demand - self.SUPPLY_RESPONSE * (available_supply - 1.0)

        # --- scarcity ----------------------------------------------------
        # Scarcity rises with the locality's inherent scarcity and falls when
        # zoning relaxes (supply release). Reported as a deviation vs the
        # locality baseline so steady-state adds ~0.
        land_scarity = _clamp(
            cal.locality_scarcity + 0.25 * (1.0 - available_supply), 0.0, 1.0
        )

        # --- growth decomposition (deviations vs baseline) --------------
        g_market = cal.baseline_annual_growth
        g_demand = cal.demand_sensitivity * market_pressure
        g_scarity = cal.scarcity_sensitivity * (land_scarity - cal.locality_scarcity)
        g_risk = cal.risk_sensitivity * max(0.0, (state.interest_rate - state.base_interest_rate) / 100.0)

        # Infrastructure attribution: the share of demand-driven growth that is
        # due to the Impact Engine's influence rather than baseline demand.
        # This is reported as g_infra but is NOT added to g_total (no double
        # counting) — it partitions g_demand.
        base_demand = max(1e-6, abs(total_demand) - state.infrastructure_influence)
        if state.infrastructure_influence > 0 and total_demand > 0:
            infra_share = state.infrastructure_influence / (state.infrastructure_influence + base_demand)
        else:
            infra_share = 0.0
        g_infra = g_demand * infra_share

        # Keep growth sane: bound the annual move so a single shock can't explode.
        g_total = g_market + g_demand + g_scarity - g_risk
        g_total = _clamp(g_total, -0.25, 0.45)

        return YearGrowth(
            g_market=g_market,
            g_demand=g_demand,
            g_infra=g_infra,
            g_scarity=g_scarity,
            g_risk=g_risk,
            g_total=g_total,
            market_pressure=market_pressure,
            land_scarity=land_scarity,
            total_demand=total_demand,
            available_supply=available_supply,
        )


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
