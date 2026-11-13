"""Infrastructure Impact Engine.

Converts nearby infrastructure development into measurable, distance-dependent
economic and spatial effects on a parcel (accessibility, employment access,
residential amenity, commercial attractiveness, aggregate influence). These
scores feed the household, developer and market-dynamics agents.

    engine.py   - InfrastructureImpactEngine + per-type profiles / decay.
"""

from app.impact.engine import INFRA_PROFILES, InfrastructureImpactEngine, ImpactScores

__all__ = ["InfrastructureImpactEngine", "ImpactScores", "INFRA_PROFILES"]
