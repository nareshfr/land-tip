"""POST /parcel/analyze orchestration.

Accepts GeoJSON (or a locality name), runs the Year-0 baseline valuation via the
pre-existing model, then runs spatial buffer analysis (500m / 1km / 2km) against
stored infrastructure projects.
"""

from __future__ import annotations

from shapely.geometry import Point

from app.baseline import baseline_valuation
from app.config import get_settings
from app.db import get_repository
from app.schemas import (
    BaselineValuation,
    BufferImpact,
    ParcelAnalysisResponse,
    ParcelRequest,
)
from app.spatial.buffers import buffer_impact, parse_geometry
from app.spatial.localities import locality_centroid


def _parcel_centroid(req: ParcelRequest) -> tuple[Point, str]:
    """Derive a lon/lat centroid from GeoJSON geometry or a locality name."""
    if req.geojson:
        geom = parse_geometry(geojson=req.geojson)
        if geom is not None:
            c = geom.centroid
            return Point(c.x, c.y), f"POINT ({c.x} {c.y})"
    return locality_centroid(req.location), None


def analyze_parcel(req: ParcelRequest) -> ParcelAnalysisResponse:
    """Run baseline valuation + spatial buffer impact for one parcel."""
    baseline: BaselineValuation = baseline_valuation(
        location=req.location,
        total_sqft=req.total_sqft,
        bhk=req.bhk,
        bath=req.bath,
        balcony=req.balcony,
        area_type=req.area_type,
        availability=req.availability,
        society=req.society,
    )

    centroid, geom_wkt = _parcel_centroid(req)
    if geom_wkt is None:
        geom_wkt = f"POINT ({centroid.x} {centroid.y})"

    repo = get_repository()
    settings = get_settings()
    infra = repo.list_infrastructure()
    impacts = buffer_impact(infra, centroid, settings.buffer_radii_m)
    buffers = [
        BufferImpact(
            radius_m=r,
            project_count=impacts[r]["project_count"],
            projects=impacts[r]["projects"],
        )
        for r in settings.buffer_radii_m
    ]
    nearby = impacts[max(settings.buffer_radii_m)]["projects"]

    parcel_id = repo.save_parcel({
        "location": req.location,
        "total_sqft": req.total_sqft,
        "bhk": req.bhk,
        "bath": req.bath,
        "balcony": req.balcony,
        "area_type": req.area_type,
        "availability": req.availability,
        "society": req.society,
        "geometry_wkt": geom_wkt,
        "baseline": baseline.model_dump(),
    })

    return ParcelAnalysisResponse(
        parcel_id=parcel_id,
        baseline=baseline,
        buffers=buffers,
        nearby_projects=nearby,
        geometry_wkt=geom_wkt,
    )
