"""UrbanAlpha FastAPI application factory.

Run locally with:

    uvicorn app.main:app --reload

Endpoints
    POST /parcel/analyze            - baseline valuation + spatial buffers
    POST /infrastructure/scrape-live- trigger scraping cluster
    GET  /infrastructure/            - list stored infrastructure projects
    POST /simulation/run            - run the Mesa multi-cluster simulation
    GET  /simulation/{id}            - fetch a simulation run + future valuation
    GET  /health                     - liveness probe
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import ROUTERS
from app.baseline import get_seed
from app.db import get_repository


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Eagerly validate the baseline model is available so failures surface early.
    get_repository()
    _ = get_seed().is_ready()
    yield


app = FastAPI(
    title="UrbanAlpha - GeoAI Urban Simulation & Land Valuation",
    description=(
        "Bengaluru land valuation platform integrating a pre-existing CatBoost "
        "baseline model (Year 0), real-time web-scraping intelligence, and a "
        "Mesa multi-agent simulation (Macro/Policy, Demand, Supply clusters)."
    ),
    version=__version__,
    lifespan=lifespan,
)

# Allow the land-tip frontend (and any dev origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    seed = get_seed()
    return {
        "status": "ok",
        "version": __version__,
        "baseline_model_ready": seed.is_ready(),
        "repository": type(get_repository()).__name__,
    }


@app.get("/")
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and "application/json" not in accept:
        index_path = _DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
    return {
        "service": "UrbanAlpha",
        "version": __version__,
        "endpoints": [
            "POST /parcel/analyze",
            "POST /infrastructure/scrape-live",
            "GET /infrastructure/",
            "POST /simulation/run",
            "GET /simulation/{id}",
            "GET /health",
        ],
    }


@app.get("/app", response_class=FileResponse)
def serve_app():
    index_path = _DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "Frontend build not found. Run 'npm run build' in land-tip."}


_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "land-tip" / "dist"
if _DIST_DIR.exists() and (_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST_DIR / "assets")), name="assets")


for router in ROUTERS:
    app.include_router(router)
