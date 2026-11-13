"""SQLAlchemy-backed repository for PostGIS persistence.

Activated only when ``DATABASE_URL`` is configured. Uses an engine-scoped
session. Geometry is stored as WKT text in a normal column (PostGIS works
because we write EWKT), which keeps the schema portable to plain PostgreSQL.

Kept minimal: maps the ORM rows in ``app.db.models`` to the dataclass records
used by business logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base,
    InfrastructureProject,
    Parcel,
    SimulationRun,
    SimulationTimeline,
)
from app.db.repository import SimulationRecord


class SqlRepository:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, future=True)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)
        # Create tables if missing. Safe on a fresh PostGIS-enabled DB.
        Base.metadata.create_all(self.engine)

    # --- parcels ---
    def save_parcel(self, parcel: dict) -> str:
        from app.db.repository import InMemoryRepository  # noqa: only for id helper

        pid = parcel.get("id") or f"parcel-{__import__('uuid').uuid4().hex[:12]}"
        with self.Session() as s:
            row = s.get(Parcel, pid)
            if row is None:
                row = Parcel(id=pid)
                s.add(row)
            for k, v in parcel.items():
                if k == "id":
                    continue
                if k == "geometry" and v is not None:
                    row.geometry_wkt = v if isinstance(v, str) else None
                elif hasattr(row, k):
                    setattr(row, k, v)
            row.baseline = parcel.get("baseline")
            s.commit()
        return pid

    def get_parcel(self, parcel_id: str) -> Optional[dict]:
        with self.Session() as s:
            row = s.get(Parcel, parcel_id)
            if row is None:
                return None
            d = {
                "id": row.id,
                "location": row.location,
                "total_sqft": row.total_sqft,
                "bhk": row.bhk,
                "bath": row.bath,
                "balcony": row.balcony,
                "area_type": row.area_type,
                "availability": row.availability,
                "society": row.society,
                "geometry_wkt": row.geometry_wkt,
                "baseline": row.baseline,
            }
            return d

    # --- infrastructure ---
    def save_infrastructure(self, project: dict) -> str:
        import uuid as _uuid

        pid = project.get("project_id") or f"infra-{_uuid.uuid4().hex[:12]}"
        with self.Session() as s:
            row = s.get(InfrastructureProject, pid)
            if row is None:
                row = InfrastructureProject(project_id=pid)
                s.add(row)
            for k, v in project.items():
                if k == "project_id":
                    continue
                if k == "geometry" and v is not None:
                    row.geometry_wkt = v if isinstance(v, str) else None
                elif hasattr(row, k):
                    setattr(row, k, v)
            row.raw = project.get("raw")
            s.commit()
        return pid

    def list_infrastructure(self) -> list[dict]:
        with self.Session() as s:
            rows = s.execute(select(InfrastructureProject)).scalars().all()
            out = []
            for r in rows:
                out.append({
                    "project_id": r.project_id,
                    "name": r.name,
                    "source": r.source,
                    "type": r.type,
                    "status": r.status,
                    "announcement_date": r.announcement_date,
                    "geometry_wkt": r.geometry_wkt,
                    "raw": r.raw,
                })
            return out

    # --- simulations ---
    def save_simulation(self, record: SimulationRecord) -> str:
        import uuid as _uuid

        if not record.id:
            record.id = f"sim-{_uuid.uuid4().hex[:12]}"
        if record.created_at is None:
            record.created_at = datetime.now(timezone.utc).isoformat()
        with self.Session() as s:
            row = s.get(SimulationRun, record.id)
            if row is None:
                row = SimulationRun(id=record.id)
                s.add(row)
            row.parcel_id = record.parcel_id
            row.years = record.years
            row.config = record.config
            row.summary = record.summary
            # Replace timeline rows.
            for t in list(row.timeline):
                s.delete(t)
            for snap in record.timeline:
                row.timeline.append(
                    SimulationTimeline(year=snap.get("year", 0), state=snap)
                )
            s.commit()
        return record.id

    def get_simulation(self, run_id: str) -> Optional[SimulationRecord]:
        with self.Session() as s:
            row = s.get(SimulationRun, run_id)
            if row is None:
                return None
            return SimulationRecord(
                id=row.id,
                parcel_id=row.parcel_id,
                years=row.years,
                config=row.config or {},
                summary=row.summary or {},
                timeline=[{"year": t.year, **(t.state or {})} for t in row.timeline],
                created_at=row.created_at.isoformat() if row.created_at else None,
            )

    def list_simulations(self) -> list[SimulationRecord]:
        with self.Session() as s:
            rows = s.execute(select(SimulationRun)).scalars().all()
            return [self.get_simulation(r.id) for r in rows]  # type: ignore[list-item]

    def reset(self) -> None:
        # Destructive: drops all app tables. Used only by tests with a throwaway DB.
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
