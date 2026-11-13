"""Simulation endpoints: POST /simulation/run and GET /simulation/{id}."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import (
    SimulationFetchResponse,
    SimulationRunRequest,
    SimulationRunResponse,
)
from app.services.simulation_service import fetch_simulation, run_simulation_request

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/run", response_model=SimulationRunResponse)
def run_simulation(req: SimulationRunRequest) -> SimulationRunResponse:
    """Execute the Mesa-powered multi-cluster simulation (Years 0..N)."""
    return run_simulation_request(req)


@router.get("/{run_id}", response_model=SimulationFetchResponse)
def get_simulation(run_id: str) -> SimulationFetchResponse:
    """Retrieve a simulation run's results, timeline, and future valuation."""
    return fetch_simulation(run_id)
