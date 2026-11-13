"""Pytest configuration shared by all tests.

Ensures every test starts with a fresh in-memory repository and that scraping
uses offline fixtures (no network).
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.db.repository import InMemoryRepository, set_repository


@pytest.fixture(autouse=True)
def fresh_repository():
    """Reset to a clean in-memory store before each test."""
    set_repository(InMemoryRepository())
    yield
    set_repository(InMemoryRepository())


def pytest_configure():
    # Force offline scraping regardless of any local .env.
    s = get_settings()
    s.scrape_live = False
