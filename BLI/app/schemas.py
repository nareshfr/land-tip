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
    PARK = "park"
    LAKE_RESTORATION = "lake_restoration"
    COMMERCIAL = "commercial"
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

class BaselineValuation(BaseModel):
    """Year-0 valuation seed produced by the pre-existing CatBoost model."""

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
    # Copy of the raw model output for traceability.
    raw: dict


# ---------------------------------------------------------------------------
# Parcel analysis
# ---------------------------------------------------------------------------

class ParcelRequest(BaseModel):
    """Input for POST /parcel/analyze.

    Either supply explicit parcel attributes (location, total_sqft, ...) and/or
    a GeoJSON polygon. When attributes are missing, sane defaults are applied.
    """

    location: str = Field("Whitefield", description="Bengaluru locality name.")
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


class ParcelAnalysisResponse(BaseModel):
    parcel_id: str
    baseline: BaselineValuation
    buffers: list[BufferImpact]
    nearby_projects: list[dict]
    geometry_wkt: Optional[str] = None


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
    mean_demand_utility: float
    mean_developer_profit_margin: float
    land_value_per_sqft: float
    land_value_index: float  # relative to Year 0 = 1.0
    active_infrastructure: int
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
