"""Spatial layer tests: projector, distance, buffer impact."""

from __future__ import annotations

from shapely.geometry import Point

from app.spatial.buffers import LocalProjector, buffer_impact, distance_m
from app.spatial.localities import locality_centroid


def test_local_projector_roundtrip():
    proj = LocalProjector.bengaluru()
    x, y = proj.project(77.7, 13.0)
    lon, lat = proj.unproject(x, y)
    assert abs(lon - 77.7) < 1e-9
    assert abs(lat - 13.0) < 1e-9


def test_distance_metres_reasonable():
    whitefield = locality_centroid("Whitefield")  # 77.7499, 12.9696
    marathahalli = Point(77.6884, 12.9556)
    d = distance_m(whitefield, marathahalli)
    # ~6 km apart in reality; allow a generous band for the projection.
    assert 4000.0 < d < 9000.0


def test_buffer_impact_counts_colocated_project():
    centroid = locality_centroid("Whitefield")
    projects = [
        {"project_id": "p1", "name": "Whitefield Metro", "geometry": "POINT (77.7499 12.9696)"},
        {"project_id": "p2", "name": "Distant Highway", "geometry": "POINT (77.50 13.05)"},
    ]
    impact = buffer_impact(projects, centroid, (500, 1000, 2000))
    for r in (500, 1000, 2000):
        assert impact[r]["project_count"] == 1
        assert impact[r]["projects"][0]["project_id"] == "p1"


def test_buffer_impact_no_centroid_returns_empty():
    projects = [{"project_id": "p1", "name": "x", "geometry": "POINT (77.7 12.9)"}]
    impact = buffer_impact(projects, None, (500, 1000, 2000))
    assert all(impact[r]["project_count"] == 0 for r in (500, 1000, 2000))
