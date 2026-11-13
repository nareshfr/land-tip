"""FastAPI routers."""

from app.api import infrastructure, parcels, simulation

ROUTERS = [parcels.router, infrastructure.router, simulation.router]

__all__ = ["ROUTERS"]
