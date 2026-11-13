"""Simulation engine: wires baseline seed + scraped infrastructure into the Mesa
model, runs Years 0..N, and returns the timeline + future valuation.
"""

from __future__ import annotations

from shapely.geometry import Point

from app.agents.model import UrbanAlphaModel
from app.config import get_settings
from app.schemas import BaselineValuation, SimulationConfig
from app.simulation.valuation import compute_future_valuation
from app.spatial.buffers import buffer_impact, parse_geometry


def build_model(
    baseline: BaselineValuation,
    infrastructure: list[dict],
    parcel_centroid: Point,
    config: SimulationConfig,
) -> UrbanAlphaModel:
    """Construct the Mesa model and tag projects within 2km of the parcel."""
    radii = get_settings().buffer_radii_m
    # Determine which projects fall within the largest buffer radius.
    impacts = buffer_impact(infrastructure, parcel_centroid, (max(radii),))
    within_ids = {p.get("project_id") for p in impacts[max(radii)]["projects"]}

    model = UrbanAlphaModel(
        baseline=baseline,
        infrastructure=infrastructure,
        years=config.years,
        households=config.households,
        developers=config.developers,
        initial_interest_rate=config.initial_interest_rate,
        capital_availability=config.capital_availability,
        seed=config.seed,
    )
    model.set_within_2km(within_ids)
    return model


def run_simulation(
    baseline: BaselineValuation,
    infrastructure: list[dict],
    parcel_centroid: Point,
    config: SimulationConfig,
    total_sqft: float,
) -> dict:
    """Run the Mesa simulation and return timeline + future valuation + summary."""
    model = build_model(baseline, infrastructure, parcel_centroid, config)
    # Step through the horizon (one step == one year after Year 0).
    for _ in range(config.years):
        model.step()
        if not model.running:
            break

    timeline = [dict(snap) for snap in model.timeline]
    future = compute_future_valuation(
        baseline_ppsqft=baseline.price_per_sqft_inr,
        total_sqft=total_sqft,
        timeline=timeline,
        baseline_price_lakhs=baseline.predicted_price_lakhs,
    )

    summary = _summarise(timeline, future)
    return {
        "timeline": timeline,
        "future_valuation": future,
        "summary": summary,
    }


def _summarise(timeline: list[dict], future: dict) -> dict:
    if not timeline:
        return {}
    last = timeline[-1]
    return {
        "years_simulated": last.get("year", 0),
        "final_interest_rate": last.get("interest_rate"),
        "final_land_value_index": last.get("land_value_index"),
        "final_land_value_per_sqft": last.get("land_value_per_sqft"),
        "future_price_lakhs": future.get("future_price_lakhs"),
        "appreciation_pct": future.get("appreciation_pct"),
        "final_demand_pressure": last.get("demand_pressure"),
        "final_supply_pressure": last.get("supply_pressure"),
        "active_infrastructure": last.get("active_infrastructure"),
    }
