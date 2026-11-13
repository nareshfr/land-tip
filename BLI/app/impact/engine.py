"""Infrastructure Impact Engine.

Instead of just *counting* nearby projects (the v1 fixed-buffer approach),
this engine computes a **continuous, distance-decayed** influence for every
infrastructure project near the parcel, weighted by its type and status:

    I = S * exp(-d / lambda) * status_factor

where

    S            - infrastructure significance (per type)
    d            - distance from the parcel (metres)
    lambda       - distance-decay scale (per type, metres)
    status_factor- 1.0 OPERATIONAL, 0.25 UNDER_CONSTRUCTION, 0.05 APPROVED,
                   0.0 PROPOSED (anticipation only once approved)

Each type contributes differently to four scores — accessibility, employment,
residential amenity and commercial attractiveness — which are exactly the inputs
the household / developer / market agents need. Scores are capped so a single
project cannot dominate, and the aggregate ``infrastructure_influence`` is the
weighted combination used by the Market Dynamics Engine to attribute the
infrastructure share of demand-driven growth (avoiding double counting).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shapely.geometry import Point

from app.schemas import ProjectStatus
from app.spatial.buffers import _project_geometry, distance_m


# ---------------------------------------------------------------------------
# Per-type profiles: significance, distance-decay scale, and how much each
# project type contributes to each score (0..1 weights; amenity may be
# slightly negative for industrial, which reduces residential attractiveness).
# Values are reasonable starting points to be calibrated against historical
# observations (see app.calibration).
# ---------------------------------------------------------------------------

INFRA_PROFILES: dict[str, dict] = {
    "metro": {"significance": 1.00, "lambda_m": 800.0, "access": 1.0, "employment": 0.6, "amenity": 0.2, "commercial": 0.5},
    "suburban_rail": {"significance": 0.85, "lambda_m": 1200.0, "access": 0.9, "employment": 0.5, "amenity": 0.1, "commercial": 0.4},
    "railway": {"significance": 0.70, "lambda_m": 1500.0, "access": 0.7, "employment": 0.4, "amenity": 0.0, "commercial": 0.3},
    "road": {"significance": 0.60, "lambda_m": 1500.0, "access": 0.7, "employment": 0.2, "amenity": 0.0, "commercial": 0.3},
    "highway": {"significance": 0.70, "lambda_m": 2500.0, "access": 0.8, "employment": 0.2, "amenity": 0.0, "commercial": 0.3},
    "flyover": {"significance": 0.50, "lambda_m": 1000.0, "access": 0.6, "employment": 0.1, "amenity": 0.0, "commercial": 0.2},
    "commercial": {"significance": 0.80, "lambda_m": 1500.0, "access": 0.2, "employment": 0.9, "amenity": 0.1, "commercial": 1.0},
    "it_park": {"significance": 0.90, "lambda_m": 1800.0, "access": 0.3, "employment": 1.0, "amenity": 0.1, "commercial": 0.8},
    "industrial_park": {"significance": 0.70, "lambda_m": 2500.0, "access": 0.2, "employment": 1.0, "amenity": -0.15, "commercial": 0.4},
    "park": {"significance": 0.50, "lambda_m": 600.0, "access": 0.0, "employment": 0.0, "amenity": 1.0, "commercial": 0.1},
    "lake_restoration": {"significance": 0.45, "lambda_m": 700.0, "access": 0.0, "employment": 0.0, "amenity": 0.9, "commercial": 0.1},
    "educational": {"significance": 0.60, "lambda_m": 1500.0, "access": 0.2, "employment": 0.3, "amenity": 0.5, "commercial": 0.2},
    "other": {"significance": 0.30, "lambda_m": 1000.0, "access": 0.2, "employment": 0.1, "amenity": 0.1, "commercial": 0.1},
}

# Status anticipation factor: how much of the full influence a project exerts
# before it is fully operational.
_STATUS_FACTOR = {
    ProjectStatus.OPERATIONAL.value: 1.0,
    ProjectStatus.UNDER_CONSTRUCTION.value: 0.25,
    ProjectStatus.APPROVED.value: 0.05,
    ProjectStatus.PROPOSED.value: 0.0,
    ProjectStatus.DELAYED.value: 0.10,
}

# Hard caps so one project (or a cluster) cannot run scores away to infinity.
_SCORE_CAP = 1.5


@dataclass
class ImpactScores:
    """Parcel-level impact scores produced by the engine."""

    accessibility: float = 0.0
    employment: float = 0.0
    amenity: float = 0.0
    commercial: float = 0.0
    infrastructure_influence: float = 0.0
    # Per-project influence detail (for explainability / debugging).
    contributions: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "accessibility": round(self.accessibility, 4),
            "employment": round(self.employment, 4),
            "amenity": round(self.amenity, 4),
            "commercial": round(self.commercial, 4),
            "infrastructure_influence": round(self.infrastructure_influence, 4),
            "contributions": self.contributions,
        }


class InfrastructureImpactEngine:
    """Compute distance-decayed infrastructure impact for a parcel.

    The engine is stateless: call :meth:`compute` with the current parcel
    centroid and the list of (runtime) projects each simulation year.
    """

    # Aggregate-influence weights across the four component scores.
    W_ACCESS = 0.30
    W_EMPLOY = 0.30
    W_AMENITY = 0.20
    W_COMMERCIAL = 0.20

    def __init__(self, parcel_centroid: Optional[Point] = None) -> None:
        self.parcel_centroid = parcel_centroid

    def set_centroid(self, centroid: Point) -> None:
        self.parcel_centroid = centroid

    def compute(self, projects: list, parcel_centroid: Optional[Point] = None) -> ImpactScores:
        """Compute impact scores for the parcel given the current projects.

        ``projects`` may be dicts (validated InfrastructureSchema rows) or
        RuntimeProject dataclasses (from the Mesa model). Only projects flagged
        ``within_2km`` (or carrying geometry within ~2 * max lambda) contribute;
        the model tags membership upstream.
        """
        centroid = parcel_centroid or self.parcel_centroid
        scores = ImpactScores()
        if centroid is None:
            return scores

        for proj in projects:
            within = _get(proj, "within_2km", False)
            # Projects outside the 2km band do not influence the parcel.
            if not within:
                continue
            itype = _get(proj, "type", "other")
            profile = INFRA_PROFILES.get(itype, INFRA_PROFILES["other"])
            status = _get(proj, "status", ProjectStatus.PROPOSED.value)
            status_factor = _STATUS_FACTOR.get(status, 0.0)
            if status_factor <= 0.0:
                continue

            geom = _project_geometry(proj) if isinstance(proj, dict) else None
            d = distance_m(centroid, geom) if geom is not None else _fallback_distance(proj, centroid)
            lam = max(1.0, profile["lambda_m"])
            influence = profile["significance"] * status_factor * (2.718281828 ** (-d / lam))

            access = influence * profile["access"]
            employ = influence * profile["employment"]
            amenity = influence * profile["amenity"]
            commer = influence * profile["commercial"]

            scores.accessibility += access
            scores.employment += employ
            scores.amenity += amenity
            scores.commercial += commer
            scores.contributions.append({
                "project_id": _get(proj, "project_id", ""),
                "type": itype,
                "status": status,
                "distance_m": round(d, 1),
                "influence": round(influence, 4),
            })

        scores.accessibility = _cap(scores.accessibility)
        scores.employment = _cap(scores.employment)
        scores.amenity = _cap_signed(scores.amenity)
        scores.commercial = _cap(scores.commercial)
        scores.infrastructure_influence = _cap(
            self.W_ACCESS * scores.accessibility
            + self.W_EMPLOY * scores.employment
            + self.W_AMENITY * max(0.0, scores.amenity)
            + self.W_COMMERCIAL * scores.commercial
        )
        return scores


def _cap(x: float) -> float:
    return max(0.0, min(_SCORE_CAP, x))


def _cap_signed(x: float) -> float:
    # Amenity can be slightly negative (industrial disamenity).
    return max(-0.3, min(_SCORE_CAP, x))


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _fallback_distance(proj, centroid: Point) -> float:
    """If a project has no parseable geometry, treat it as ~2km away (mild)."""
    return 2000.0
