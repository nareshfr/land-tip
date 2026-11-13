# Implementation Log — UrbanAlpha backend

Tracks every change made while building the UrbanAlpha GeoAI Urban Simulation &
Land Valuation backend. Append new entries at the bottom; never rewrite history.

Format per entry:

```
### YYYY-MM-DD — <short title>
- What changed (files, components)
- Why
- Verification (commands / results)
```

---

### 2025-11-13 — Baseline + Stack audit

- Read the pre-existing model: `predict_price.py` (`PricePredictorPipeline`,
  CatBoost), `catboost_house_price_model.cbm`, `preprocessor_metadata.json`,
  `bengaluru_house_prices.csv`, `requirements.txt`.
- Decided to wrap `PricePredictorPipeline` unchanged as the **Year-0 baseline
  seed** (no edits to `predict_price.py`).
- Inspected `.venv`: CatBoost, pandas, numpy, scikit-learn present; needed
  FastAPI, Mesa, Shapely, SQLAlchemy, httpx, bs4, Pydantic.

### 2025-11-13 — Dependency install

- Installed into `.venv`: mesa 3.5.2, fastapi 0.162.5, uvicorn, pydantic
  2.14.3, pydantic-settings, shapely 2.2.0, sqlalchemy 2.1.8, httpx 0.28.1,
  beautifulsoup4 + lxml, geoalchemy2, pytest, pytest-asyncio.
- Verified Mesa 3.5 API: `Model(rng=...)`, `agents` / `agents_by_type`,
  `AgentSet.do("step")`, `run_for`, auto-incrementing `steps`, `model.random`
  is stdlib `random.Random` (so use `gauss`, not numpy `normal`).

### 2025-11-13 — Foundation: config, db, schemas, baseline

- `app/config.py`: `Settings` (pydantic-settings); in-memory by default,
  PostGIS when `DATABASE_URL` set; `buffer_radii_m=(500,1000,2000)`.
- `app/db/`: ORM models (`parcels`, `infrastructure_projects`, `simulation_runs`,
  `simulation_timeline`) with optional `geoalchemy2` Geometry columns;
  `Repository` protocol + `InMemoryRepository` (default) + `SqlRepository`
  (PostGIS) + `get_repository()` factory.
- `app/schemas.py`: `InfrastructureSchema` (Pydantic validation gate for scraped
  rows), `BaselineValuation`, request/response models for all endpoints.
- `app/baseline/seed.py`: `BaselineSeed` lazily loads the CatBoost model,
  re-derives the engineered feature vector, computes a confidence heuristic
  (location known to training set → higher), returns `BaselineValuation`.

### 2025-11-13 — Spatial layer

- `app/spatial/buffers.py`: `LocalProjector` (equirectangular, metre-accurate for
  few-km distances), `distance_m`, `buffer_impact` (per-radius project counts +
  lists), GeoJSON/WKT parsing.
- `app/spatial/localities.py`: small built-in geocoder for common Bengaluru
  localities; assigns a parcel centroid when no GeoJSON is supplied.

### 2025-11-13 — Real-Time Web-Scraping Intelligence Cluster

- `app/scraping/sources.py`: source configs (BMRCL, BDA, K-RIDE, NHAI, news,
  real_estate_board) with real public URLs + parser selector.
- `app/scraping/parser.py`: `html_generic` parser — scans blocks for
  type/status keywords + dates, emits structured candidate rows.
- `app/scraping/fixtures.py`: 7 realistic Bengaluru infrastructure fixtures
  (metro, suburban rail, flyover, ring road, lake, park, tech park) with WKT
  geometry — used when `SCRAPE_LIVE=false` (default).
- `app/scraping/scraper.py`: async `scrape_sources` (httpx), validates every row
  via `InfrastructureSchema`, persists to repo, flags affected parcels by
  buffer radius; `scrape_live` sync wrapper for FastAPI.

### 2025-11-13 — Mesa multi-agent clusters

- `app/agents/macro.py`: `MacroeconomicAgent` — mean-reverting interest-rate
  random walk, capital availability, risk multiplier, zoning factor; reacts to
  policy events.
- `app/agents/demand.py`: `HouseholdAgent` —
  `Utility = Accessibility + Employment + Amenity − Housing Cost` (operational
  transit/commercial/parks near the parcel, cost vs baseline).
- `app/agents/supply.py`: `DeveloperAgent` —
  `Expected Revenue − Land Cost − Construction Cost − Financing Cost`, develops
  above a margin threshold, capital scaled by macro availability.
- `app/agents/model.py`: `UrbanAlphaModel` owns shared market state, the
  infrastructure status timeline (auto-promotes PROPOSED→APPROVED→UNDER_
  CONSTRUCTION→OPERATIONAL), Year-0 baseline utility, the per-year land-value
  index, and the snapshot timeline.

### 2025-11-13 — Simulation engine + future valuation

- `app/simulation/engine.py`: `run_simulation` builds the model, tags projects
  within 2km of the parcel, steps Years 1..N, returns timeline + valuation.
- `app/simulation/valuation.py`: `compute_future_valuation` converts the final
  land-value index into parcel price/sqft/lakhs and attributes appreciation to
  demand, infrastructure, and macro-risk drivers.

### 2025-11-13 — Service layer + FastAPI

- `app/services/`: thin orchestration (`analyze_parcel`, `trigger_scrape`,
  `run_simulation_request`, `fetch_simulation`) between routers and domain.
- `app/api/`: routers for `/parcel/analyze`, `/infrastructure/scrape-live`,
  `/infrastructure/`, `/simulation/run`, `/simulation/{id}`.
- `app/main.py`: FastAPI app with `lifespan`, `/health`, `/` route listings.

### 2025-11-13 — Test suite

- `conftest.py`: fresh in-memory repo per test; forces `SCRAPE_LIVE=false`.
- `tests/`: 24 tests — baseline valuation, spatial buffers, HTML parser,
  scraping store/flagging, Mesa determinism & timeline, simulation future
  valuation, all five API endpoints via `TestClient`.
- Result: **24 passed**.

### 2025-11-13 — Bug fixes during integration

- Mesa 3.5 `model.random` is stdlib `random.Random`: replaced `rng.normal(...)`
  with `rng.gauss(...)` in macro/demand agents.
- Offline scrape was round-tripping fixtures through the parser, dropping
  geometry → now serves fixtures directly (parser covered by its own test).
- Future valuation persisted inside the run summary so `GET /simulation/{id}`
  can return it without re-running the engine.
- Deprecation cleanups: FastAPI `on_event` → `lifespan`;
  `datetime.utcnow()` → `datetime.now(timezone.utc)` in repo/models/sql_repo.

### 2025-11-13 — Project metadata

- Updated `requirements.txt` (added FastAPI/Mesa/Shapely/SQLAlchemy/httpx/bs4/
  pytest/optional geoalchemy2+psycopg2).
- Added `.env.example`, `pyproject.toml` (setuptools + pytest config),
  `README.md`, and this `IMPLEMENTATION_LOG.md`.

---

<!-- Append future changes below this line, newest at the bottom. -->
