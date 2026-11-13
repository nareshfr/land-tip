"""Application settings loaded from environment / .env.

Settings are intentionally tolerant: the app runs with zero configuration using
an in-memory store and the bundled baseline model, so tests and local dev need
no database or external services.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of the app/ package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Persistence. Empty string => in-memory repository.
    database_url: str = ""

    # Baseline model artifacts. Resolved relative to PROJECT_ROOT when not absolute.
    baseline_model_path: str = "catboost_house_price_model.cbm"
    baseline_metadata_path: str = "preprocessor_metadata.json"
    baseline_csv_path: str = "bengaluru_house_prices.csv"

    # Simulation.
    simulation_years: int = 5

    # Scraping cluster.
    scrape_timeout_seconds: int = 20
    scrape_user_agent: str = "UrbanAlpha-GeoAI-Research-Bot/1.0"
    scrape_enabled: bool = True
    # When False, use bundled offline fixtures instead of live external URLs.
    scrape_live: bool = False

    # Spatial buffer radii in metres.
    buffer_radii_m: tuple[int, ...] = (500, 1000, 2000)

    # --- v1.1 baseline asset verification ---------------------------------
    # The pre-existing CatBoost model is a *house*-price model. UrbanAlpha's
    # target is *land* valuation, so by default we derive a land-only baseline
    # from the house-price prediction (strip estimated structure value for
    # built properties; plot records are already land-valued). Set to "house"
    # to use the raw house-price prediction unchanged (legacy behaviour).
    baseline_asset_type: str = "land"
    # Construction cost per sqft (INR) used to estimate structure value.
    construction_rate_per_sqft: float = 2500.0
    # Floor for derived land value as a fraction of the house-price prediction,
    # so the adjustment can never go negative or implausibly low.
    land_value_floor_pct: float = 0.40
    # Confidence penalty applied when the baseline is derived from a
    # house-price model rather than a dedicated land-price model.
    land_model_confidence_penalty: float = 0.9

    # Bengaluru reference centroid used to approximate metres <-> degrees.
    # lat 12.9716, lon 77.5946. 1 deg lat ~= 110.574 km; 1 deg lon ~= cos(lat)*111.32 km.
    bengaluru_lat: float = 12.9716
    bengaluru_lon: float = 77.5946

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    def resolve_path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else (PROJECT_ROOT / p)

    @property
    def baseline_model_abs(self) -> Path:
        return self.resolve_path(self.baseline_model_path)

    @property
    def baseline_metadata_abs(self) -> Path:
        return self.resolve_path(self.baseline_metadata_path)

    @property
    def baseline_csv_abs(self) -> Path:
        return self.resolve_path(self.baseline_csv_path)

    @property
    def use_database(self) -> bool:
        return bool(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
