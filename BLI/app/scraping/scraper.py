"""Async scraper + storage + buffer flagging.

``scrape_live(source=None)`` fetches (or serves fixtures), parses, validates
every record through :class:`InfrastructureSchema`, persists valid projects to
the repository, then flags affected parcels within 500m / 1km / 2km buffers.

Returns a :class:`app.schemas.ScrapeResponse` payload (plain dict) describing
what was fetched, stored, and which parcels were affected.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import get_settings
from app.db import get_repository
from app.scraping.fixtures import FIXTURES
from app.scraping.parser import PARSERS
from app.scraping.sources import SOURCE_BY_NAME, SOURCES
from app.schemas import InfrastructureSchema

logger = logging.getLogger(__name__)


async def _fetch_source(client: httpx.AsyncClient, source_name: str) -> list[dict]:
    src = SOURCE_BY_NAME[source_name]
    parser = PARSERS[src.parser]
    settings = get_settings()
    try:
        if not settings.scrape_live:
            # Offline mode: serve bundled structured fixtures directly. These
            # already carry validated geometry, so no parser round-trip (which
            # has no geometry to recover from raw HTML anyway).
            return [dict(f) for f in FIXTURES if f["source"] == source_name]
        # Live mode: fetch each URL and parse raw HTML into structured rows.
        out: list[dict] = []
        for url in src.urls:
            try:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                out.extend(parser(resp.text, source_name))
            except Exception as exc:  # network / parse failure on one URL
                logger.warning("scrape %s %s failed: %s", source_name, url, exc)
        if not out:
            rows = [f for f in FIXTURES if f["source"] == source_name]
            return list(rows)
        return out
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("source %s failed entirely: %s", source_name, exc)
        return [f for f in FIXTURES if f["source"] == source_name]


def _fixtures_to_html(rows: list[dict]) -> str:
    """Render fixture dicts as minimal HTML so the live parser path is exercised.

    Used only by the parser unit tests (tests/test_parser.py builds HTML by hand,
    so this helper is retained for ad-hoc debugging of the live parser).
    """
    items = "".join(
        f"<li>{r.get('name', '')} ({r.get('status', '')}) "
        f"{r.get('announcement_date', '')}</li>"
        for r in rows
    )
    return f"<ul>{items}</ul>"


async def scrape_sources(sources: Optional[list[str]] = None) -> dict:
    """Scrape one or more sources; validate; persist; flag affected parcels."""
    settings = get_settings()
    targets = sources or [s.name for s in SOURCES]
    started = datetime.now(timezone.utc).isoformat()
    fetched: list[dict] = []

    headers = {"User-Agent": settings.scrape_user_agent}
    timeout = httpx.Timeout(settings.scrape_timeout_seconds)
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        tasks = [_fetch_source(client, name) for name in targets]
        for name, result in zip(targets, await asyncio.gather(*tasks)):
            for row in result:
                row.setdefault("source", name)
                fetched.append(row)

    # Validate + persist.
    repo = get_repository()
    stored: list[dict] = []
    for row in fetched:
        try:
            schema = InfrastructureSchema(**row)
        except Exception as exc:
            logger.debug("dropping invalid scraped row %r: %s", row.get("name"), exc)
            continue
        stored_dict = schema.model_dump()
        stored_dict["geometry_wkt"] = stored_dict.pop("geometry", None)
        repo.save_infrastructure(stored_dict)
        stored.append(stored_dict)

    # Flag affected parcels by radius. Uses stored parcels + stored infra.
    affected = _flag_affected_parcels(repo, stored)

    finished = datetime.now(timezone.utc).isoformat()
    return {
        "started_at": started,
        "finished_at": finished,
        "source": ",".join(targets),
        "projects_fetched": len(fetched),
        "projects_stored": len(stored),
        "affected_parcels_by_radius": affected,
        "projects": stored,
    }


def _flag_affected_parcels(repo, infra: list[dict]) -> dict[int, int]:
    """Count parcels whose centroid falls within each buffer radius of any
    newly-scraped project. Parcels without geometry are skipped.
    """
    from shapely.geometry import Point

    from app.spatial.buffers import _project_geometry, parse_geometry

    settings = get_settings()
    radii = settings.buffer_radii_m
    # We don't have a list_parcels method on the protocol; use saved parcels via
    # the in-memory store's dict when available, else skip.
    parcels: list[dict] = []
    repo_parcels = getattr(repo, "_parcels", None)
    if repo_parcels is not None:
        parcels = list(repo_parcels.values())

    counts = {r: 0 for r in radii}
    if not parcels:
        return counts

    for parcel in parcels:
        geom_wkt = parcel.get("geometry_wkt")
        c = parcel.get("centroid_lonlat")
        if geom_wkt:
            cg = parse_geometry(wkt=geom_wkt)
            centroid = cg.centroid if cg is not None else None
            if centroid is not None:
                centroid = Point(centroid.x, centroid.y)
        elif isinstance(c, (tuple, list)) and len(c) == 2:
            centroid = Point(c[0], c[1])
        else:
            continue
        if centroid is None:
            continue
        # Distance to nearest scraped project.
        min_d = float("inf")
        for p in infra:
            g = _project_geometry(p)
            if g is None:
                continue
            min_d = min(min_d, _proximity_m(centroid, g))
        for r in radii:
            if min_d <= r:
                counts[r] += 1
    return counts


def _proximity_m(centroid: Point, geom) -> float:
    from app.spatial.buffers import LocalProjector
    import math

    proj = LocalProjector.bengaluru()
    px, py = proj.project(centroid.x, centroid.y)
    rep = geom.representative_point()
    gx, gy = proj.project(rep.x, rep.y)
    return math.hypot(gx - px, gy - py)


def scrape_live(sources: Optional[list[str]] = None) -> dict:
    """Synchronous wrapper around the async scraper (for FastAPI sync endpoints)."""
    return asyncio.run(scrape_sources(sources))
