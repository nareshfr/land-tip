"""Scenario Simulation & Backtesting tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    BacktestRequest,
    ParcelRequest,
    ScenarioConfig,
    ScenarioRunRequest,
    SimulationConfig,
)
from app.services.simulation_service import run_backtest, run_scenarios

client = TestClient(app)


def test_doddaballapur_three_scenarios():
    """Verify Section 11 proposal:
    Scenario A: No Major Development
    Scenario B: Industrial Development
    Scenario C: Industrial + Infrastructure Corridor
    Outcome: Appreciation C > Appreciation B > Appreciation A.
    """
    parcel = ParcelRequest(
        location="doddaballapur",
        total_sqft=2400.0,
        bhk=3.0,
        bath=2.0,
        balcony=1.0,
        area_type="Plot  Area",
    )
    req = ScenarioRunRequest(
        parcel=parcel,
        config=SimulationConfig(years=5, seed=42),
    )
    resp = run_scenarios(req)

    assert resp.parcel_id
    assert len(resp.scenarios) == 3

    sc_a, sc_b, sc_c = resp.scenarios[0], resp.scenarios[1], resp.scenarios[2]
    apprec_a = sc_a.future_valuation["appreciation_pct"]
    apprec_b = sc_b.future_valuation["appreciation_pct"]
    apprec_c = sc_c.future_valuation["appreciation_pct"]

    # Verify meaningful differentiation as required by Version 1.1 spec
    assert apprec_c > apprec_b > apprec_a
    assert sc_c.future_valuation["future_price_lakhs"] > sc_b.future_valuation["future_price_lakhs"] > sc_a.future_valuation["future_price_lakhs"]


def test_backtest_evaluation_metrics():
    """Verify Backtesting produces MAE, RMSE, MAPE, ranking accuracy, and compares against simple baseline."""
    req = BacktestRequest(
        localities=["whitefield", "sarjapur road", "electronic city", "hebbal", "doddaballapur"],
        start_year=2019,
        horizon_years=5,
        seed=42,
    )
    res = run_backtest(req)

    assert res.run_id
    assert len(res.points) == 5
    m = res.metrics
    assert m["n_points"] == 5
    assert m["mae_lakhs"] >= 0.0
    assert m["rmse_lakhs"] >= 0.0
    assert m["mape_pct"] >= 0.0
    assert "ranking_accuracy_spearman" in m
    assert "historical_growth_baseline_mae_lakhs" in m


def test_api_scenarios_endpoint():
    payload = {
        "parcel": {
            "location": "Whitefield",
            "total_sqft": 2000,
            "bhk": 3,
            "bath": 2,
            "balcony": 1,
            "area_type": "Plot  Area",
        },
        "config": {"years": 3, "seed": 42},
    }
    resp = client.post("/simulation/scenarios", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) >= 3


def test_api_backtest_endpoint():
    payload = {
        "localities": ["whitefield", "doddaballapur"],
        "start_year": 2019,
        "horizon_years": 5,
        "seed": 42,
    }
    resp = client.post("/simulation/backtest", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "points" in data
    assert len(data["points"]) == 2
