"""Storage repository abstraction.

Default implementation is in-memory and thread-safe via a lock. When
`settings.database_url` is set, `get_repository()` returns a SQLAlchemy-backed
repository that persists to PostgreSQL/PostGIS. Business logic never imports
the storage backend directly; it always goes through `Repository`.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from app.config import get_settings


# ---------------------------------------------------------------------------
# Dataclass records (storage-agnostic). Maps 1:1 to ORM rows.
# ---------------------------------------------------------------------------

@dataclass
class SimulationRecord:
    id: str
    parcel_id: Optional[str]
    years: int
    config: dict
    summary: dict
    timeline: list[dict] = field(default_factory=list)
    created_at: Optional[str] = None


class Repository(Protocol):
    """Minimal repository protocol used across the app."""

    def save_parcel(self, parcel: dict) -> str: ...
    def get_parcel(self, parcel_id: str) -> Optional[dict]: ...
    def save_infrastructure(self, project: dict) -> str: ...
    def list_infrastructure(self) -> list[dict]: ...
    def save_simulation(self, record: SimulationRecord) -> str: ...
    def get_simulation(self, run_id: str) -> Optional[SimulationRecord]: ...
    def list_simulations(self) -> list[SimulationRecord]: ...
    def reset(self) -> None: ...


# ---------------------------------------------------------------------------
# In-memory implementation (default; no external dependencies).
# ---------------------------------------------------------------------------

class InMemoryRepository:
    """Thread-safe in-memory store. Used by default and in tests."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._parcels: dict[str, dict] = {}
        self._infra: dict[str, dict] = {}
        self._sims: dict[str, SimulationRecord] = {}
        self._seed_fixtures()

    def _seed_fixtures(self) -> None:
        try:
            from app.scraping.fixtures import FIXTURES
            for f in FIXTURES:
                self._infra[f["project_id"]] = dict(f)
        except Exception:
            pass

    # --- parcels ---
    def save_parcel(self, parcel: dict) -> str:
        pid = parcel.get("id") or f"parcel-{uuid.uuid4().hex[:12]}"
        parcel = {**parcel, "id": pid}
        with self._lock:
            self._parcels[pid] = parcel
        return pid

    def get_parcel(self, parcel_id: str) -> Optional[dict]:
        with self._lock:
            return self._parcels.get(parcel_id)

    # --- infrastructure ---
    def save_infrastructure(self, project: dict) -> str:
        pid = project.get("project_id") or f"infra-{uuid.uuid4().hex[:12]}"
        project = {**project, "project_id": pid}
        with self._lock:
            self._infra[pid] = project
        return pid

    def list_infrastructure(self) -> list[dict]:
        with self._lock:
            return list(self._infra.values())

    # --- simulations ---
    def save_simulation(self, record: SimulationRecord) -> str:
        if not record.id:
            record.id = f"sim-{uuid.uuid4().hex[:12]}"
        if record.created_at is None:
            record.created_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._sims[record.id] = record
        return record.id

    def get_simulation(self, run_id: str) -> Optional[SimulationRecord]:
        with self._lock:
            return self._sims.get(run_id)

    def list_simulations(self) -> list[SimulationRecord]:
        with self._lock:
            return list(self._sims.values())

    def reset(self) -> None:
        with self._lock:
            self._parcels.clear()
            self._infra.clear()
            self._sims.clear()
            self._seed_fixtures()


# ---------------------------------------------------------------------------
# Factory.
# ---------------------------------------------------------------------------

_repo: Optional[Repository] = None
_repo_lock = threading.Lock()


def get_repository() -> Repository:
    """Return a process-wide repository. In-memory by default; SQL when configured."""
    global _repo
    if _repo is not None:
        return _repo
    with _repo_lock:
        if _repo is None:
            settings = get_settings()
            if settings.use_database:
                # Lazy import to avoid requiring SQLAlchemy when unused.
                from app.db.sql_repo import SqlRepository
                _repo = SqlRepository(settings.database_url)
            else:
                _repo = InMemoryRepository()
    return _repo


def set_repository(repo: Repository) -> None:
    """Override the repository (used by tests to inject a fresh in-memory store)."""
    global _repo
    with _repo_lock:
        _repo = repo
