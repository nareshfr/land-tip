"""Offline fixture data for the scraping cluster.

Realistic Bengaluru infrastructure events used when SCRAPE_LIVE=false and as a
fallback when a live fetch fails. Geometry is WKT POINT in EPSG:4326. These
mirror the kind of structured rows the live parsers would emit.
"""

from __future__ import annotations

# Each entry already conforms to InfrastructureSchema's required fields.
FIXTURES: list[dict] = [
    {
        "project_id": "bmrcl-purple-whitefield",
        "name": "Namma Metro Purple Line Extension - Whitefield",
        "source": "BMRCL",
        "type": "metro",
        "status": "UNDER_CONSTRUCTION",
        "announcement_date": "2020-02-15",
        "geometry": "POINT (77.7499 12.9696)",
    },
    {
        "project_id": "kride-cor-1",
        "name": "Bengaluru Suburban Rail - Corridor 1 (Sampige to Whitefield)",
        "source": "K-RIDE",
        "type": "suburban_rail",
        "status": "APPROVED",
        "announcement_date": "2022-06-01",
        "geometry": "POINT (77.7041 12.9616)",
    },
    {
        "project_id": "bda-orr-flyover",
        "name": "BDA Outer Ring Road Flyover - Marathahalli",
        "source": "BDA",
        "type": "flyover",
        "status": "PROPOSED",
        "announcement_date": "2023-09-10",
        "geometry": "POINT (77.6884 12.9556)",
    },
    {
        "project_id": "nhai-prr-phase1",
        "name": "NHAI Peripheral Ring Road Phase 1",
        "source": "NHAI",
        "type": "road",
        "status": "PROPOSED",
        "announcement_date": "2023-04-20",
        "geometry": "POINT (77.50 13.05)",
    },
    {
        "project_id": "bbmp-kaikondrahalli-lake",
        "name": "Kaikondrahalli Lake Restoration",
        "source": "news",
        "type": "lake_restoration",
        "status": "UNDER_CONSTRUCTION",
        "announcement_date": "2022-03-15",
        "geometry": "POINT (77.6620 12.9150)",
    },
    {
        "project_id": "bbmp-aggada-bayalu-park",
        "name": "Agara Lake Park Upgradation",
        "source": "news",
        "type": "park",
        "status": "PROPOSED",
        "announcement_date": "2023-11-05",
        "geometry": "POINT (77.6470 12.9190)",
    },
    {
        "project_id": "rera-techpark-sarjapur",
        "name": "Sarjapur Road IT Tech Park Hub",
        "source": "real_estate_board",
        "type": "commercial",
        "status": "UNDER_CONSTRUCTION",
        "announcement_date": "2022-12-01",
        "geometry": "POINT (77.6877 12.9105)",
    },
]
