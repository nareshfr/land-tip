"""POST /simulation/run, scenarios, backtest + GET /simulation/{id} orchestration."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from shapely.geometry import Point

from app.baseline import baseline_valuation
from app.calibration.data import list_localities
from app.calibration.engine import get_calibration_engine
from app.db import Repository, get_repository
from app.db.repository import SimulationRecord
from app.schemas import (
    BacktestPoint,
    BacktestRequest,
    BacktestResult,
    BaselineValuation,
    ParcelRequest,
    ScenarioConfig,
    ScenarioResult,
    ScenarioRunRequest,
    ScenarioRunResponse,
    SimulationConfig,
    SimulationFetchResponse,
    SimulationRunRequest,
    SimulationRunResponse,
    TimelineEntry,
)
from app.simulation.engine import run_simulation
from app.spatial.localities import locality_centroid
from app.services.parcel_service import _parcel_centroid
from app.services.scraping_service import trigger_scrape


def run_simulation_request(req: SimulationRunRequest) -> SimulationRunResponse:
    cfg = req.config
    parcel_req: ParcelRequest = req.parcel

    # Optional live scrape before simulating so the timeline reflects fresh data.
    if req.scrape_first:
        trigger_scrape()

    baseline = baseline_valuation(
        location=parcel_req.location,
        total_sqft=parcel_req.total_sqft,
        bhk=parcel_req.bhk,
        bath=parcel_req.bath,
        balcony=parcel_req.balcony,
        area_type=parcel_req.area_type,
        availability=parcel_req.availability,
        society=parcel_req.society,
    )

    centroid, geom_wkt = _parcel_centroid(parcel_req)

    repo: Repository = get_repository()
    infra = repo.list_infrastructure()

    parcel_id = repo.save_parcel({
        "location": parcel_req.location,
        "total_sqft": parcel_req.total_sqft,
        "bhk": parcel_req.bhk,
        "bath": parcel_req.bath,
        "balcony": parcel_req.balcony,
        "area_type": parcel_req.area_type,
        "availability": parcel_req.availability,
        "society": parcel_req.society,
        "geometry_wkt": geom_wkt or f"POINT ({centroid.x} {centroid.y})",
        "baseline": baseline.model_dump(),
    })

    result = run_simulation(
        baseline=baseline,
        infrastructure=infra,
        parcel_centroid=centroid,
        config=cfg,
        total_sqft=parcel_req.total_sqft,
    )

    timeline = [TimelineEntry(**snap) for snap in result["timeline"]]

    # Embed future_valuation into the summary so GET /simulation/{id} can return it
    # without re-running the engine.
    summary = {**result["summary"], "future_valuation": result["future_valuation"]}
    record = SimulationRecord(
        id="",
        parcel_id=parcel_id,
        years=cfg.years,
        config=cfg.model_dump(),
        summary=summary,
        timeline=result["timeline"],
    )
    run_id = repo.save_simulation(record)

    return SimulationRunResponse(
        run_id=run_id,
        parcel_id=parcel_id,
        years=cfg.years,
        config=cfg,
        baseline=baseline,
        timeline=timeline,
        future_valuation=result["future_valuation"],
        summary=result["summary"],
        created_at=record.created_at,
    )


def fetch_simulation(run_id: str) -> SimulationFetchResponse:
    repo = get_repository()
    record = repo.get_simulation(run_id)
    if record is None:
        return SimulationFetchResponse(run_id=run_id, found=False)
    timeline = [TimelineEntry(**snap) for snap in record.timeline]
    cfg = SimulationConfig(**(record.config or {}))
    return SimulationFetchResponse(
        run_id=record.id,
        found=True,
        parcel_id=record.parcel_id,
        years=record.years,
        config=cfg,
        timeline=timeline,
        future_valuation=record.summary.get("future_valuation") if record.summary else None,
        summary=record.summary,
        created_at=record.created_at,
    )


def run_scenarios(req: ScenarioRunRequest) -> ScenarioRunResponse:
    if req.scrape_first:
        trigger_scrape()

    parcel_req = req.parcel
    baseline = baseline_valuation(
        location=parcel_req.location,
        total_sqft=parcel_req.total_sqft,
        bhk=parcel_req.bhk,
        bath=parcel_req.bath,
        balcony=parcel_req.balcony,
        area_type=parcel_req.area_type,
        availability=parcel_req.availability,
        society=parcel_req.society,
    )
    centroid, geom_wkt = _parcel_centroid(parcel_req)
    repo = get_repository()
    base_infra = repo.list_infrastructure()

    parcel_id = repo.save_parcel({
        "location": parcel_req.location,
        "total_sqft": parcel_req.total_sqft,
        "bhk": parcel_req.bhk,
        "bath": parcel_req.bath,
        "balcony": parcel_req.balcony,
        "area_type": parcel_req.area_type,
        "availability": parcel_req.availability,
        "society": parcel_req.society,
        "geometry_wkt": geom_wkt or f"POINT ({centroid.x} {centroid.y})",
        "baseline": baseline.model_dump(),
    })

    scenarios = req.scenarios
    if not scenarios:
        scenarios = [
            ScenarioConfig(
                name="Scenario A: Baseline / No Major Development",
                description="Status quo market growth without new major infrastructure interventions.",
                infrastructure=[],
            ),
            ScenarioConfig(
                name="Scenario B: Industrial Development",
                description="New industrial park approved and constructed nearby, boosting employment and demand.",
                infrastructure=[{
                    "project_id": "sc_ind_park",
                    "name": f"{parcel_req.location} Industrial Park",
                    "source": "KIADB",
                    "type": "industrial_park",
                    "status": "APPROVED",
                    "announcement_date": "2024-01-01",
                    "geometry": f"POINT ({centroid.x + 0.005} {centroid.y + 0.005})",
                }],
            ),
            ScenarioConfig(
                name="Scenario C: Industrial & Infrastructure Corridor",
                description="Industrial park plus high-capacity transit / highway extension operational.",
                infrastructure=[
                    {
                        "project_id": "sc_ind_park",
                        "name": f"{parcel_req.location} Industrial Park",
                        "source": "KIADB",
                        "type": "industrial_park",
                        "status": "UNDER_CONSTRUCTION",
                        "announcement_date": "2023-01-01",
                        "geometry": f"POINT ({centroid.x + 0.005} {centroid.y + 0.005})",
                    },
                    {
                        "project_id": "sc_transit_exp",
                        "name": f"{parcel_req.location} Metro / Expressway Corridor",
                        "source": "BMRCL/NHAI",
                        "type": "metro",
                        "status": "UNDER_CONSTRUCTION",
                        "announcement_date": "2023-06-01",
                        "geometry": f"POINT ({centroid.x + 0.002} {centroid.y + 0.002})",
                    },
                ],
            ),
        ]

    results: list[ScenarioResult] = []
    for sc in scenarios:
        sc_infra_map = {p.get("project_id", ""): dict(p) for p in base_infra}
        for extra_p in sc.infrastructure:
            pid = extra_p.get("project_id", "") or f"sc_p_{len(sc_infra_map)}"
            sc_infra_map[pid] = {**extra_p, "project_id": pid}
        combined_infra = list(sc_infra_map.values())

        cfg_dict = req.config.model_dump()
        cfg_dict.update(sc.config_overrides)
        sc_cfg = SimulationConfig(**cfg_dict)

        sqft = float(sc.parcel_overrides.get("total_sqft", parcel_req.total_sqft))

        res = run_simulation(
            baseline=baseline,
            infrastructure=combined_infra,
            parcel_centroid=centroid,
            config=sc_cfg,
            total_sqft=sqft,
        )

        sc_timeline = [TimelineEntry(**snap) for snap in res["timeline"]]
        summary = {**res["summary"], "future_valuation": res["future_valuation"]}
        record = SimulationRecord(
            id="",
            parcel_id=parcel_id,
            years=sc_cfg.years,
            config=sc_cfg.model_dump(),
            summary=summary,
            timeline=res["timeline"],
        )
        run_id = repo.save_simulation(record)

        results.append(ScenarioResult(
            name=sc.name,
            description=sc.description,
            run_id=run_id,
            future_valuation=res["future_valuation"],
            summary=res["summary"],
            timeline=sc_timeline,
        ))

    return ScenarioRunResponse(
        parcel_id=parcel_id,
        baseline=baseline,
        scenarios=results,
    )


def run_backtest(req: BacktestRequest) -> BacktestResult:
    cal_engine = get_calibration_engine()
    localities = req.localities or list_localities()
    points: list[BacktestPoint] = []
    start_year = req.start_year
    horizon = req.horizon_years
    end_year = start_year + horizon

    pred_gains: list[float] = []
    obs_gains: list[float] = []
    baseline_errors_lakhs: list[float] = []

    for loc in localities:
        p_start = cal_engine.observed_price(loc, start_year)
        p_end = cal_engine.observed_price(loc, end_year)
        if p_start is None or p_end is None:
            continue

        total_sqft = 2400.0
        start_lakhs = (p_start * total_sqft) / 100_000.0
        obs_lakhs = round((p_end * total_sqft) / 100_000.0, 2)

        base = BaselineValuation(
            predicted_price_lakhs=round(start_lakhs, 2),
            predicted_price_inr=int(p_start * total_sqft),
            price_per_sqft_inr=round(p_start, 2),
            location_used=loc,
            total_sqft=total_sqft,
            bhk=3.0,
            bath=2.0,
            balcony=1.0,
            area_type="Plot  Area",
            confidence=0.85,
            feature_vector={"is_plot": 1},
            asset_type="land",
            baseline_method="historical_seed",
            raw={"historical_start_year": start_year},
        )

        centroid = locality_centroid(loc)
        cfg = SimulationConfig(years=horizon, seed=req.seed)
        sim_res = run_simulation(
            baseline=base,
            infrastructure=[],
            parcel_centroid=centroid,
            config=cfg,
            total_sqft=total_sqft,
        )

        pred_lakhs = sim_res["future_valuation"]["future_price_lakhs"]
        err_lakhs = round(pred_lakhs - obs_lakhs, 2)
        err_pct = round((pred_lakhs - obs_lakhs) / max(0.01, obs_lakhs) * 100.0, 2)

        points.append(BacktestPoint(
            locality=loc,
            start_year=start_year,
            horizon_years=horizon,
            predicted_lakhs=pred_lakhs,
            observed_lakhs=obs_lakhs,
            error_lakhs=err_lakhs,
            error_pct=err_pct,
        ))

        pred_gains.append(pred_lakhs / max(0.01, start_lakhs) - 1.0)
        obs_gains.append(obs_lakhs / max(0.01, start_lakhs) - 1.0)

        cal_params = cal_engine.calibrate(loc)
        base_cagr = cal_params.baseline_annual_growth
        hist_baseline_pred = start_lakhs * ((1.0 + base_cagr) ** horizon)
        baseline_errors_lakhs.append(abs(hist_baseline_pred - obs_lakhs))

    n = len(points)
    if n > 0:
        mae = round(sum(abs(p.error_lakhs) for p in points) / n, 2)
        rmse = round(math.sqrt(sum(p.error_lakhs ** 2 for p in points) / n), 2)
        mape = round(sum(abs(p.error_pct) for p in points) / n, 2)
        baseline_mae = round(sum(baseline_errors_lakhs) / n, 2)
        appreciation_error_pct = round(
            sum(abs(pg - og) for pg, og in zip(pred_gains, obs_gains)) / n * 100.0, 2
        )
        ranking_accuracy = _rank_correlation(pred_gains, obs_gains)
    else:
        mae = rmse = mape = baseline_mae = appreciation_error_pct = ranking_accuracy = 0.0

    metrics = {
        "n_points": n,
        "mae_lakhs": mae,
        "rmse_lakhs": rmse,
        "mape_pct": mape,
        "appreciation_rate_error_pct": appreciation_error_pct,
        "historical_growth_baseline_mae_lakhs": baseline_mae,
        "ranking_accuracy_spearman": ranking_accuracy,
        "model_improvement_vs_simple_baseline_pct": round(
            ((baseline_mae - mae) / max(0.01, baseline_mae)) * 100.0, 2
        ) if baseline_mae > 0 else 0.0,
    }

    return BacktestResult(
        run_id=uuid.uuid4().hex[:12],
        points=points,
        metrics=metrics,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _rank_correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 1.0
    rx = _ranks(xs)
    ry = _ranks(ys)
    n = len(xs)
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1.0 - (6.0 * d2) / (n * (n * n - 1)), 4)


def _ranks(vals: list[float]) -> list[float]:
    indices = list(range(len(vals)))
    indices.sort(key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    for rank, idx in enumerate(indices, start=1):
        ranks[idx] = float(rank)
    return ranks
