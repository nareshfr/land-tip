# UrbanAlpha

GeoAI-Powered Urban Simulation and Land Valuation platform for **Bengaluru**.

UrbanAlpha integrates a **pre-existing CatBoost land/price model** as the
**Year-0 baseline seed**, runs a **Real-Time Web-Scraping Intelligence Cluster**
that captures live urban updates, and simulates **Years 0–5** with a **Mesa
multi-agent model** (Macroeconomic & Policy, Demand, Supply & Development
clusters) to project **future land valuation**.

## Architecture

```
                     ┌──────────────────────────────┐
   Pre-existing      │  app.baseline  (Year-0 seed) │   CatBoost model +
   CatBoost model ──▶│  price, price/sqft, feature  │   metadata at repo root
                     │  vector, confidence          │
                     └───────────────┬──────────────┘
                                     │ baseline valuation (anchor)
   BMRCL / BDA /    ┌────────────────▼──────────────┐
   K-RIDE / NHAI ──▶ │  app.scraping  (asyncio cluster)│  Pydantic validation →
   news / RERA       │  parse → validate → store      │  PostGIS / in-memory store
                     └────────────────┬──────────────┘
                                      │ infrastructure events + 500m/1km/2km buffers
                                      ▼
   ┌──────────────────────────────────────────────────────────┐
   │  app.agents  (Mesa)                                       │
   │   • MacroeconomicAgent   interest rate, capital, risk     │
   │   • HouseholdAgent       Utility = Access+Employ+Amen-Cost│
   │   • DeveloperAgent       Rev − Land − Constr − Finance    │
   │  app.simulation.engine   Years 0..N → land-value index    │
   │  app.simulation.valuation  future valuation + drivers     │
   └──────────────────────────────────────────────────────────┘
                                      ▼
                      app.api  (FastAPI)  +  app.services
   POST /parcel/analyze   POST /infrastructure/scrape-live
   POST /simulation/run   GET /simulation/{id}
```

## Data flow

1. **Baseline seed** (`app.baseline`) loads the existing
   `catboost_house_price_model.cbm` + `preprocessor_metadata.json` and returns
   price, price/sqft, a confidence heuristic, and the engineered feature vector.
   This is the **Year-0 anchor** every cluster reads.
2. **Scraping cluster** (`app.scraping`) fetches (or serves offline fixtures
   for) BMRCL, BDA, K-RIDE, NHAI, news, RERA; parses raw HTML into structured
   rows; validates each through `InfrastructureSchema` (Pydantic); persists to
   the repository; and flags affected parcels within **500m / 1km / 2km**
   spatial buffers (Shapely, metre-accurate local projection).
3. **Mesa model** (`app.agents.model`) owns shared market state, the
   infrastructure status timeline, and a per-year land-value index. Each step
   (one year): advance infrastructure → Macro cluster → Supply cluster →
   Demand cluster → recompute demand/supply pressure → update the index.
4. **Future valuation** (`app.simulation.valuation`) converts the final
   land-value index into a parcel-level future price and attributes the
   appreciation to demand, infrastructure, and macro-risk drivers.

## Run

```bash
# deps (into the existing .venv)
.venv/bin/pip install -r requirements.txt

# API server
.venv/bin/uvicorn app.main:app --reload

# tests
.venv/bin/pytest
```

The app runs **with zero configuration**: an in-memory store is used by default
and the scraper serves bundled offline fixtures (`SCRAPE_LIVE=false`). To use
PostgreSQL/PostGIS, set `DATABASE_URL`; to hit real portals, set
`SCRAPE_LIVE=true` (see `.env.example`).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/parcel/analyze` | GeoJSON + parcel attrs → baseline valuation + buffer impact |
| POST | `/infrastructure/scrape-live` | Trigger scraping cluster; persist; flag affected parcels |
| GET  | `/infrastructure/` | List stored infrastructure projects |
| POST | `/simulation/run` | Run the Mesa multi-cluster simulation (Years 0..N) |
| GET  | `/simulation/{id}` | Fetch a run's timeline + future valuation |
| GET  | `/health` | Liveness + model readiness |

## Project layout

```
app/
  main.py            FastAPI app + lifespan
  config.py          settings (pydantic-settings)
  schemas.py         Pydantic schemas incl. InfrastructureSchema validation gate
  baseline/          Year-0 seed wrapping predict_price.py
  scraping/          sources, async fetcher, HTML parser, fixtures, store+buffer flag
  spatial/           local projector, buffer impact, locality geocoder
  agents/            Mesa model + macro/demand/supply clusters
  simulation/        engine (Years 0..N) + future valuation
  services/          thin orchestration between API and domain
  api/               FastAPI routers
  db/                ORM models + in-memory / SQLAlchemy repositories
tests/               24 tests across all layers
IMPLEMENTATION_LOG.md  change tracker (see file)
```
