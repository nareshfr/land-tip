"""UrbanAlpha backend package.

GeoAI-Powered Urban Simulation and Land Valuation platform for Bengaluru.

Layers (each importable on its own):
    app.config          - settings (pydantic-settings)
    app.baseline        - Year-0 valuation seed wrapping the pre-existing CatBoost model
    app.scraping        - Real-Time Web-Scraping Intelligence Cluster (asyncio workers)
    app.spatial         - PostGIS/Shapely buffer analysis (500m / 1km / 2km)
    app.agents          - Mesa multi-agent clusters (Macro/Policy, Demand, Supply)
    app.simulation      - Mesa simulation engine + future valuation (Years 0-5)
    app.db              - SQLAlchemy ORM models + in-memory repository fallback
    app.api             - FastAPI routers
"""

__version__ = "0.1.0"
