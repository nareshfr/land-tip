"""Metre-accurate geometry helpers built on Shapely.

Bengaluru is small enough that a local equirectangular projection is accurate to
well under 1% for distances up to a few kilometres, so we avoid a hard pyproj
dependency. Distances and buffers are computed in metres.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from shapely.geometry import Point, mapping, shape
from shapely import wkt as _wkt
import shapely
import numpy as np

from app.config import get_settings

_M_PER_DEG_LAT = 111_320.0  # mean metres per degree latitude


@dataclass
class LocalProjector:
    lat0: float
    lon0: float

    @classmethod
    def bengaluru(cls) -> "LocalProjector":
        s = get_settings()
        return cls(lat0=s.bengaluru_lat, lon0=s.bengaluru_lon)

    def project(self, lon: float, lat: float) -> tuple[float, float]:
        """lon/lat (EPSG:4326) -> local metres (x east, y north)."""
        x = (lon - self.lon0) * _M_PER_DEG_LAT * math.cos(math.radians(self.lat0))
        y = (lat - self.lat0) * _M_PER_DEG_LAT
        return x, y

    def unproject(self, x: float, y: float) -> tuple[float, float]:
        lon = self.lon0 + x / (_M_PER_DEG_LAT * math.cos(math.radians(self.lat0)))
        lat = self.lat0 + y / _M_PER_DEG_LAT
        return lon, lat


def distance_m(p1: Point, p2: Point) -> float:
    """Great-circle-ish distance in metres between two lon/lat Shapely points."""
    proj = LocalProjector.bengaluru()
    x1, y1 = proj.project(p1.x, p1.y)
    x2, y2 = proj.project(p2.x, p2.y)
    return math.hypot(x2 - x1, y2 - y1)


def point_wkt(lon: float, lat: float) -> str:
    return f"POINT ({lon} {lat})"


def parse_geometry(geojson: Optional[dict] = None, wkt: Optional[str] = None):
    """Parse a geometry from GeoJSON dict or WKT string into a Shapely geometry."""
    if geojson is not None:
        # Accept either a Feature or a bare geometry.
        geom = geojson.get("geometry", geojson) if isinstance(geojson, dict) else None
        if geom is None:
            return None
        return shape(geom)
    if wkt:
        return _wkt.loads(wkt)
    return None


def geometry_centroid_lonlat(geom) -> Optional[Point]:
    if geom is None:
        return None
    c = geom.centroid
    return Point(c.x, c.y)


def buffer_impact(
    projects: list[dict],
    parcel_centroid: Optional[Point],
    radii_m: tuple[int, ...],
) -> dict[int, dict]:
    """For each radius, return the count and list of infrastructure projects whose
    geometry is within ``radius`` metres of the parcel centroid.

    Returns ``{radius_m: {"radius_m": r, "project_count": n, "projects": [...]}}``.
    Projects lacking geometry are skipped from spatial matching.
    """
    result: dict[int, dict] = {}
    if parcel_centroid is None:
        for r in radii_m:
            result[r] = {"radius_m": r, "project_count": 0, "projects": []}
        return result

    for r in radii_m:
        within: list[dict] = []
        for proj in projects:
            g = _project_geometry(proj)
            if g is None:
                continue
            # Use nearest point distance so LINESTRING/POLYGON corridors count.
            d = _distance_geometry_m(parcel_centroid, g)
            if d <= r:
                within.append({**proj, "distance_m": round(d, 1)})
        result[r] = {"radius_m": r, "project_count": len(within), "projects": within}
    return result


def _project_geometry(proj: dict):
    g = proj.get("geometry")
    if g is None:
        w = proj.get("geometry_wkt")
        if w:
            try:
                return _wkt.loads(w)
            except Exception:
                return None
        return None
    if hasattr(g, "geom_type"):
        return g
    if isinstance(g, str):
        try:
            return _wkt.loads(g)
        except Exception:
            return None
    try:
        return shape(g)
    except Exception:
        return None


def _distance_geometry_m(point: Point, geom) -> float:
    """True Euclidean distance in metres from a lon/lat point to a lon/lat geometry.

    Transforms the geometry into local metre coordinates so that Point,
    LineString transit/road corridors, and Polygon boundaries compute accurate
    edge-to-edge distances in metres.
    """
    proj = LocalProjector.bengaluru()
    px, py = proj.project(point.x, point.y)
    p_m = Point(px, py)
    try:
        cos_lat = math.cos(math.radians(proj.lat0))

        def _trans(coords):
            xs = (coords[:, 0] - proj.lon0) * _M_PER_DEG_LAT * cos_lat
            ys = (coords[:, 1] - proj.lat0) * _M_PER_DEG_LAT
            if coords.shape[1] > 2:
                return np.column_stack([xs, ys, coords[:, 2:]])
            return np.column_stack([xs, ys])

        geom_m = shapely.transform(geom, _trans)
        return float(p_m.distance(geom_m))
    except Exception:
        rep = geom.centroid if hasattr(geom, "centroid") else geom.representative_point()
        gx, gy = proj.project(rep.x, rep.y)
        return float(math.hypot(gx - px, gy - py))


def to_geojson(geom) -> Optional[dict]:
    if geom is None:
        return None
    return mapping(geom)
