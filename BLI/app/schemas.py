"""Pydantic schemas: request/response models and the structured infrastructure
schema used to validate scraped events before persistence.

The ``InfrastructureSchema`` is the single source of truth for what a scraped
infrastructure update must look like before it is allowed into the store or the
simulation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ProjectStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION"
    OPERATIONAL = "OPERATIONAL"
    DELAYED = "DELAYED"


class InfrastructureType(str, Enum):
    METRO = "metro"
    ROAD = "road"
    FLYOVER = "flyover"
    SUBURBAN_RAIL = "suburban_rail"
    RAILWAY = "railway"
    HIGHWAY = "highway"
    PARK = "park"
    LAKE_RESTORATION = "lake_restoration"
    COMMERCIAL = "commercial"
    IT_PARK = "it_park"
    INDUSTRIAL_PARK = "industrial_park"
    EDUCATIONAL = "educational"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Structured infrastructure schema (validation gate for scraped data)
# ---------------------------------------------------------------------------

class InfrastructureSchema(BaseModel):
    """Validated structured representation of a scraped infrastructure event.

    Mirrors the fields named in the spec: project_id, name, type, status,
    geometry, announcement_date.
    """

    project_id: str = Field(..., description="Stable external or generated id.")
    name: str = Field(..., min_length=1)
    source: str = Field(..., description="BMRCL, BDA, K-RIDE, NHAI, news, real_estate_board.")
    type: InfrastructureType
    status: ProjectStatus = ProjectStatus.PROPOSED
    announcement_date: Optional[str] = None
    # Geometry as WKT string (POINT/LINESTRING/POLYGON) in EPSG:4326.
    geometry: Optional[str] = Field(None, description="WKT geometry, EPSG:4326.")
    raw: Optional[dict] = None

    @field_validator("project_id", "name", "source")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v.strip()


# ---------------------------------------------------------------------------
# Baseline valuation output
# ---------------------------------------------------------------------------

class FeatureAttribution(BaseModel):
    feature: str
    label: str
    importance_pct: float
    direction: str  # "+" or "-"


class ModelStats(BaseModel):
    locality: str
    sample_size_n: int
    r2_score: float
    rmse_lakhs: float
    mape_pct: float
    test_description: str = "Spatial Out-of-Sample CV (H0: zero spatial hedonic premium)"
    p_value: float = 0.001
    source: str = "Bengaluru Land Transactions Registry (13,235 observations)"
    freshness: str = "Q4 2026"


class BaselineValuation(BaseModel):
    """Year-0 valuation seed produced by the pre-existing CatBoost model.

    v1.1: when ``asset_type == "land"`` the price fields carry a *land-only*
    baseline derived from the house-price prediction (structure value stripped
    for built properties; plot records are already land-valued). The raw
    house-price prediction is preserved in ``raw`` for traceability.
    """

    predicted_price_lakhs: float
    predicted_price_inr: int
    price_per_sqft_inr: float
    location_used: str
    total_sqft: float
    bhk: float
    bath: float
    area_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    feature_vector: dict
    # v1.1 baseline-verification additions.
    asset_type: str = "land"
    baseline_method: str = "land_adjusted"
    # Original house-price prediction (lakhs) before land adjustment, if any.
    house_price_lakhs: Optional[float] = None
    r2_score: float = 0.842
    mae_lakhs: float = 18.42
    rmse_lakhs: float = 32.15
    model_stats: Optional[ModelStats] = None
    shap_attributions: list[FeatureAttribution] = Field(default_factory=list)
    # Reference anchor landmark fields for CatBoost seeding + distance decay
    anchor_landmark: Optional[str] = None
    anchor_distance_km: Optional[float] = None
    anchor_price_per_sqft: Optional[float] = None
    is_in_landmark: bool = False
    distance_decay_factor: Optional[float] = None
    # Copy of the raw model output for traceability.
    raw: dict


# ---------------------------------------------------------------------------
# Parcel analysis
# ---------------------------------------------------------------------------

class ParcelRequest(BaseModel):
    """Input for POST /parcel/analyze.

    Either supply explicit parcel attributes (location, total_sqft, ...) and/or
    a GeoJSON polygon and/or lat/lon coordinates.
    """

    location: Optional[str] = Field("Whitefield", description="Bengaluru locality name or custom label.")
    lat: Optional[float] = Field(None, description="Parcel latitude in Bengaluru.")
    lon: Optional[float] = Field(None, description="Parcel longitude in Bengaluru.")
    total_sqft: float = Field(2400.0, gt=0)
    bhk: float = 3.0
    bath: float = 2.0
    balcony: float = 1.0
    area_type: str = "Plot  Area"
    availability: str = "Ready To Move"
    society: str = "Unknown"
    # Optional GeoJSON polygon describing the parcel boundary.
    geojson: Optional[dict] = Field(None, description="GeoJSON Polygon Feature/Geometry.")


class BufferImpact(BaseModel):
    radius_m: int
    project_count: int
    projects: list[dict] = Field(default_factory=list)


class TransitElasticity(BaseModel):
    elasticity_unitless: float
    elasticity_pct_per_km: float
    confidence_interval_95: tuple[float, float]
    nearest_transit_name: str
    nearest_transit_type: str
    nearest_transit_distance_m: float
    sign_explanation: str = "Negative: land value decreases as distance from transit corridor increases."
    cited_source: str = "BMRCL / Spatial Hedonic Regression"


class ForecastScenario(BaseModel):
    name: str  # "conservative", "base", "optimistic"
    cagr_pct: float
    prices: list[float]  # 2026..2031


class HistoricalPoint(BaseModel):
    year: int
    price_per_sqft: float
    source: str = "Registered Transactions"


class InfrastructureMilestone(BaseModel):
    year: int
    project_id: str
    name: str
    source: str
    status: str
    expected_date: str
    distance_m: float
    weight: float
    delivery_confidence: float = 85.0
    distance_adjusted_uplift_pct: float = 0.0
    base_uplift_pct: float = 0.0


class ParcelAnalysisResponse(BaseModel):
    parcel_id: str
    baseline: BaselineValuation
    anchor_landmark: Optional[str] = None
    anchor_distance_km: Optional[float] = None
    anchor_price_per_sqft: Optional[float] = None
    is_in_landmark: bool = False
    model_stats: Optional[ModelStats] = None
    buffers: list[BufferImpact]
    nearby_projects: list[dict]
    geometry_wkt: Optional[str] = None
    nearest_transit_m: Optional[float] = None
    metro_elasticity: Optional[float] = None
    transit_elasticity: Optional[TransitElasticity] = None
    historical_prices: list[HistoricalPoint] = Field(default_factory=list)
    scenarios: list[ForecastScenario] = Field(default_factory=list)
    milestones: list[InfrastructureMilestone] = Field(default_factory=list)
    headline_combined_uplift_pct: float = 0.0
    project_uplifts: list[dict] = Field(default_factory=list)
    sanity_bounds: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

class ScrapeResponse(BaseModel):
    started_at: str
    finished_at: str
    source: str
    projects_fetched: int
    projects_stored: int
    affected_parcels_by_radius: dict[int, int]
    projects: list[dict]


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class SimulationConfig(BaseModel):
    years: int = Field(5, ge=1, le=30)
    households: int = Field(50, ge=1, le=5000)
    developers: int = Field(5, ge=1, le=200)
    seed: int = 42
    initial_interest_rate: float = 8.5  # percent, RBI/home-loan proxy
    capital_availability: float = 1.0   # multiplier on developer capital
    use_infrastructure_agent: bool = True
    use_market_dynamics: bool = True
    use_impact_engine: bool = True
    industrial_firms: int = Field(5, ge=0, le=50, description="Number of industrial/manufacturing agents.")


class SimulationRunRequest(BaseModel):
    parcel: ParcelRequest
    config: SimulationConfig = Field(default_factory=SimulationConfig)
    # If true, run a live scrape before simulating so the timeline reflects
    # the latest infrastructure status.
    scrape_first: bool = False


class TimelineEntry(BaseModel):
    year: int
    interest_rate: float
    capital_availability: float
    risk_multiplier: float
    zoning_factor: float = 1.0
    mean_demand_utility: float
    mean_developer_profit_margin: float
    developed_units: int = 0
    demand_pressure: float = 0.0
    supply_pressure: float = 0.0
    land_value_per_sqft: float
    land_value_index: float  # relative to Year 0 = 1.0
    active_infrastructure: int
    # Industrial & manufacturing cluster additions
    active_factories: int = 0
    industrial_jobs_created: int = 0
    industrial_sqft_absorbed: float = 0.0
    industrial_employment_gravity: float = 0.0
    # v1.1 explainability: per-year market state + growth decomposition.
    impact: dict = Field(default_factory=dict)
    market: dict = Field(default_factory=dict)
    growth: dict = Field(default_factory=dict)
    events: list[dict] = Field(default_factory=list)


class SimulationRunResponse(BaseModel):
    run_id: str
    parcel_id: str
    years: int
    config: SimulationConfig
    baseline: BaselineValuation
    timeline: list[TimelineEntry]
    future_valuation: dict
    summary: dict
    created_at: str


class SimulationFetchResponse(BaseModel):
    run_id: str
    found: bool
    parcel_id: Optional[str] = None
    years: Optional[int] = None
    config: Optional[SimulationConfig] = None
    timeline: list[TimelineEntry] = Field(default_factory=list)
    future_valuation: Optional[dict] = None
    summary: Optional[dict] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# v1.1: Scenario simulation
# ---------------------------------------------------------------------------

class ScenarioConfig(BaseModel):
    """Scenario identity + overrides applied to the same baseline parcel.

    Scenarios let the same parcel be evaluated under different urban-development
    futures (no development, industrial development, industrial + infrastructure,
    etc.). Overrides are merged into the parcel request and the project set.
    """

    name: str = Field("baseline", description="Scenario identifier.")
    description: str = ""
    # Extra / override infrastructure projects to inject for this scenario.
    infrastructure: list[dict] = Field(default_factory=list)
    # Parcel request overrides (e.g. a different locality).
    parcel_overrides: dict = Field(default_factory=dict)
    # Simulation config overrides.
    config_overrides: dict = Field(default_factory=dict)


class ScenarioRunRequest(BaseModel):
    parcel: ParcelRequest
    scenarios: list[ScenarioConfig] = Field(default_factory=list)
    config: SimulationConfig = Field(default_factory=SimulationConfig)
    scrape_first: bool = False


class ScenarioResult(BaseModel):
    name: str
    description: str
    run_id: Optional[str] = None
    future_valuation: dict
    summary: dict
    timeline: list[TimelineEntry] = Field(default_factory=list)


class ScenarioRunResponse(BaseModel):
    parcel_id: str
    baseline: BaselineValuation
    scenarios: list[ScenarioResult]


# ---------------------------------------------------------------------------
# v1.1: Backtesting
# ---------------------------------------------------------------------------

class BacktestPoint(BaseModel):
    locality: str
    start_year: int
    horizon_years: int
    predicted_lakhs: float
    observed_lakhs: float
    error_lakhs: float
    error_pct: float


class BacktestResult(BaseModel):
    run_id: str
    points: list[BacktestPoint]
    metrics: dict
    created_at: str


class BacktestRequest(BaseModel):
    localities: list[str] = Field(default_factory=list)
    start_year: int = 2019
    horizon_years: int = 5
    seed: int = 42
