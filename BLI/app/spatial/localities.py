"""Small built-in geocoder for common Bengaluru localities.

Used to assign a parcel centroid when the caller does not supply a GeoJSON
geometry. Falls back to the city centre. This is intentionally tiny and static;
a real deployment would use a geocoding service, but it keeps the demo runnable
without network access.
"""

from __future__ import annotations

from shapely.geometry import Point

from app.config import get_settings

# (name_lower, lon, lat)
_LOCALITIES = {
    "whitefield": (77.7499, 12.9696),
    "electronic city": (77.6716, 12.8452),
    "electronic city phase ii": (77.6863, 12.8190),
    "koramangala": (77.6264, 12.9352),
    "indiranagar": (77.6412, 12.9719),
    "hsr layout": (77.6488, 12.9082),
    "hebbal": (77.5964, 13.0358),
    "yelahanka": (77.5959, 13.1006),
    "marathahalli": (77.6884, 12.9556),
    "sarjapur road": (77.6877, 12.9105),
    "jp nagar": (77.5838, 12.9082),
    "jayanagar": (77.5920, 12.9250),
    "bannerghatta road": (77.6144, 12.8933),
    "malleshwaram": (77.5650, 13.0030),
    "rajajinagar": (77.5532, 12.9870),
    "hebbal kempapura": (77.5920, 13.0420),
    "thanisandra": (77.6210, 13.0480),
    "bommanahalli": (77.6184, 12.9155),
    "vijayanagar": (77.5340, 12.9590),
    "sadashiva nagar": (77.5720, 13.0140),
}


def locality_centroid(location: str) -> Point:
    """Return a lon/lat Point for a Bengaluru locality, defaulting to city centre."""
    s = get_settings()
    key = (location or "").strip().lower()
    lon, lat = _LOCALITIES.get(key, (s.bengaluru_lon, s.bengaluru_lat))
    return Point(lon, lat)
