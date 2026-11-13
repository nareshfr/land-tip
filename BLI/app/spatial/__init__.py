"""Spatial processing.

All geometry math is done in Python via Shapely using a local equirectangular
projection (metres) around a reference latitude. This avoids requiring a live
PostGIS to answer buffer queries, while remaining numerically equivalent for
the few-kilometre distances relevant to urban land valuation. When PostGIS is
configured, the same WKT geometries are persisted to ``geometry`` columns.
"""

from app.spatial.buffers import (
    LocalProjector,
    buffer_impact,
    distance_m,
    parse_geometry,
    point_wkt,
)
from app.spatial.localities import locality_centroid

__all__ = [
    "LocalProjector",
    "buffer_impact",
    "distance_m",
    "parse_geometry",
    "point_wkt",
    "locality_centroid",
]
