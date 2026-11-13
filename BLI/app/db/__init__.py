"""Database layer.

SQLAlchemy ORM models for PostGIS persistence, plus an in-memory repository
used by default (and in tests) when DATABASE_URL is not configured. All
read/write paths in the app go through `get_repository()`, so the storage
backend is swappable without touching business logic.
"""

from app.db.repository import (
    InMemoryRepository,
    Repository,
    SimulationRecord,
    get_repository,
)

__all__ = [
    "InMemoryRepository",
    "Repository",
    "SimulationRecord",
    "get_repository",
]
