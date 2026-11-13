"""POST /simulation/run + GET /simulation/{id} orchestration."""

from __future__ import annotations

from shapely.geometry import Point

from app.baseline import baseline_valuation
from app.db import Repository, get_repository
from app.db.repository import SimulationRecord
from app.schemas import (
    ParcelRequest,
    SimulationConfig,
    SimulationFetchResponse,
    SimulationRunRequest,
    SimulationRunResponse,
    TimelineEntry,
)
from app.simulation.engine import run_simulation
from app.spatial.localities import locality_centroid
from app.services.parcel_service import _parcel_centroid
from app.services.scraping_service import trigger_scrape


def run_simulation_request(req: SimulationRunRequest) -> SimulationRunResponse:
    cfg = req.config
    parcel_req: ParcelRequest = req.parcel

    # Optional live scrape before simulating so the timeline reflects fresh data.
    if req.scrape_first:
        trigger_scrape()

    baseline = baseline_valuation(
        location=parcel_req.location,
        total_sqft=parcel_req.total_sqft,
        bhk=parcel_req.bhk,
        bath=parcel_req.bath,
        balcony=parcel_req.balcony,
        area_type=parcel_req.area_type,
        availability=parcel_req.availability,
        society=parcel_req.society,
    )

    centroid, geom_wkt = _parcel_centroid(parcel_req)

    repo: Repository = get_repository()
    infra = repo.list_infrastructure()

    parcel_id = repo.save_parcel({
        "location": parcel_req.location,
        "total_sqft": parcel_req.total_sqft,
        "bhk": parcel_req.bhk,
        "bath": parcel_req.bath,
        "balcony": parcel_req.balcony,
        "area_type": parcel_req.area_type,
        "availability": parcel_req.availability,
        "society": parcel_req.society,
        "geometry_wkt": geom_wkt or f"POINT ({centroid.x} {centroid.y})",
        "baseline": baseline.model_dump(),
    })

    result = run_simulation(
        baseline=baseline,
        infrastructure=infra,
        parcel_centroid=centroid,
        config=cfg,
        total_sqft=parcel_req.total_sqft,
    )

    timeline = [TimelineEntry(**snap) for snap in result["timeline"]]

    # Embed future_valuation into the summary so GET /simulation/{id} can return it
    # without re-running the engine.
    summary = {**result["summary"], "future_valuation": result["future_valuation"]}
    record = SimulationRecord(
        id="",
        parcel_id=parcel_id,
        years=cfg.years,
        config=cfg.model_dump(),
        summary=summary,
        timeline=result["timeline"],
    )
    run_id = repo.save_simulation(record)

    return SimulationRunResponse(
        run_id=run_id,
        parcel_id=parcel_id,
        years=cfg.years,
        config=cfg,
        baseline=baseline,
        timeline=timeline,
        future_valuation=result["future_valuation"],
        summary=result["summary"],
        created_at=record.created_at,
    )


def fetch_simulation(run_id: str) -> SimulationFetchResponse:
    repo = get_repository()
    record = repo.get_simulation(run_id)
    if record is None:
        return SimulationFetchResponse(run_id=run_id, found=False)
    timeline = [TimelineEntry(**snap) for snap in record.timeline]
    cfg = SimulationConfig(**(record.config or {}))
    return SimulationFetchResponse(
        run_id=record.id,
        found=True,
        parcel_id=record.parcel_id,
        years=record.years,
        config=cfg,
        timeline=timeline,
        future_valuation=record.summary.get("future_valuation") if record.summary else None,
        summary=record.summary,
        created_at=record.created_at,
    )
