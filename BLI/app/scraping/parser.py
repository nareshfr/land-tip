"""Parsers that turn raw HTML/text into structured project dicts.

The live parsers are intentionally defensive: government portal markup varies, so
they extract plausible project-like records (text mentioning metro/road/park,
dates, and a status keyword) and map them onto ``InfrastructureSchema`` fields.
They never raise on a missing field - invalid records are simply dropped at the
Pydantic validation gate.
"""

from __future__ import annotations

import re
from typing import Iterable

from bs4 import BeautifulSoup

from app.schemas import InfrastructureType, ProjectStatus

# Keyword -> infrastructure type.
_TYPE_KEYWORDS = (
    (r"metro", InfrastructureType.METRO),
    (r"suburban\s*rail|k-ride|commuter\s*rail", InfrastructureType.SUBURBAN_RAIL),
    (r"flyover|grade\s*separator", InfrastructureType.FLYOVER),
    (r"ring\s*road|highway|road\s*widen|expressway", InfrastructureType.ROAD),
    (r"lake", InfrastructureType.LAKE_RESTORATION),
    (r"park|garden|playground", InfrastructureType.PARK),
    (r"tech\s*park|commercial\s*complex|office|mall|hub", InfrastructureType.COMMERCIAL),
)

_STATUS_KEYWORDS = (
    (r"operational|commissioned|inaugurated|opened", ProjectStatus.OPERATIONAL),
    (r"under\s*construction|work\s*in\s*progress|ongoing", ProjectStatus.UNDER_CONSTRUCTION),
    (r"approved|sanctioned|cleared|awarded", ProjectStatus.APPROVED),
    (r"proposed|planned|announced|envisaged|tender", ProjectStatus.PROPOSED),
    (r"delayed|stalled|deferred", ProjectStatus.DELAYED),
)

_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},\s*\d{4})\b"
)
# Bare YYYY-MM-DD prefix used by fixtures.
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def html_generic(html: str, source: str) -> list[dict]:
    """Parse a generic HTML page into candidate project dicts."""
    soup = BeautifulSoup(html, "lxml")
    records: list[dict] = []

    # Strategy: scan list items, headings, table cells, and paragraphs for
    # project-like text. Each matched block becomes one candidate.
    blocks = soup.select("li, h2, h3, h4, td, p, div.card-title, div.title")
    seen_text: set[str] = set()
    for el in blocks:
        text = " ".join(el.get_text(" ", strip=True).split())
        if not text or len(text) < 12 or text in seen_text:
            continue
        seen_text.add(text)
        rec = _classify_text(text, source)
        if rec is not None:
            records.append(rec)
    return records


def _classify_text(text: str, source: str) -> dict | None:
    itype = _match_keyword(text, _TYPE_KEYWORDS, InfrastructureType.OTHER)
    if itype is InfrastructureType.OTHER and source not in {"news", "real_estate_board"}:
        return None
    status = _match_keyword(text, _STATUS_KEYWORDS, ProjectStatus.PROPOSED)
    date = _DATE_RE.search(text)
    return {
        "project_id": _slugify(f"{source}-{text[:60]}"),
        "name": text[:160],
        "source": source,
        "type": itype.value,
        "status": status.value,
        "announcement_date": date.group(0) if date else None,
        # No geometry from raw HTML; the store step will leave geometry null and
        # rely on curated fixtures for spatial matching when live.
        "geometry": None,
        "raw": {"text": text},
    }


def _match_keyword(text: str, patterns: Iterable[tuple[str, object]], default):
    for pat, val in patterns:
        if re.search(pat, text, flags=re.IGNORECASE):
            return val
    return default


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:64]


# Registry consumed by the scraper.
PARSERS = {
    "html_generic": html_generic,
}
