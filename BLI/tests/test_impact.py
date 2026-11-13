"""Infrastructure Impact Engine tests."""

from __future__ import annotations

import pytest
from shapely.geometry import Point

from app.impact.engine import (
    INFRA_PROFILES,
    InfrastructureImpactEngine,
)
from app.schemas import ProjectStatus


def test_distance_decay_metro_near_vs_far():
    """Verify metro at 400m has higher influence than metro at 1800m."""
    engine = InfrastructureImpactEngine()
    parcel = Point(77.6000, 12.9700)

    # Metro at ~400m (approx 0.0036 deg lat)
    near_metro = {
        "project_id": "metro_near",
        "type": "metro",
        "status": ProjectStatus.OPERATIONAL.value,
        "within_2km": True,
        "geometry": f"POINT (77.6000 {12.9700 + 0.0036})",
    }
    # Metro at ~1800m (approx 0.0162 deg lat)
    far_metro = {
        "project_id": "metro_far",
        "type": "metro",
        "status": ProjectStatus.OPERATIONAL.value,
        "within_2km": True,
        "geometry": f"POINT (77.6000 {12.9700 + 0.0162})",
    }

    scores_near = engine.compute([near_metro], parcel_centroid=parcel)
    scores_far = engine.compute([far_metro], parcel_centroid=parcel)

    assert scores_near.accessibility > scores_far.accessibility
    assert scores_near.infrastructure_influence > scores_far.infrastructure_influence
    assert scores_near.contributions[0]["influence"] > scores_far.contributions[0]["influence"]


def test_status_factor_progression():
    """Operational project exerts much more influence than under-construction or proposed."""
    engine = InfrastructureImpactEngine()
    parcel = Point(77.6000, 12.9700)
    geom = f"POINT (77.6000 {12.9700 + 0.005})"

    op_proj = {"project_id": "p1", "type": "metro", "status": ProjectStatus.OPERATIONAL.value, "within_2km": True, "geometry": geom}
    uc_proj = {"project_id": "p1", "type": "metro", "status": ProjectStatus.UNDER_CONSTRUCTION.value, "within_2km": True, "geometry": geom}
    prop_proj = {"project_id": "p1", "type": "metro", "status": ProjectStatus.PROPOSED.value, "within_2km": True, "geometry": geom}

    op_score = engine.compute([op_proj], parcel).infrastructure_influence
    uc_score = engine.compute([uc_proj], parcel).infrastructure_influence
    prop_score = engine.compute([prop_proj], parcel).infrastructure_influence

    assert op_score > uc_score > prop_score
    assert prop_score == 0.0  # Proposed exerts no anticipatory price pressure


def test_category_profiles_distinguish_amenity_vs_employment():
    """Park increases amenity; IT park increases employment and commercial."""
    engine = InfrastructureImpactEngine()
    parcel = Point(77.6000, 12.9700)
    geom = f"POINT (77.6000 {12.9700 + 0.004})"

    park = {"project_id": "pk", "type": "park", "status": ProjectStatus.OPERATIONAL.value, "within_2km": True, "geometry": geom}
    it_park = {"project_id": "it", "type": "it_park", "status": ProjectStatus.OPERATIONAL.value, "within_2km": True, "geometry": geom}

    park_scores = engine.compute([park], parcel)
    it_scores = engine.compute([it_park], parcel)

    assert park_scores.amenity > 0.0
    assert park_scores.employment == 0.0
    assert it_scores.employment > 0.0
    assert it_scores.commercial > 0.0
