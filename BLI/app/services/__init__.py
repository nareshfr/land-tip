"""Service layer - thin orchestration between API routers and domain modules.

Routers stay free of business logic; services compose the baseline seed,
spatial analysis, scraping cluster, and simulation engine.
"""

from app.services.parcel_service import analyze_parcel
from app.services.scraping_service import trigger_scrape
from app.services.simulation_service import (
    fetch_simulation,
    run_backtest,
    run_scenarios,
    run_simulation_request,
)

__all__ = [
    "analyze_parcel",
    "trigger_scrape",
    "run_simulation_request",
    "fetch_simulation",
    "run_scenarios",
    "run_backtest",
]
