"""Historical Market Calibration Engine.

Estimates per-locality baseline land-price appreciation (CAGR) and the
sensitivities the Market Dynamics Engine uses to convert market pressure,
scarcity, infrastructure influence and rate risk into annual growth.

To avoid evaluating the model on the same data used to fit it, observations are
split into a **calibration** period (earlier years) and a **validation** period
(later years). CAGR is fit on the calibration period; the validation period is
used to report a directional out-of-sample check (exposed via
:meth:`CalibrationParams.validation_cagr`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from app.calibration.data import CITY_WIDE_DEFAULTS, LOCALITY_HISTORY


@dataclass
class CalibrationParams:
    """Calibrated parameters for one locality (or the city-wide default)."""

    locality: str
    baseline_annual_growth: float  # g_market: structural CAGR (fraction/yr)
    demand_sensitivity: float
    scarcity_sensitivity: float
    infrastructure_sensitivity: float
    risk_sensitivity: float
    locality_scarcity: float  # [0,1]; high = little developable land
    calibration_cagr: float = 0.0
    validation_cagr: float = 0.0
    calibration_years: tuple[int, int] = (0, 0)
    validation_years: tuple[int, int] = (0, 0)
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "locality": self.locality,
            "baseline_annual_growth": round(self.baseline_annual_growth, 4),
            "demand_sensitivity": round(self.demand_sensitivity, 4),
            "scarcity_sensitivity": round(self.scarcity_sensitivity, 4),
            "infrastructure_sensitivity": round(self.infrastructure_sensitivity, 4),
            "risk_sensitivity": round(self.risk_sensitivity, 4),
            "locality_scarcity": round(self.locality_scarcity, 4),
            "calibration_cagr": round(self.calibration_cagr, 4),
            "validation_cagr": round(self.validation_cagr, 4),
        }


class HistoricalCalibrationEngine:
    """Fit per-locality calibration parameters from historical observations."""

    def __init__(self, history: Optional[list[dict]] = None, validation_fraction: float = 0.3) -> None:
        self.history = history if history is not None else LOCALITY_HISTORY
        self.validation_fraction = max(0.1, min(0.5, validation_fraction))
        self._cache: dict[str, CalibrationParams] = {}

    # ------------------------------------------------------------------
    def calibrate(self, locality: str) -> CalibrationParams:
        """Return calibration parameters for a locality (city-wide default fallback)."""
        key = (locality or "").strip().lower()
        if key in self._cache:
            return self._cache[key]
        rows = [r for r in self.history if r["locality"].strip().lower() == key]
        rows.sort(key=lambda r: r["year"])
        if not rows:
            params = self._city_wide(key or "city-wide")
            self._cache[key] = params
            return params

        cal_rows, val_rows = self._split(rows)
        cal_cagr = _cagr(cal_rows)
        val_cagr = _cagr(val_rows) if len(val_rows) >= 2 else cal_cagr

        # Scarcity: mature, high-price localities have less developable land.
        latest_price = rows[-1]["land_price_per_sqft"]
        scarcity = _scarcity_from_price(latest_price)

        # Sensitivities scale with how volatile / fast-growing the locality is.
        growth = max(0.0, cal_cagr)
        d = CITY_WIDE_DEFAULTS
        demand_sens = _clamp(d["demand_sensitivity"] * (0.7 + growth / 0.07), 0.1, 0.8)
        infra_sens = _clamp(d["infrastructure_sensitivity"] * (0.8 + growth / 0.07), 0.1, 0.9)
        scarcity_sens = _clamp(d["scarcity_sensitivity"] * (0.6 + scarcity), 0.05, 0.4)
        risk_sens = d["risk_sensitivity"]

        params = CalibrationParams(
            locality=key,
            baseline_annual_growth=max(0.0, cal_cagr),
            demand_sensitivity=demand_sens,
            scarcity_sensitivity=scarcity_sens,
            infrastructure_sensitivity=infra_sens,
            risk_sensitivity=risk_sens,
            locality_scarcity=scarcity,
            calibration_cagr=cal_cagr,
            validation_cagr=val_cagr,
            calibration_years=(cal_rows[0]["year"], cal_rows[-1]["year"]) if cal_rows else (0, 0),
            validation_years=(val_rows[0]["year"], val_rows[-1]["year"]) if val_rows else (0, 0),
        )
        self._cache[key] = params
        return params

    def _split(self, rows: list[dict]) -> tuple[list[dict], list[dict]]:
        """Calibration = earliest (1 - f) of years; validation = latest f."""
        n = len(rows)
        if n < 4:
            # Too few points: calibrate on all, validate on the last two.
            return rows, rows[-2:] if n >= 2 else rows
        n_val = max(2, int(round(n * self.validation_fraction)))
        return rows[: n - n_val], rows[n - n_val :]

    def _city_wide(self, locality: str) -> CalibrationParams:
        d = CITY_WIDE_DEFAULTS
        return CalibrationParams(
            locality=locality,
            baseline_annual_growth=d["baseline_annual_growth"],
            demand_sensitivity=d["demand_sensitivity"],
            scarcity_sensitivity=d["scarcity_sensitivity"],
            infrastructure_sensitivity=d["infrastructure_sensitivity"],
            risk_sensitivity=d["risk_sensitivity"],
            locality_scarcity=d["locality_scarcity"],
        )

    # ------------------------------------------------------------------
    def observed_price(self, locality: str, year: int) -> Optional[float]:
        """Closest-in-time observed land price/sqft for a locality (backtesting)."""
        rows = [r for r in self.history if r["locality"].strip().lower() == (locality or "").strip().lower()]
        if not rows:
            return None
        rows.sort(key=lambda r: abs(r["year"] - year))
        return rows[0]["land_price_per_sqft"]


def _cagr(rows: list[dict]) -> float:
    """Compound annual growth rate across a sorted (by year) series."""
    if len(rows) < 2:
        return 0.0
    first, last = rows[0], rows[-1]
    n_years = max(1, last["year"] - first["year"])
    p0 = max(1.0, first["land_price_per_sqft"])
    p1 = last["land_price_per_sqft"]
    if p1 <= 0:
        return 0.0
    return math.pow(p1 / p0, 1.0 / n_years) - 1.0


def _scarcity_from_price(price_per_sqft: float) -> float:
    """Higher-priced mature localities are scarcer (less developable land)."""
    # Map a price/sqft in [1000, 25000] to a scarcity index in [0.1, 0.9].
    import math as _m

    norm = (price_per_sqft - 1000.0) / (25000.0 - 1000.0)
    return _clamp(0.1 + 0.8 * max(0.0, min(1.0, norm)), 0.1, 0.9)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# Module-level singleton (calibration is deterministic / cheap to cache).
_ENGINE: Optional[HistoricalCalibrationEngine] = None


def get_calibration_engine() -> HistoricalCalibrationEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = HistoricalCalibrationEngine()
    return _ENGINE


def calibrate_locality(locality: str) -> CalibrationParams:
    return get_calibration_engine().calibrate(locality)
