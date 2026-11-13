"""Simulation endpoints: POST /simulation/run, scenarios, backtest, and GET /simulation/{id}."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import (
    BacktestRequest,
    BacktestResult,
    ScenarioRunRequest,
    ScenarioRunResponse,
    SimulationFetchResponse,
    SimulationRunRequest,
    SimulationRunResponse,
)
from app.services.simulation_service import (
    fetch_simulation,
    run_backtest,
    run_scenarios,
    run_simulation_request,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/run", response_model=SimulationRunResponse)
def run_simulation(req: SimulationRunRequest) -> SimulationRunResponse:
    """Execute the Mesa-powered multi-cluster simulation (Years 0..N)."""
    return run_simulation_request(req)


@router.post("/scenarios", response_model=ScenarioRunResponse)
def run_simulation_scenarios(req: ScenarioRunRequest) -> ScenarioRunResponse:
    """Evaluate a parcel under multiple urban development scenarios."""
    return run_scenarios(req)


@router.post("/backtest", response_model=BacktestResult)
def backtest_simulation(req: BacktestRequest) -> BacktestResult:
    """Backtest simulation against historical observed Bengaluru land prices."""
    return run_backtest(req)


@router.get("/{run_id}", response_model=SimulationFetchResponse)
def get_simulation(run_id: str) -> SimulationFetchResponse:
    """Retrieve a simulation run's results, timeline, and future valuation."""
    return fetch_simulation(run_id)
