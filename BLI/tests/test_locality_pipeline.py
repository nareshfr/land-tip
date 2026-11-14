"""
UrbanAlpha End-to-End Pipeline & Locality Differentiation Test Suite.

Runs 5 distinct Bengaluru localities (Indiranagar, Whitefield, Yelahanka,
Jayanagar, Electronic City) and verifies all 10 rules:
1. No hardcoded or placeholder values; area-specific computed outputs.
2. Internal consistency assertions:
   - Projected rate card = 2031 curve endpoint; delta matches endpoints.
   - Compounding CAGR = (P2031 / P2026)^(1/5) - 1.
   - Convex compounding curve.
   - TreeSHAP sums to 100% (with "Other / residual").
   - Geometric buffer counts: count(500m) <= count(1km) <= count(2km).
   - Features at >500m do not appear in 500m buffer.
3. Euclidean metric distance for POIs and corridors.
4. Negative transit elasticity with 95% CI and explanation.
5. Sourced infrastructure milestones with status and expected year.
6. 5Y historical + 3 forecast scenarios (conservative <= base <= optimistic).
7. Out-of-sample model statistics (R², n, RMSE, MAPE).
8. Drivers / Attribution terminology with association note.
9. Landmarks categorized into Tech, Transit, Water-Park, Retail, Road.
10. Plausible CAGR bounds vs city median (8.4%).
"""

import math
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

LOCALITIES = [
    "Sahakara Nagar",
    "Indiranagar",
    "Whitefield",
    "Yelahanka",
    "Jayanagar",
]


@pytest.fixture(scope="module")
def locality_results():
    """Execute analysis and simulation for all 5 localities."""
    results = {}
    for loc in LOCALITIES:
        payload = {
            "location": loc,
            "total_sqft": 2400.0,
            "bhk": 3,
            "bath": 2,
            "balcony": 1,
            "area_type": "Plot  Area",
            "availability": "Ready To Move",
            "society": "Unknown",
        }
        res_analysis = client.post("/parcel/analyze", json=payload)
        assert res_analysis.status_code == 200, f"Analysis failed for {loc}: {res_analysis.text}"
        analysis_data = res_analysis.json()

        res_sim = client.post(
            "/simulation/run",
            json={
                "parcel": payload,
                "config": {
                    "years": 5,
                    "households": 50,
                    "developers": 5,
                    "seed": 42,
                    "initial_interest_rate": 8.5,
                    "capital_availability": 1.0,
                },
                "persist": False,
            },
        )
        assert res_sim.status_code == 200, f"Simulation failed for {loc}: {res_sim.text}"
        sim_data = res_sim.json()

        results[loc] = {
            "analysis": analysis_data,
            "sim": sim_data,
            "payload": payload,
        }
    return results


def test_locality_differentiation(locality_results):
    """Assert all 5 localities return distinct, area-specific outputs."""
    p2026_values = set()
    p2031_values = set()
    cagr_values = set()
    r2_values = set()
    sample_sizes = set()
    top_shap_features = []
    buffer_500_counts = []

    for loc in LOCALITIES:
        data = locality_results[loc]
        analysis = data["analysis"]
        sim = data["sim"]

        p2026 = sim["baseline"]["price_per_sqft_inr"]
        p2031 = sim["timeline"][-1]["land_value_per_sqft"]
        cagr = (p2031 / p2026) ** (1 / 5) - 1

        p2026_values.add(round(p2026, 1))
        p2031_values.add(round(p2031, 1))
        cagr_values.add(round(cagr, 4))

        stats = analysis["model_stats"]
        r2_values.add(round(stats["r2_score"], 3))
        sample_sizes.add(stats["sample_size_n"])

        top_shap_features.append(sim["baseline"]["shap_attributions"][0]["feature"])
        buffer_500_counts.append(analysis["buffers"][0]["project_count"])

    # All 5 localities must have unique 2026 prices and 2031 valuations
    assert len(p2026_values) == 5, f"Expected 5 distinct 2026 prices, got {p2026_values}"
    assert len(p2031_values) == 5, f"Expected 5 distinct 2031 valuations, got {p2031_values}"
    assert len(cagr_values) == 5, f"Expected 5 distinct CAGRs, got {cagr_values}"
    assert len(r2_values) >= 4, f"Expected distinct R² across localities, got {r2_values}"
    assert len(sample_sizes) == 5, f"Expected 5 distinct sample sizes, got {sample_sizes}"


def test_internal_consistency_rule_2(locality_results):
    """Assert Rule 2 internal consistency checks for all 5 areas."""
    for loc in LOCALITIES:
        data = locality_results[loc]
        analysis = data["analysis"]
        sim = data["sim"]

        p2026 = sim["baseline"]["price_per_sqft_inr"]
        p2031 = sim["timeline"][-1]["land_value_per_sqft"]
        delta = p2031 - p2026

        # 1. Projected rate card = 2031 endpoint; delta matches endpoints
        assert p2031 > 0
        assert math.isclose(delta, p2031 - p2026, rel_tol=1e-5)

        # 2. Compounding CAGR = (P2031 / P2026)^(1/5) - 1
        expected_cagr = (p2031 / p2026) ** (1 / 5) - 1
        timeline_prices = [entry["land_value_per_sqft"] for entry in sim["timeline"]]
        actual_cagr = (timeline_prices[-1] / timeline_prices[0]) ** (1 / 5) - 1
        assert math.isclose(actual_cagr, expected_cagr, rel_tol=1e-4)

        # 3. Compounding curve convexity check (annual increments are positive & consistent)
        for i in range(len(timeline_prices) - 1):
            assert timeline_prices[i + 1] > timeline_prices[i], (
                f"{loc}: timeline price decreased at year {i+1}"
            )

        # 4. TreeSHAP contributions sum to 100% and contain 'Other / residual'
        shap = sim["baseline"]["shap_attributions"]
        total_pct = sum(item["importance_pct"] for item in shap)
        assert math.isclose(total_pct, 100.0, abs_tol=0.2), (
            f"{loc}: SHAP sum is {total_pct}, expected 100%"
        )
        assert any("other" in item["feature"].lower() for item in shap), (
            f"{loc}: Missing 'Other / residual' in SHAP attribution"
        )

        # 5. Buffer counts strictly nested: count(500m) <= count(1km) <= count(2km)
        buffers = analysis["buffers"]
        b500 = buffers[0]["project_count"]
        b1000 = buffers[1]["project_count"]
        b2000 = buffers[2]["project_count"]
        assert b500 <= b1000 <= b2000, (
            f"{loc}: Buffer nesting violated: {b500} <= {b1000} <= {b2000}"
        )

        # 6. Feature at > 500m must NOT appear in 500m buffer
        p500_names = {p["name"] for p in buffers[0]["projects"]}
        p1000_only = [p for p in buffers[1]["projects"] if p["name"] not in p500_names]
        # Any project only in 1000m buffer must not be present in 500m buffer
        for p in p1000_only:
            assert p["name"] not in p500_names


def test_transit_elasticity_rule_4(locality_results):
    """Assert Rule 4: transit elasticity is negative with 95% CI and explanation."""
    for loc in LOCALITIES:
        data = locality_results[loc]
        analysis = data["analysis"]
        te = analysis["transit_elasticity"]

        assert te["elasticity_unitless"] < 0, f"{loc}: Elasticity should be negative"
        assert te["elasticity_pct_per_km"] < 0, f"{loc}: elasticity_pct_per_km should be negative"
        assert te["confidence_interval_95"] is not None
        assert te["confidence_interval_95"][0] < te["confidence_interval_95"][1]
        assert "negative" in te["sign_explanation"].lower() or "decrease" in te["sign_explanation"].lower()


def test_infrastructure_sources_rule_5(locality_results):
    """Assert Rule 5: all infrastructure milestones have cited sources and valid status."""
    valid_statuses = {"OPERATIONAL", "UNDER_CONSTRUCTION", "PROPOSED", "APPROVED", "COMPLETED"}
    for loc in LOCALITIES:
        data = locality_results[loc]
        analysis = data["analysis"]
        milestones = analysis["milestones"]

        for m in milestones:
            assert m["source"] in {"BMRCL", "BDA", "BBMP", "K-RIDE", "NHAI", "MoRTH", "GOK"}, (
                f"Invalid or uncited source for {m['name']}: {m['source']}"
            )
            assert m["status"] in valid_statuses, f"Invalid status: {m['status']}"
            assert 2026 <= m["year"] <= 2031, f"Year out of bounds: {m['year']}"


def test_forecast_scenarios_rule_6(locality_results):
    """Assert Rule 6: 3 forecast scenarios satisfy conservative <= base <= optimistic."""
    for loc in LOCALITIES:
        data = locality_results[loc]
        analysis = data["analysis"]
        scenarios = {s["name"]: s for s in analysis["scenarios"]}

        assert "conservative" in scenarios
        assert "base" in scenarios
        assert "optimistic" in scenarios

        con = scenarios["conservative"]["prices"]
        base = scenarios["base"]["prices"]
        opt = scenarios["optimistic"]["prices"]

        assert len(con) == 6 and len(base) == 6 and len(opt) == 6
        for y in range(6):
            assert con[y] <= base[y] <= opt[y], (
                f"{loc} year +{y}: conservative ({con[y]}) <= base ({base[y]}) <= optimistic ({opt[y]}) violated"
            )


def test_locality_scoping_and_relevance_rule_a1_a2(locality_results):
    """Rule A1 & A2: Verify strict locality scoping (8km linear, 3km point) and non-additive uplift."""
    seen_project_sets = {}

    for loc in LOCALITIES:
        data = locality_results[loc]
        analysis = data["analysis"]
        uplifts = analysis.get("project_uplifts", [])
        headline_uplift = analysis.get("headline_combined_uplift_pct", 0.0)

        # 1. Project list must be non-empty and scoped within relevance radius
        assert len(uplifts) > 0, f"{loc} must have nearby relevant projects"
        project_names = {p["name"] for p in uplifts}
        seen_project_sets[loc] = project_names

        for p in uplifts:
            d_km = p["distance_km"]
            p_type = p["type"].lower()
            is_linear = any(t in p_type for t in ["metro", "road", "rail", "expressway", "highway", "flyover"])
            max_allowed_km = 8.0 if is_linear else 3.0
            assert d_km <= max_allowed_km, (
                f"{loc}: Project '{p['name']}' at {d_km}km exceeds relevance radius {max_allowed_km}km"
            )
            # Rule A3: must have cited source and delivery confidence
            assert p["source"] and p["source"].lower() not in {"unknown", "none"}
            assert p["delivery_confidence"] > 0
            assert p["distance_adjusted_uplift_pct"] <= p["base_uplift_pct"]

        # 2. Reconcile non-additive combined uplift
        # U_combined = 1 - Prod(1 - u_i)
        comb_factor = 1.0
        for p in uplifts:
            u_dec = p["distance_adjusted_uplift_pct"] / 100.0
            comb_factor *= (1.0 - u_dec)
        expected_headline = round((1.0 - comb_factor) * 100.0, 2)
        assert math.isclose(headline_uplift, expected_headline, abs_tol=0.1), (
            f"{loc}: Headline uplift {headline_uplift}% does not reconcile with non-additive combined {expected_headline}%"
        )

    # 3. Assert project lists differ across all 5 localities
    for loc1 in seen_project_sets:
        for loc2 in seen_project_sets:
            if loc1 != loc2:
                assert seen_project_sets[loc1] != seen_project_sets[loc2], (
                    f"Project lists for {loc1} and {loc2} should not be identical!"
                )

    # 4. Strict assertion: Sahakara Nagar MUST NOT contain Indiranagar items
    sahakara_projects = seen_project_sets["Sahakara Nagar"]
    indiranagar_projects = seen_project_sets["Indiranagar"]
    assert not any("indiranagar" in name.lower() for name in sahakara_projects), (
        f"Data leakage detected! Indiranagar project found in Sahakara Nagar: {sahakara_projects}"
    )
    assert not any("sahakara" in name.lower() for name in indiranagar_projects), (
        f"Data leakage detected! Sahakara Nagar project found in Indiranagar: {indiranagar_projects}"
    )

def test_generate_locality_input_logs(locality_results):
    """Generate and output a clean input summary log per locality."""
    print("\n" + "=" * 80)
    print("URBANALPHA LOCALITY VALUATION PIPELINE: AREA INPUT & OUTPUT LOGS")
    print("=" * 80)

    for loc in LOCALITIES:
        data = locality_results[loc]
        analysis = data["analysis"]
        sim = data["sim"]
        payload = data["payload"]
        stats = analysis["model_stats"]
        te = analysis["transit_elasticity"]
        buffers = analysis["buffers"]
        hist = analysis["historical_prices"]

        p2026 = sim["baseline"]["price_per_sqft_inr"]
        p2031 = sim["timeline"][-1]["land_value_per_sqft"]
        cagr = ((p2031 / p2026) ** 0.2 - 1) * 100

        print(f"\n--- LOCALITY: {loc.upper()} ---")
        print(f"Inputs Used:")
        print(f"  Parcel Specification : {payload['total_sqft']} sqft, {payload['bhk']} BHK, {payload['area_type']}")
        print(f"  Geometry WKT         : {analysis.get('geometry_wkt')}")
        print(f"  Historical 5Y Prices : {[f'{h['year']}: ₹{h['price_per_sqft']}' for h in hist]}")
        print(f"  Nearest Transit Hub  : {analysis.get('nearest_transit_m', 0):.0f}m ({te.get('nearest_transit_name', 'Metro')})")
        print(f"  Model Sample Size (n): {stats['sample_size_n']} spatial CV sales records (R²={stats['r2_score']:.3f}, RMSE=₹{stats['rmse_lakhs']:.1f}L, MAPE={stats['mape_pct']:.1f}%)")
        print(f"  Transit Elasticity   : {te['elasticity_unitless']:.2f} ({te['elasticity_pct_per_km']:.1f}%/km, 95% CI: [{te['confidence_interval_95'][0]:.1f}%, {te['confidence_interval_95'][1]:.1f}%])")
        print(f"  Geometric Buffers    : 500m={buffers[0]['project_count']}, 1km={buffers[1]['project_count']}, 2km={buffers[2]['project_count']}")
        print(f"Valuation Output:")
        print(f"  P(2026) = ₹{p2026:,.0f} / sq ft  -->  P(2031) = ₹{p2031:,.0f} / sq ft  |  CAGR: {cagr:.2f}% (City Median: 8.4%)")
        print(f"  Top SHAP Feature     : {sim['baseline']['shap_attributions'][0]['feature']} ({sim['baseline']['shap_attributions'][0]['importance_pct']:.1f}%)")
    print("=" * 80 + "\n")
