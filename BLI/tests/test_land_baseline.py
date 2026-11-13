"""Land-baseline adjustment & asset verification tests (Phase 1)."""

from __future__ import annotations

import pytest

from app.baseline.land_adjust import LandBaselineAdjuster, apply_land_confidence
from app.config import get_settings


def test_plot_area_treated_as_direct_land_value():
    adjuster = LandBaselineAdjuster()
    adj = adjuster.adjust(
        house_price_lakhs=150.0,
        total_sqft=2000.0,
        area_type="Plot  Area",
        is_plot=True,
    )
    assert adj.asset_type == "land"
    assert adj.baseline_method == "plot_direct"
    assert adj.land_price_lakhs == 150.0
    assert adj.structure_value_lakhs == 0.0
    assert adj.is_plot is True


def test_built_property_deducts_structure_value():
    adjuster = LandBaselineAdjuster()
    # 2000 sqft at construction rate 2500 INR/sqft = 50 lakh structure value
    # house price 180 lakh -> land value 130 lakh
    adj = adjuster.adjust(
        house_price_lakhs=180.0,
        total_sqft=2000.0,
        area_type="Super built-up  Area",
        is_plot=False,
    )
    assert adj.asset_type == "land"
    assert adj.baseline_method == "land_adjusted"
    assert adj.structure_value_lakhs == 50.0
    assert adj.land_price_lakhs == 130.0
    assert adj.is_plot is False


def test_structure_value_exceeding_threshold_hits_floor():
    adjuster = LandBaselineAdjuster()
    # 3000 sqft at 2500 = 75 lakh structure value
    # house price 80 lakh -> 80 - 75 = 5 lakh (too low, below 40% floor = 32 lakh)
    adj = adjuster.adjust(
        house_price_lakhs=80.0,
        total_sqft=3000.0,
        area_type="Super built-up  Area",
        is_plot=False,
    )
    assert adj.asset_type == "land"
    assert adj.land_price_lakhs == 32.0  # 40% floor of 80
    assert "floored" in adj.note.lower()


def test_land_confidence_penalty():
    conf = apply_land_confidence(0.9)
    # Default land model confidence penalty is 0.9 -> 0.9 * 0.9 = 0.81
    assert conf == pytest.approx(0.81, abs=0.01)
