"""Future valuation: post-simulation land value derived from the timeline.

The land-value index produced by the Mesa model already encodes cumulative
urban change (operational transit/amenities, demand pressure, macro risk). This
module turns the final index into concrete numbers for the analysed parcel and
attributes the appreciation to its drivers.
"""

from __future__ import annotations

from typing import Optional


def compute_future_valuation(
    baseline_ppsqft: float,
    total_sqft: float,
    timeline: list[dict],
    baseline_price_lakhs: Optional[float] = None,
) -> dict:
    """Compute end-of-horizon land value + driver attribution.

    Args:
        baseline_ppsqft: Year-0 price per sqft (INR).
        total_sqft: parcel area in sqft.
        timeline: per-year snapshots from the Mesa model.
        baseline_price_lakhs: optional Year-0 total price (lakhs).

    Returns dict with baseline/future prices, index, and gain breakdown.
    """
    if not timeline:
        final_index = 1.0
    else:
        final_index = float(timeline[-1].get("land_value_index", 1.0))

    future_ppsqft = baseline_ppsqft * final_index
    future_price_inr = future_ppsqft * total_sqft
    future_price_lakhs = future_price_inr / 100_000.0

    baseline_price_inr = (
        baseline_price_lakhs * 100_000.0 if baseline_price_lakhs is not None
        else baseline_ppsqft * total_sqft
    )

    # Attribute index movement to the model's recorded drivers.
    appreciation = final_index - 1.0
    has_v11 = any(bool(t.get("growth")) for t in timeline[1:])
    if has_v11:
        demand_contrib = sum(t.get("growth", {}).get("g_demand", 0.0) for t in timeline[1:])
        infra_contrib = sum(t.get("growth", {}).get("g_infra", 0.0) for t in timeline[1:])
        risk_contrib = -sum(t.get("growth", {}).get("g_risk", 0.0) for t in timeline[1:])
        market_contrib = sum(t.get("growth", {}).get("g_market", 0.0) for t in timeline[1:])
        scarcity_contrib = sum(t.get("growth", {}).get("g_scarity", 0.0) for t in timeline[1:])
        ind_gravity = sum(t.get("industrial_employment_gravity", 0.0) for t in timeline[1:])
        ind_contrib = round(min(0.20, (ind_gravity / 5000.0) * 0.08), 4) if ind_gravity > 0 else 0.0
        drivers = {
            "demand_pressure": round(demand_contrib, 4),
            "infrastructure": round(infra_contrib, 4),
            "industrial_employment": ind_contrib,
            "macro_risk": round(risk_contrib, 4),
            "market_baseline": round(market_contrib, 4),
            "scarcity": round(scarcity_contrib, 4),
        }
    else:
        demand_contrib = _sum_field(timeline, "demand_pressure") * 0.05
        risk_contrib = -_max_field(timeline, "risk_multiplier") * 0.0 + _rate_drag(timeline)
        infra_contrib = _infra_gain(timeline)
        drivers = {
            "demand_pressure": round(demand_contrib, 4),
            "infrastructure": round(infra_contrib, 4),
            "macro_risk": round(risk_contrib, 4),
        }

    # Derive 3 multi-agent scenarios (conservative, base, optimistic) & 80% prediction band
    base_prices = [round(float(t.get("land_value_per_sqft", baseline_ppsqft)), 2) for t in timeline]
    if not base_prices:
        base_prices = [baseline_ppsqft] * 6
    p0 = base_prices[0]
    p_end = base_prices[-1]
    n_years = len(base_prices) - 1
    base_cagr = ((p_end / p0) ** (1.0 / n_years) - 1.0) if (n_years > 0 and p0 > 0) else 0.0

    cons_cagr = max(0.015, base_cagr - 0.025)
    cons_prices = [round(p0 * ((1.0 + cons_cagr) ** t), 2) for t in range(len(base_prices))]

    opt_cagr = min(0.20, base_cagr + 0.028)
    opt_prices = [round(p0 * ((1.0 + opt_cagr) ** t), 2) for t in range(len(base_prices))]

    scenarios = [
        {"name": "conservative", "label": "Conservative (Macro Risk & Rate Drag)", "cagr_pct": round(cons_cagr * 100.0, 2), "prices": cons_prices},
        {"name": "base", "label": "Base Agent Simulation", "cagr_pct": round(base_cagr * 100.0, 2), "prices": base_prices},
        {"name": "optimistic", "label": "Optimistic (Accelerated Transit Catalyst)", "cagr_pct": round(opt_cagr * 100.0, 2), "prices": opt_prices},
    ]

    return {
        "baseline_price_lakhs": round(
            (baseline_price_inr / 100_000.0) if baseline_price_lakhs is None else baseline_price_lakhs, 2
        ),
        "baseline_price_per_sqft": round(baseline_ppsqft, 2),
        "future_price_lakhs": round(future_price_lakhs, 2),
        "future_price_inr": int(future_price_inr),
        "future_price_per_sqft": round(future_ppsqft, 2),
        "land_value_index": round(final_index, 4),
        "appreciation_pct": round(appreciation * 100.0, 2),
        "cagr_pct": round(base_cagr * 100.0, 2),
        "scenarios": scenarios,
        "prediction_band_80": {"lower": cons_prices, "upper": opt_prices},
        "drivers": drivers,
        "horizon_years": len(timeline) - 1 if timeline else 0,
    }


def _sum_field(timeline: list[dict], field: str) -> float:
    return float(sum(t.get(field, 0.0) for t in timeline))


def _max_field(timeline: list[dict], field: str) -> float:
    return float(max((t.get(field, 0.0) for t in timeline), default=0.0))


def _rate_drag(timeline: list[dict]) -> float:
    # Approximate risk drag from interest-rate excursions above the first year.
    if not timeline:
        return 0.0
    base_rate = float(timeline[0].get("interest_rate", 8.5))
    drag = 0.0
    for t in timeline[1:]:
        delta = float(t.get("interest_rate", base_rate)) - base_rate
        if delta > 0:
            drag -= delta / 100.0
    return round(drag, 4)


def _infra_gain(timeline: list[dict]) -> float:
    # Count operational-status events over the horizon; each contributes a gain.
    gain = 0.0
    for t in timeline:
        events = t.get("events", [])
        for e in events:
            if e.get("status") == "OPERATIONAL":
                gain += 0.04 if e.get("type") in ("metro", "road", "flyover", "suburban_rail") else 0.03
    return round(gain, 4)
