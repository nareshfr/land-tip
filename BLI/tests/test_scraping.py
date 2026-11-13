"""Scraping cluster tests (offline fixtures -> validate -> store -> flag parcels)."""

from __future__ import annotations

from app.schemas import InfrastructureSchema
from app.scraping import scrape_live
from app.db import get_repository
from app.services import analyze_parcel
from app.schemas import ParcelRequest


def test_scrape_live_offline_stores_all_fixtures():
    resp = scrape_live()
    # 7 fixtures across the 6 sources.
    assert resp["projects_stored"] == 7
    assert resp["projects_fetched"] >= resp["projects_stored"]
    # Every stored row validates against the structured schema.
    for p in resp["projects"]:
        InfrastructureSchema(**p)
    # Repository now holds them.
    assert len(get_repository().list_infrastructure()) == 7


def test_scrape_live_carries_geometry():
    resp = scrape_live()
    metro = next(p for p in resp["projects"] if p["type"] == "metro")
    # Geometry preserved as WKT for the Whitefield metro fixture.
    assert metro["geometry_wkt"].startswith("POINT")


def test_scrape_flags_affected_parcels_after_analysis():
    # First scrape to populate infrastructure, then analyze a Whitefield parcel
    # so the repository has a parcel with geometry near the metro fixture.
    scrape_live()
    analyze_parcel(ParcelRequest(location="Whitefield", total_sqft=2400))
    # Re-scrape: affected parcel counts should now be non-zero within 2000m.
    resp = scrape_live()
    assert resp["affected_parcels_by_radius"][2000] >= 1
