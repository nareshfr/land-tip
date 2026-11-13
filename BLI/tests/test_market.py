"""Market Dynamics Engine tests."""

from __future__ import annotations

import pytest

from app.calibration.engine import CalibrationParams
from app.market.dynamics import MarketDynamicsEngine, MarketState


def _cal():
    return CalibrationParams(
        locality="test_loc",
        baseline_annual_growth=0.08,
        demand_sensitivity=0.4,
        scarcity_sensitivity=0.2,
        infrastructure_sensitivity=0.4,
        risk_sensitivity=0.5,
        locality_scarcity=0.3,
    )


def test_market_dynamics_demand_increase_boosts_growth():
    engine = MarketDynamicsEngine(_cal())
    state_low = MarketState(residential_demand=0.0)
    state_high = MarketState(residential_demand=0.5)

    g_low = engine.compute_growth(state_low)
    g_high = engine.compute_growth(state_high)

    assert g_high.g_demand > g_low.g_demand
    assert g_high.g_total > g_low.g_total
    assert g_high.market_pressure > g_low.market_pressure


def test_oversupply_dampens_price_pressure():
    engine = MarketDynamicsEngine(_cal())
    state_normal = MarketState(residential_demand=0.3, zoning_factor=1.0)
    state_oversupply = MarketState(residential_demand=0.3, zoning_factor=1.5)

    g_normal = engine.compute_growth(state_normal)
    g_over = engine.compute_growth(state_oversupply)

    assert g_over.available_supply > g_normal.available_supply
    assert g_over.market_pressure < g_normal.market_pressure
    assert g_over.g_total < g_normal.g_total


def test_no_double_counting_infrastructure():
    """Verify g_infra partitions g_demand rather than adding on top."""
    engine = MarketDynamicsEngine(_cal())
    state = MarketState(
        residential_demand=0.6,
        infrastructure_influence=0.3,
    )
    g = engine.compute_growth(state)

    # g_infra must be less than or equal to g_demand
    assert 0.0 < g.g_infra <= g.g_demand
    # g_total must equal g_market + g_demand + g_scarity - g_risk (not + g_infra)
    expected_total = g.g_market + g.g_demand + g.g_scarity - g.g_risk
    assert g.g_total == pytest.approx(expected_total, abs=1e-5)
