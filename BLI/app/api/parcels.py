"""POST /parcel/analyze - GeoJSON + parcel attributes -> baseline + buffer impact."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import ParcelAnalysisResponse, ParcelRequest
from app.services import analyze_parcel

router = APIRouter(prefix="/parcel", tags=["parcels"])


@router.post("/analyze", response_model=ParcelAnalysisResponse)
def analyze(req: ParcelRequest) -> ParcelAnalysisResponse:
    """Accept GeoJSON + parcel attributes, run baseline valuation and spatial
    buffer analysis (500m / 1km / 2km) against stored infrastructure projects."""
    return analyze_parcel(req)
