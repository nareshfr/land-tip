"""Year-0 baseline valuation seed.

Integrates the pre-existing ``predict_price.py`` CatBoost pipeline. The model
file (``catboost_house_price_model.cbm``) and metadata live at the project root
and are loaded lazily.

The seed produces a :class:`app.schemas.BaselineValuation`, which carries:
    - predicted price (lakhs + INR)
    - price per sqft
    - a confidence score (heuristic: higher when the requested location was seen
      frequently during model training)
    - the engineered feature vector used by the model (for traceability)
    - the raw model output

This output is the anchor every agent cluster and the future-valuation model
initialise against.
"""

from __future__ import annotations

import logging
import sys
from threading import Lock
from typing import Optional

from app.config import get_settings
from app.schemas import BaselineValuation
from app.baseline.land_adjust import LandBaselineAdjuster, apply_land_confidence

logger = logging.getLogger(__name__)

# Make the project root importable so we can import the existing predictor.
_PROJECT_ROOT = get_settings().project_root
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from predict_price import (  # type: ignore[import-not-found]
        ALL_FEATURES,
        PricePredictorPipeline,
    )
except Exception as exc:  # pragma: no cover - depends on root module presence
    raise RuntimeError(
        "Could not import pre-existing predict_price.PricePredictorPipeline. "
        "Ensure predict_price.py is at the project root."
    ) from exc


class BaselineSeed:
    """Lazily-loaded wrapper around the pre-existing CatBoost model."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._pipeline: Optional[PricePredictorPipeline] = None

    def _ensure_loaded(self) -> PricePredictorPipeline:
        if self._pipeline is not None:
            return self._pipeline
        with self._lock:
            if self._pipeline is None:
                settings = get_settings()
                model_path = settings.baseline_model_abs
                meta_path = settings.baseline_metadata_abs
                if not model_path.exists() or not meta_path.exists():
                    raise FileNotFoundError(
                        f"Baseline model artifacts missing: {model_path}, {meta_path}"
                    )
                pipe = PricePredictorPipeline()
                # predict_price works relative to the CWD; chdir to root for load.
                import os

                cwd = os.getcwd()
                try:
                    os.chdir(settings.project_root)
                    pipe.load(str(model_path), str(meta_path))
                finally:
                    os.chdir(cwd)
                self._pipeline = pipe
                logger.info("Baseline CatBoost model loaded.")
            return self._pipeline

    def is_ready(self) -> bool:
        s = get_settings()
        return s.baseline_model_abs.exists() and s.baseline_metadata_abs.exists()

    def evaluate(
        self,
        location: str,
        total_sqft: float,
        bhk: float = 3.0,
        bath: float = 2.0,
        balcony: float = 1.0,
        area_type: str = "Plot  Area",
        availability: str = "Ready To Move",
        society: str = "Unknown",
    ) -> BaselineValuation:
        """Run the pre-existing model for a single parcel and return the seed."""
        pipe = self._ensure_loaded()
        raw = pipe.predict(
            location=location,
            total_sqft=total_sqft,
            bhk=bhk,
            bath=bath,
            balcony=balcony,
            area_type=area_type,
            availability=availability,
            society=society,
        )

        # Feature vector: re-engineer the same features the model used so the
        # downstream clusters can reason about the baseline feature space.
        feature_vector = self._feature_vector(
            location, total_sqft, bhk, bath, balcony, area_type, availability, society
        )

        confidence = self._confidence(raw, total_sqft)

        # Phase 1 (v1.1): verify the baseline asset type. The CatBoost model is a
        # house-price model; derive a land-only baseline from its prediction.
        is_plot = bool(feature_vector.get("is_plot", 0))
        adjuster = LandBaselineAdjuster()
        adj = adjuster.adjust(
            house_price_lakhs=raw["predicted_price_lakhs"],
            total_sqft=total_sqft,
            area_type=area_type,
            is_plot=is_plot,
        )
        land_price_lakhs = adj.land_price_lakhs
        land_price_inr = int(round(land_price_lakhs * 100_000.0))
        land_ppsqft = round(land_price_inr / float(total_sqft), 2)
        confidence = apply_land_confidence(confidence)

        baseline_raw = dict(raw)
        baseline_raw["house_price_lakhs"] = adj.house_price_lakhs
        baseline_raw["structure_value_lakhs"] = adj.structure_value_lakhs
        baseline_raw["baseline_note"] = adj.note

        return BaselineValuation(
            predicted_price_lakhs=round(land_price_lakhs, 2),
            predicted_price_inr=land_price_inr,
            price_per_sqft_inr=land_ppsqft,
            location_used=raw["location_used"],
            total_sqft=raw["total_sqft"],
            bhk=raw["bhk"],
            bath=raw["bath"],
            area_type=raw["area_type"],
            confidence=confidence,
            feature_vector=feature_vector,
            asset_type=adj.asset_type,
            baseline_method=adj.baseline_method,
            house_price_lakhs=adj.house_price_lakhs,
            raw=baseline_raw,
        )

    # --- internals ---
    def _feature_vector(
        self, location, total_sqft, bhk, bath, balcony, area_type, availability, society
    ) -> dict:
        """Re-derive the engineered feature vector without re-running prediction."""
        pipe = self._ensure_loaded()
        import pandas as pd

        sample_df = pd.DataFrame([{
            "location": location,
            "total_sqft": total_sqft,
            "total_sqft_clean": float(total_sqft),
            "bhk": float(bhk),
            "size": f"{int(bhk)} BHK",
            "bath": float(bath),
            "balcony": float(balcony),
            "area_type": area_type,
            "availability": availability,
            "society": society,
        }])
        proc = pipe.transform_features(sample_df)
        return {feat: _coerce(proc[feat].iloc[0]) for feat in ALL_FEATURES}

    def _confidence(self, raw: dict, total_sqft: float) -> float:
        """Heuristic confidence in [0,1].

        Higher when the location was seen frequently during training (i.e. not
        bucketed into 'Other') and the area is within a plausible range.
        """
        score = 0.5
        if raw.get("location_used") and raw["location_used"] != "Other":
            score += 0.3
        else:
            score -= 0.1
        if 300.0 <= float(total_sqft) <= 10000.0:
            score += 0.2
        else:
            score -= 0.1
        return round(max(0.0, min(1.0, score)), 3)


def _coerce(v):
    """Make numpy/pandas scalars JSON-serialisable."""
    try:
        import numpy as np

        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
    except Exception:
        pass
    if isinstance(v, float):
        return v
    return v if isinstance(v, (int, str, bool, type(None))) else str(v)


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_seed: Optional[BaselineSeed] = None
_seed_lock = Lock()


def get_seed() -> BaselineSeed:
    global _seed
    if _seed is None:
        with _seed_lock:
            if _seed is None:
                _seed = BaselineSeed()
    return _seed


def baseline_valuation(
    location: str,
    total_sqft: float,
    bhk: float = 3.0,
    bath: float = 2.0,
    balcony: float = 1.0,
    area_type: str = "Plot  Area",
    availability: str = "Ready To Move",
    society: str = "Unknown",
) -> BaselineValuation:
    return get_seed().evaluate(
        location=location,
        total_sqft=total_sqft,
        bhk=bhk,
        bath=bath,
        balcony=balcony,
        area_type=area_type,
        availability=availability,
        society=society,
    )
