"""Land-baseline adjustment (Phase 1: baseline verification).

The pre-existing CatBoost model is a **house-price** model trained on
``bengaluru_house_prices.csv`` (features BHK, bath, balcony, area_type, ...). The
UrbanAlpha target is **land** valuation, so a house-price prediction cannot be
used unchanged as a land-price baseline:

  * For ``Plot  Area`` records (``is_plot == 1``) the prediction is already a
    plot/land transaction, so it is treated as the land value directly — but a
    confidence penalty is applied because the underlying model was not trained
    solely on land transactions.
  * For built properties (``is_plot == 0``) the house price = land value +
    structure value, so the estimated depreciated structure value is subtracted
    to isolate the residual land value (floored to ``land_value_floor_pct`` of
    the house price so the result can never go negative or implausibly low).

Set ``Settings.baseline_asset_type = "house"`` to bypass adjustment and use the
raw house-price prediction (legacy behaviour). A dedicated land-price model
trained on land transactions should replace this adjuster when such data is
available — the interface (``LandBaselineAdjuster.adjust``) stays the same.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import get_settings


@dataclass
class LandAdjustment:
    """Result of adjusting a house-price prediction to a land baseline."""

    asset_type: str          # "land" or "house"
    baseline_method: str     # "land_adjusted", "plot_direct" or "house_passthrough"
    land_price_lakhs: float
    house_price_lakhs: float
    structure_value_lakhs: float
    is_plot: bool
    note: str = ""


class LandBaselineAdjuster:
    """Convert a CatBoost house-price prediction into a land-only baseline."""

    def adjust(
        self,
        house_price_lakhs: float,
        total_sqft: float,
        area_type: str,
        is_plot: Optional[bool] = None,
    ) -> LandAdjustment:
        settings = get_settings()
        asset_type = settings.baseline_asset_type.strip().lower()

        # Resolve is_plot from area_type when not supplied.
        if is_plot is None:
            is_plot = _is_plot_area(area_type)

        house = max(0.0, float(house_price_lakhs))

        if asset_type != "land":
            return LandAdjustment(
                asset_type="house",
                baseline_method="house_passthrough",
                land_price_lakhs=house,
                house_price_lakhs=house,
                structure_value_lakhs=0.0,
                is_plot=is_plot,
                note="Raw house-price prediction used as the baseline (legacy).",
            )

        # Plot records are already land-valued.
        if is_plot:
            return LandAdjustment(
                asset_type="land",
                baseline_method="plot_direct",
                land_price_lakhs=house,
                house_price_lakhs=house,
                structure_value_lakhs=0.0,
                is_plot=True,
                note=(
                    "Plot record: prediction treated as land value directly "
                    "(confidence carries a land-model penalty)."
                ),
            )

        # Built property: subtract estimated structure value.
        structure_value_lakhs = self._structure_value_lakhs(total_sqft, settings)
        floor = settings.land_value_floor_pct * house
        land = house - structure_value_lakhs
        if land < floor:
            land = floor
            note = (
                "Structure value exceeded price; land value floored to "
                f"{settings.land_value_floor_pct:.0%} of house price."
            )
        else:
            note = "Land value = house price minus estimated structure value."

        return LandAdjustment(
            asset_type="land",
            baseline_method="land_adjusted",
            land_price_lakhs=round(land, 2),
            house_price_lakhs=round(house, 2),
            structure_value_lakhs=round(structure_value_lakhs, 2),
            is_plot=False,
            note=note,
        )

    # ------------------------------------------------------------------
    def _structure_value_lakhs(self, total_sqft: float, settings) -> float:
        """Estimated structure (built-up) value in lakh.

        Uses the construction rate per sqft. New construction (no depreciation
        applied) gives a conservative — i.e. higher — structure value, which
        yields a conservative (lower) residual land value.
        """
        rate = settings.construction_rate_per_sqft
        structure_inr = rate * max(0.0, float(total_sqft))
        return structure_inr / 100_000.0


def apply_land_confidence(confidence: float) -> float:
    """Apply the land-model confidence penalty when the baseline is land-derived."""
    settings = get_settings()
    if settings.baseline_asset_type.strip().lower() != "land":
        return confidence
    penalty = settings.land_model_confidence_penalty
    return round(max(0.0, min(1.0, confidence * penalty)), 3)


def _is_plot_area(area_type: str) -> bool:
    return bool(area_type and "plot" in area_type.strip().lower())
