"""Source definitions for the scraping cluster.

Each source maps an authority/board to a list of candidate URLs plus a parser
selector. Parsers live in :mod:`app.scraping.parser` and are keyed by source
name. URLs are real public endpoints used only when SCRAPE_LIVE=true; otherwise
bundled offline fixtures (see :mod:`app.scraping.fixtures`) are parsed instead.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceConfig:
    name: str
    description: str
    urls: tuple[str, ...]
    parser: str  # key into app.scraping.parser.PARSERS


SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        name="BMRCL",
        description="Bangalore Metro Rail Corporation - phase updates",
        urls=(
            "https://bmrc.co.in/whats-new/",
            "https://bmrc.co.in/project-updates/",
        ),
        parser="html_generic",
    ),
    SourceConfig(
        name="BDA",
        description="Bangalore Development Authority - layouts & roads",
        urls=(
            "https://www.bdabengaluru.org/notifications.html",
        ),
        parser="html_generic",
    ),
    SourceConfig(
        name="K-RIDE",
        description="K-RIDE Bengaluru Suburban Rail Project",
        urls=(
            "https://k-ride.in/progress-status/",
        ),
        parser="html_generic",
    ),
    SourceConfig(
        name="NHAI",
        description="NHAI - peripheral ring road / highway projects",
        urls=(
            "https://nhai.gov.in/projects.aspx",
        ),
        parser="html_generic",
    ),
    SourceConfig(
        name="news",
        description="Local real-estate & infra news (aggregated feed)",
        urls=(
            "https://www.thehindu.com/news/cities/bangalore/",
        ),
        parser="html_generic",
    ),
    SourceConfig(
        name="real_estate_board",
        description="Karnataka RERA project registrations",
        urls=(
            "https://rera.karnataka.gov.in/project-status",
        ),
        parser="html_generic",
    ),
)


SOURCE_BY_NAME = {s.name: s for s in SOURCES}
