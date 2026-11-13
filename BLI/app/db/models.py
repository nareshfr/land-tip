"""SQLAlchemy ORM models for PostGIS persistence.

These models define the persistence schema used when DATABASE_URL points at a
PostgreSQL/PostGIS instance. They are deliberately importable without a live
database (no engine is created here). GeoAlchemy2 `Geometry` columns require
PostGIS at DDL time only.

Tables:
    parcels               - analyzed land parcels + Year-0 baseline valuation
    infrastructure_projects- scraped / curated infrastructure events
    simulation_runs       - Mesa simulation runs (one per /simulation/run)
    simulation_timeline   - per-year state snapshot for a run
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    # Optional: only present when geoalchemy2 is installed.
    from geoalchemy2 import Geometry
    _HAS_GEO = True
except Exception:  # pragma: no cover - dependency optional
    _HAS_GEO = False


class Base(DeclarativeBase):
    pass


def _geometry(geom_type: str = "POLYGON", srid: int = 4326):
    """Return a Geometry column when geoalchemy2 is available, else a JSON text fallback.

    This lets the schema be created on plain PostgreSQL (or even SQLite for dev)
    without PostGIS installed.
    """
    if _HAS_GEO:
        return Geometry(geometry_type=geom_type, srid=srid)
    # Fallback: store WKT/EWKT as text.
    return Text()


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    location: Mapped[Optional[str]] = mapped_column(String, index=True)
    total_sqft: Mapped[float] = mapped_column(Float, nullable=False)
    bhk: Mapped[float] = mapped_column(Float, default=3.0)
    bath: Mapped[float] = mapped_column(Float, default=2.0)
    balcony: Mapped[float] = mapped_column(Float, default=1.0)
    area_type: Mapped[Optional[str]] = mapped_column(String, default="Plot  Area")
    availability: Mapped[Optional[str]] = mapped_column(String, default="Ready To Move")
    society: Mapped[Optional[str]] = mapped_column(String, default="Unknown")
    # Geometry stored as WKT/EWKT text column; PostGIS Geometry when available.
    geometry_wkt: Mapped[Optional[str]] = mapped_column(Text)

    # Year-0 baseline valuation output (mirror of BaselineValuation).
    baseline: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class InfrastructureProject(Base):
    __tablename__ = "infrastructure_projects"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, index=True)  # BMRCL, BDA, K-RIDE, NHAI, news
    type: Mapped[str] = mapped_column(String, index=True)  # metro, road, flyover, park, ...
    status: Mapped[str] = mapped_column(String, index=True)  # PROPOSED, APPROVED, UNDER_CONSTRUCTION, OPERATIONAL
    announcement_date: Mapped[Optional[str]] = mapped_column(String)
    geometry_wkt: Mapped[Optional[str]] = mapped_column(Text)
    raw: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    parcel_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("parcels.id"))
    years: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSON)
    summary: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    timeline: Mapped[list["SimulationTimeline"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class SimulationTimeline(Base):
    __tablename__ = "simulation_timeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("simulation_runs.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)

    run: Mapped[SimulationRun] = relationship(back_populates="timeline")
