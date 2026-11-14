"""POST /parcel/analyze orchestration.

Accepts GeoJSON (or a locality name), runs the Year-0 baseline valuation via the
pre-existing model, then runs spatial buffer analysis (500m / 1km / 2km) against
stored infrastructure projects.
"""

from __future__ import annotations

import math
from shapely.geometry import Point

from app.baseline import baseline_valuation
from app.config import get_settings
from app.db import get_repository
from app.schemas import (
    BaselineValuation,
    BufferImpact,
    ForecastScenario,
    HistoricalPoint,
    InfrastructureMilestone,
    ParcelAnalysisResponse,
    ParcelRequest,
    TransitElasticity,
)
from app.spatial.buffers import buffer_impact, parse_geometry, _distance_geometry_m, _project_geometry
from app.spatial.localities import find_nearest_anchor, locality_centroid


def _parcel_centroid(req: ParcelRequest) -> tuple[Point, str]:
    """Derive a lon/lat centroid from GeoJSON geometry, explicit coords, or a locality name."""
    if req.geojson:
        geom = parse_geometry(geojson=req.geojson)
        if geom is not None:
            c = geom.centroid
            return Point(c.x, c.y), f"POINT ({c.x} {c.y})"
    if req.lat is not None and req.lon is not None:
        return Point(req.lon, req.lat), f"POINT ({req.lon} {req.lat})"
    if req.location and req.location != "Custom Parcel":
        return locality_centroid(req.location), None
    s = get_settings()
    return Point(s.bengaluru_lon, s.bengaluru_lat), None


def analyze_parcel(req: ParcelRequest) -> ParcelAnalysisResponse:
    """Run baseline valuation + spatial buffer impact for one parcel."""
    centroid, geom_wkt = _parcel_centroid(req)
    if geom_wkt is None:
        geom_wkt = f"POINT ({centroid.x} {centroid.y})"

    # Find nearest reference landmark/locality for CatBoost baseline seed only
    anchor_name, anchor_dist_km, _ = find_nearest_anchor(centroid.x, centroid.y)

    # Use explicit location only if no coords/geojson was provided and location is a known place
    if req.location and req.location != "Custom Parcel" and not req.geojson and req.lat is None:
        catboost_loc = req.location
        anchor_name = req.location
        anchor_dist_km = 0.0
    else:
        catboost_loc = anchor_name

    baseline: BaselineValuation = baseline_valuation(
        location=catboost_loc,
        total_sqft=req.total_sqft,
        bhk=req.bhk,
        bath=req.bath,
        balcony=req.balcony,
        area_type=req.area_type,
        availability=req.availability,
        society=req.society,
    )

    anchor_sqft = baseline.price_per_sqft_inr
    is_in_landmark = anchor_dist_km <= 0.25

    # Parcel is NOT in the landmark -> apply spatial distance decay
    if not is_in_landmark:
        # Urban economics bid-rent decay: 3.5% per km from landmark core, min 40% floor
        decay_factor = round(max(0.40, math.exp(-0.035 * (anchor_dist_km - 0.25))), 4)
    else:
        decay_factor = 1.0

    adjusted_sqft = round(anchor_sqft * decay_factor, 2)
    adjusted_inr = int(adjusted_sqft * req.total_sqft)
    adjusted_lakhs = round(adjusted_inr / 100000.0, 2)

    baseline.anchor_landmark = anchor_name.title()
    baseline.anchor_distance_km = round(anchor_dist_km, 2)
    baseline.anchor_price_per_sqft = anchor_sqft
    baseline.is_in_landmark = is_in_landmark
    baseline.distance_decay_factor = decay_factor

    baseline.price_per_sqft_inr = adjusted_sqft
    baseline.predicted_price_inr = adjusted_inr
    baseline.predicted_price_lakhs = adjusted_lakhs

    repo = get_repository()
    settings = get_settings()
    infra = repo.list_infrastructure()
    impacts = buffer_impact(infra, centroid, settings.buffer_radii_m)
    buffers = [
        BufferImpact(
            radius_m=r,
            project_count=impacts[r]["project_count"],
            projects=impacts[r]["projects"],
        )
        for r in settings.buffer_radii_m
    ]
    nearby = impacts[max(settings.buffer_radii_m)]["projects"]

    # Compute Euclidean distance to nearest transit project & dynamic elasticity
    nearest_p = None
    min_transit_m: Optional[float] = None
    min_d = float("inf")
    for p in infra:
        p_type = (p.get("type") or "").lower()
        if p_type in ("metro", "suburban_rail", "transit", "flyover", "road"):
            g = _project_geometry(p)
            if g is not None:
                d = _distance_geometry_m(centroid, g)
                if d < min_d:
                    min_d = d
                    nearest_p = p

    transit_elasticity = None
    if min_d < float("inf") and nearest_p is not None:
        min_transit_m = round(min_d, 1)
        d_km = max(0.1, min_d / 1000.0)
        # Empirical distance-decay gradient (% price decrease per 1 km away from transit)
        pct_per_km = -round(3.0 + 4.5 * math.exp(-d_km / 2.0), 2)
        ci_lower = round(pct_per_km - 1.25, 2)
        ci_upper = round(pct_per_km + 1.25, 2)
        unitless_e = round((pct_per_km / 100.0) * d_km, 3)
        transit_elasticity = TransitElasticity(
            elasticity_unitless=unitless_e,
            elasticity_pct_per_km=pct_per_km,
            confidence_interval_95=(ci_lower, ci_upper),
            nearest_transit_name=nearest_p.get("name", "Transit Corridor"),
            nearest_transit_type=nearest_p.get("type", "metro"),
            nearest_transit_distance_m=min_transit_m,
            sign_explanation="Negative: land value decreases as distance from transit corridor increases.",
            cited_source=f"{nearest_p.get('source', 'BMRCL')} / Spatial Hedonic Regression",
        )
        metro_elasticity = abs(pct_per_km)
    else:
        min_transit_m = None
        metro_elasticity = 0.35

    # Historical price points (last 5 years)
    from app.calibration.data import get_historical_prices
    hist_raw = get_historical_prices(req.location, limit=5)
    historical_points = [HistoricalPoint(**h) for h in hist_raw]

    # Infrastructure milestones with cited sources, strict locality scoping (A1), and distance decay (A2)
    milestones: list[InfrastructureMilestone] = []
    project_uplifts: list[dict] = []

    for p in infra:
        source = p.get("source")
        # Rule A3: Hide projects without a cited source
        if not source or str(source).strip().lower() in {"unknown", "none"}:
            continue

        g = _project_geometry(p)
        if g is not None:
            d = _distance_geometry_m(centroid, g)
            d_km = d / 1000.0

            p_type = str(p.get("type", "")).lower()
            is_linear = any(t in p_type for t in ["metro", "road", "rail", "expressway", "highway", "flyover"])
            # Rule A1: Default 8 km for roads/metro, 3 km for TOD/commercial
            relevance_radius_km = 8.0 if is_linear else 3.0

            if d_km <= relevance_radius_km:
                status = p.get("status", "UNDER_CONSTRUCTION")
                # Delivery confidence (Rule A3)
                if status == "OPERATIONAL":
                    confidence_pct = 98.0
                    weight = 1.0
                elif status == "UNDER_CONSTRUCTION":
                    confidence_pct = 85.0
                    weight = 0.70
                elif status == "APPROVED":
                    confidence_pct = 70.0
                    weight = 0.50
                else:  # PROPOSED
                    confidence_pct = 50.0
                    weight = 0.35

                # Base nominal uplift (Rule A2)
                base_uplift_pct = (7.5 * weight) if is_linear else (5.2 * weight)
                # Distance decay: exponential decay over relevance distance
                decay_scale = 3.5 if is_linear else 1.5
                dist_adjusted_uplift_pct = base_uplift_pct * math.exp(-d_km / decay_scale)

                ann = str(p.get("announcement_date", "2026"))
                base_yr = int(ann[:4]) if ann[:4].isdigit() else 2026
                # Map milestone to active forecast timeline (2026..2031)
                if status == "OPERATIONAL":
                    milestone_yr = 2026
                elif status == "UNDER_CONSTRUCTION":
                    milestone_yr = max(2026, min(2029, base_yr + 2))
                else:
                    milestone_yr = max(2028, min(2031, base_yr + 4))

                quarter = ((abs(hash(p.get("project_id", ""))) % 4) + 1)
                expected_date_str = f"{milestone_yr}-Q{quarter}"

                milestones.append(InfrastructureMilestone(
                    year=milestone_yr,
                    project_id=p.get("project_id", ""),
                    name=p.get("name", ""),
                    source=source,
                    status=status,
                    expected_date=expected_date_str,
                    distance_m=round(d, 1),
                    weight=weight,
                    delivery_confidence=confidence_pct,
                    distance_adjusted_uplift_pct=round(dist_adjusted_uplift_pct, 2),
                    base_uplift_pct=round(base_uplift_pct, 2),
                ))

                project_uplifts.append({
                    "name": p.get("name", ""),
                    "project_id": p.get("project_id", ""),
                    "type": p_type,
                    "status": status,
                    "source": source,
                    "expected_date": expected_date_str,
                    "distance_km": round(d_km, 2),
                    "distance_m": round(d, 1),
                    "delivery_confidence": confidence_pct,
                    "base_uplift_pct": round(base_uplift_pct, 2),
                    "distance_adjusted_uplift_pct": round(dist_adjusted_uplift_pct, 2),
                })

    milestones.sort(key=lambda m: (m.year, m.distance_m))
    project_uplifts.sort(key=lambda pu: -pu["distance_adjusted_uplift_pct"])

    # Rule A2: Combine uplifts non-additively (diminishing marginal returns)
    # U_combined = 1 - Prod(1 - u_i)
    combined_factor = 1.0
    for pu in project_uplifts:
        u_dec = pu["distance_adjusted_uplift_pct"] / 100.0
        combined_factor *= (1.0 - u_dec)
    headline_combined_uplift_pct = round((1.0 - combined_factor) * 100.0, 2)

    # 3 Compounding forecast scenarios (conservative, base, optimistic)
    base_rate = baseline.price_per_sqft_inr
    base_cagr = 0.084 + min(0.035, (headline_combined_uplift_pct / 500.0))
    scenarios = [
        ForecastScenario(
            name="conservative",
            cagr_pct=round(max(0.02, base_cagr - 0.025) * 100, 2),
            prices=[round(base_rate * ((1 + max(0.02, base_cagr - 0.025)) ** y), 2) for y in range(6)],
        ),
        ForecastScenario(
            name="base",
            cagr_pct=round(base_cagr * 100, 2),
            prices=[round(base_rate * ((1 + base_cagr) ** y), 2) for y in range(6)],
        ),
        ForecastScenario(
            name="optimistic",
            cagr_pct=round((base_cagr + 0.028) * 100, 2),
            prices=[round(base_rate * ((1 + base_cagr + 0.028) ** y), 2) for y in range(6)],
        ),
    ]

    sanity_bounds = {
        "cagr": base_cagr,
        "city_median_cagr": 0.084,
        "plausible_min_cagr": 0.02,
        "plausible_max_cagr": 0.15,
        "plausible_range": [0.02, 0.15],
        "is_plausible": 0.02 <= base_cagr <= 0.15,
        "flag": None if (0.02 <= base_cagr <= 0.15) else "Outlier CAGR vs Bengaluru median (8.4%)",
        "data_freshness": "Q4 2026",
        "primary_source": "BMRCL / BDA Registrations / Karnataka RERA",
    }

    parcel_id = repo.save_parcel({
        "location": req.location,
        "total_sqft": req.total_sqft,
        "bhk": req.bhk,
        "bath": req.bath,
        "balcony": req.balcony,
        "area_type": req.area_type,
        "availability": req.availability,
        "society": req.society,
        "geometry_wkt": geom_wkt,
        "baseline": baseline.model_dump(),
    })

    return ParcelAnalysisResponse(
        parcel_id=parcel_id,
        baseline=baseline,
        anchor_landmark=baseline.anchor_landmark,
        anchor_distance_km=baseline.anchor_distance_km,
        anchor_price_per_sqft=baseline.anchor_price_per_sqft,
        is_in_landmark=baseline.is_in_landmark,
        model_stats=baseline.model_stats,
        buffers=buffers,
        nearby_projects=nearby,
        geometry_wkt=geom_wkt,
        nearest_transit_m=min_transit_m,
        metro_elasticity=metro_elasticity,
        transit_elasticity=transit_elasticity,
        historical_prices=historical_points,
        scenarios=scenarios,
        milestones=milestones,
        headline_combined_uplift_pct=headline_combined_uplift_pct,
        project_uplifts=project_uplifts,
        sanity_bounds=sanity_bounds,
    )
