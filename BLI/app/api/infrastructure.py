"""Infrastructure endpoints: scrape-live trigger + listing."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.db import get_repository
from app.schemas import ScrapeResponse
from app.services import trigger_scrape

router = APIRouter(prefix="/infrastructure", tags=["infrastructure"])


@router.post("/scrape-live", response_model=ScrapeResponse)
def scrape_live(sources: list[str] | None = Query(default=None)) -> ScrapeResponse:
    """Trigger the Real-Time Web-Scraping Intelligence Cluster.

    Validates fetched rows with Pydantic, persists valid projects, and flags
    affected parcels within 500m / 1km / 2km spatial buffers."""
    return trigger_scrape(sources)


@router.get("/")
def list_infrastructure() -> dict:
    """List all stored infrastructure projects (curated or scraped)."""
    projects = get_repository().list_infrastructure()
    return {"count": len(projects), "projects": projects}
