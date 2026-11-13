"""Real-Time Web-Scraping Intelligence Cluster.

Background-capable asyncio workers that scan government portals (BMRCL, BDA,
K-RIDE, NHAI), local news and real-estate boards; parse raw updates into the
structured ``InfrastructureSchema``; validate with Pydantic; persist to the
repository; and flag affected parcels within 500m / 1km / 2km buffers.

By default (SCRAPE_LIVE=false) the cluster serves bundled offline fixtures, so
the system is fully functional without network access. Flip SCRAPE_LIVE=true to
hit the real source URLs.
"""

from app.scraping.scraper import scrape_live, scrape_sources

__all__ = ["scrape_live", "scrape_sources"]
