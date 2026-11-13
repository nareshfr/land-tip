"""Simulation engine + future valuation tests."""

from __future__ import annotations

import pytest

from app.baseline import baseline_valuation
from app.schemas import SimulationConfig
from app.simulation.engine import run_simulation
from app.simulation.valuation import compute_future_valuation
from app.spatial.localities import locality_centroid


def _infra():
    return [
        {"project_id": "metro", "name": "Whitefield Metro", "source": "BMRCL",
         "type": "metro", "status": "UNDER_CONSTRUCTION",
         "announcement_date": "2020-01-01", "geometry": "POINT (77.7499 12.9696)"},
        {"project_id": "park", "name": "Agara Park", "source": "news",
         "type": "park", "status": "PROPOSED", "announcement_date": "2023-01-01",
         "geometry": "POINT (77.647 12.919)"},
    ]


def test_run_simulation_timeline_length_matches_years():
    base = baseline_valuation(location="Whitefield", total_sqft=2400)
    centroid = locality_centroid("Whitefield")
    cfg = SimulationConfig(years=5, households=20, developers=3, seed=11)
    out = run_simulation(base, _infra(), centroid, cfg, total_sqft=2400)
    assert len(out["timeline"]) == cfg.years + 1
    assert out["timeline"][0]["year"] == 0
    assert out["timeline"][-1]["year"] == cfg.years


def test_future_valuation_anchors_to_baseline():
    base = baseline_valuation(location="Whitefield", total_sqft=2400)
    centroid = locality_centroid("Whitefield")
    cfg = SimulationConfig(years=5, households=20, developers=3, seed=11)
    out = run_simulation(base, _infra(), centroid, cfg, total_sqft=2400)
    fv = out["future_valuation"]
    assert fv["baseline_price_per_sqft"] == base.price_per_sqft_inr
    assert fv["land_value_index"] == out["timeline"][-1]["land_value_index"]
    assert fv["future_price_lakhs"] == pytest.approx(
        fv["future_price_per_sqft"] * 2400 / 100_000.0, abs=0.01
    )
    assert {"demand_pressure", "infrastructure", "macro_risk"} <= set(fv["drivers"])


def test_compute_future_valuation_flat_timeline():
    fv = compute_future_valuation(
        baseline_ppsqft=7000.0, total_sqft=2400,
        timeline=[{"land_value_index": 1.0, "interest_rate": 8.5}],
        baseline_price_lakhs=168.0,
    )
    assert fv["future_price_lakhs"] == 168.0
    assert fv["appreciation_pct"] == 0.0
