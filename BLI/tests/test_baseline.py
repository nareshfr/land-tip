"""Year-0 baseline valuation seed tests (wraps the pre-existing CatBoost model)."""

from __future__ import annotations

import pytest

from app.baseline import baseline_valuation, get_seed


@pytest.mark.skipif(not get_seed().is_ready(), reason="baseline model artifacts missing")
def test_baseline_returns_plausible_price():
    v = baseline_valuation(
        location="Whitefield", total_sqft=2400, bhk=3, bath=2, balcony=1,
        area_type="Plot  Area", availability="Ready To Move",
    )
    assert v.predicted_price_lakhs > 0
    assert isinstance(v.predicted_price_inr, int)
    assert v.predicted_price_inr > 0
    # price/sqft is derived from the same predicted price (rounded to 2 dp).
    assert v.price_per_sqft_inr == pytest.approx(
        v.predicted_price_inr / 2400, abs=0.05
    )
    assert 0.0 <= v.confidence <= 1.0
    # Feature vector carries every engineered feature the model uses.
    expected = {"area_type", "location_grouped", "society_grouped", "log_sqft",
                "bhk", "bath", "balcony", "sqft_per_bhk", "bath_to_bhk",
                "bath_diff_bhk", "total_rooms", "sqft_per_room", "is_ready",
                "is_plot", "has_society"}
    assert expected.issubset(set(v.feature_vector.keys()))


@pytest.mark.skipif(not get_seed().is_ready(), reason="baseline model artifacts missing")
def test_known_location_has_higher_confidence():
    known = baseline_valuation(location="Whitefield", total_sqft=2400)
    unknown = baseline_valuation(location="Nowhereville", total_sqft=2400)
    assert known.location_used != "Other"
    assert known.confidence >= unknown.confidence
