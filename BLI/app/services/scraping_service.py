"""POST /infrastructure/scrape-live orchestration."""

from __future__ import annotations

from app.scraping import scrape_live
from app.schemas import ScrapeResponse


def trigger_scrape(sources: list[str] | None = None) -> ScrapeResponse:
    payload = scrape_live(sources)
    return ScrapeResponse(**payload)
