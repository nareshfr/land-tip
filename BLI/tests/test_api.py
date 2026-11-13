"""FastAPI endpoint tests via TestClient."""

from __future__ import annotations

import pytest

from app.main import app


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "baseline_model_ready" in body


def test_root_lists_endpoints(client):
    r = client.get("/")
    assert r.status_code == 200
    endpoints = r.json()["endpoints"]
    assert "POST /parcel/analyze" in endpoints
    assert "POST /simulation/run" in endpoints


def test_scrape_live_endpoint(client):
    r = client.post("/infrastructure/scrape-live")
    assert r.status_code == 200
    body = r.json()
    assert body["projects_stored"] == 7
    assert set(body["affected_parcels_by_radius"]) == {"500", "1000", "2000"}


def test_list_infrastructure(client):
    client.post("/infrastructure/scrape-live")
    r = client.get("/infrastructure/")
    assert r.status_code == 200
    assert r.json()["count"] == 7


@pytest.mark.skipif(
    not __import__("app.baseline", fromlist=["get_seed"]).get_seed().is_ready(),
    reason="baseline model artifacts missing",
)
def test_parcel_analyze_endpoint(client):
    client.post("/infrastructure/scrape-live")
    r = client.post("/parcel/analyze", json={
        "location": "Whitefield", "total_sqft": 2400, "bhk": 3, "bath": 2,
        "balcony": 1, "area_type": "Plot  Area",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["baseline"]["predicted_price_lakhs"] > 0
    radii = {b["radius_m"] for b in body["buffers"]}
    assert radii == {500, 1000, 2000}
    # Whitefield metro fixture is co-located -> at least one project within 2000m.
    by2000 = next(b for b in body["buffers"] if b["radius_m"] == 2000)
    assert by2000["project_count"] >= 1


@pytest.mark.skipif(
    not __import__("app.baseline", fromlist=["get_seed"]).get_seed().is_ready(),
    reason="baseline model artifacts missing",
)
def test_simulation_run_and_fetch(client):
    client.post("/infrastructure/scrape-live")
    r = client.post("/simulation/run", json={
        "parcel": {"location": "Whitefield", "total_sqft": 2400, "bhk": 3,
                    "bath": 2, "balcony": 1, "area_type": "Plot  Area"},
        "config": {"years": 3, "households": 20, "developers": 3, "seed": 5},
    })
    assert r.status_code == 200
    body = r.json()
    run_id = body["run_id"]
    assert len(body["timeline"]) == 4
    assert "future_valuation" in body
    assert body["future_valuation"]["land_value_index"] == body["timeline"][-1]["land_value_index"]

    # Fetch it back.
    g = client.get(f"/simulation/{run_id}")
    assert g.status_code == 200
    gbody = g.json()
    assert gbody["found"] is True
    assert gbody["run_id"] == run_id
    assert len(gbody["timeline"]) == 4


def test_simulation_fetch_missing(client):
    r = client.get("/simulation/does-not-exist")
    assert r.status_code == 200
    assert r.json()["found"] is False
