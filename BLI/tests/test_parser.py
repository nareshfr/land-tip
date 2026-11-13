"""Scraping parser tests (live HTML -> structured rows)."""

from __future__ import annotations

from app.scraping.parser import html_generic


def test_html_generic_extracts_metro_and_status():
    html = """
    <ul>
      <li>Namma Metro Purple Line Extension inaugurated and operational in Whitefield, 2023-03-25</li>
      <li>BDA Outer Ring Road flyover under construction, work in progress</li>
      <li>K-RIDE suburban rail corridor approved by cabinet on 1 Jan 2022</li>
      <li>Some unrelated text about weather that should not be classified</li>
    </ul>
    """
    rows = html_generic(html, "BMRCL")
    # At least the three infrastructure-like rows survive (weather dropped).
    types = {r["type"] for r in rows}
    assert "metro" in types
    assert "flyover" in types
    assert "suburban_rail" in types
    statuses = {r["status"] for r in rows}
    assert "OPERATIONAL" in statuses
    assert "UNDER_CONSTRUCTION" in statuses
    assert "APPROVED" in statuses
    # Announcement dates parsed where present.
    dated = [r for r in rows if r["announcement_date"]]
    assert any("2023-03-25" == r["announcement_date"] for r in dated)
