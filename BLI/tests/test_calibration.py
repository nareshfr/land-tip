"""Historical Market Calibration tests."""

from __future__ import annotations

import pytest

from app.calibration.data import list_localities
from app.calibration.engine import (
    HistoricalCalibrationEngine,
    calibrate_locality,
    get_calibration_engine,
)


def test_calibrate_known_locality():
    params = calibrate_locality("Whitefield")
    assert params.locality == "whitefield"
    assert params.baseline_annual_growth > 0.05
    assert params.calibration_cagr > 0.0
    assert 0.0 <= params.locality_scarcity <= 1.0


def test_calibrate_doddaballapur_has_lower_scarcity_than_indiranagar():
    dodd = calibrate_locality("doddaballapur")
    indi = calibrate_locality("indiranagar")

    # Indiranagar has much higher price/sqft and less developable land than Doddaballapur
    assert indi.locality_scarcity > dodd.locality_scarcity


def test_calibration_validation_split():
    engine = HistoricalCalibrationEngine()
    params = engine.calibrate("electronic city")
    cal_start, cal_end = params.calibration_years
    val_start, val_end = params.validation_years

    assert cal_start < cal_end <= val_start < val_end
    assert params.calibration_cagr > 0
    assert params.validation_cagr > 0


def test_unknown_locality_falls_back_to_city_wide():
    params = calibrate_locality("UnknownPlaceXYZ")
    assert params.baseline_annual_growth == 0.07  # city-wide default
    assert params.locality_scarcity == 0.30
