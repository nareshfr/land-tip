"""Historical Market Calibration Engine.

Grounds the simulation in observed Bengaluru land-price behaviour instead of
arbitrary appreciation assumptions. Exposes per-locality baseline appreciation
and demand / scarcity / infrastructure / risk sensitivities used to initialise
and constrain the Market Dynamics Engine.

    data.py   - starter historical land-price observations per locality
    engine.py - HistoricalCalibrationEngine (CAGR + sensitivities, with a
                calibration/validation split)
"""

from app.calibration.engine import CalibrationParams, HistoricalCalibrationEngine
from app.calibration.data import LOCALITY_HISTORY, list_localities

__all__ = [
    "HistoricalCalibrationEngine",
    "CalibrationParams",
    "LOCALITY_HISTORY",
    "list_localities",
]
