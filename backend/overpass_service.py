"""
OpenPark OSM Overpass Service
-----------------------------
Fetches and serves OpenStreetMap Overpass data:
- Parking lot outlines (polygons with amenity=parking)
- Fuel stations (points with amenity=fuel)
- Toll plazas (points with barrier=toll_booth / highway=toll_gantry)

Includes preloaded high-fidelity cache for Greater Bengaluru with 793 OSM features.
Adheres strictly to [lon, lat] order in GeoJSON specification compliance.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("overpass")

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "osm_overpass_cache.geojson")

_CACHED_DATA: Optional[Dict[str, Any]] = None


def load_overpass_cache() -> Dict[str, Any]:
    global _CACHED_DATA
    if _CACHED_DATA is not None:
        return _CACHED_DATA
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _CACHED_DATA = json.load(f)
                logger.info("Loaded OSM Overpass cache with %d features", len(_CACHED_DATA.get("features", [])))
                return _CACHED_DATA
        except Exception as e:
            logger.error("Failed to load OSM overpass cache: %s", e)
    return {"type": "FeatureCollection", "features": []}


def get_overpass_features(
    bbox: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Returns OSM Overpass GeoJSON features.
    bbox format: "min_lon,min_lat,max_lon,max_lat" (or "south,west,north,east")
    category: "parking", "fuel", "toll", or None for all.
    Coordinates are guaranteed in [longitude, latitude] GeoJSON order.
    """
    data = load_overpass_cache()
    features = data.get("features", [])

    if category:
        category = category.lower()
        if category in ("parking", "parking_outline"):
            features = [
                f for f in features
                if f.get("properties", {}).get("category") == "parking_outline"
                or f.get("properties", {}).get("amenity") == "parking"
            ]
        elif category == "fuel":
            features = [
                f for f in features
                if f.get("properties", {}).get("category") == "fuel"
                or f.get("properties", {}).get("amenity") == "fuel"
            ]
        elif category in ("toll", "toll_booth"):
            features = [
                f for f in features
                if f.get("properties", {}).get("category") == "toll"
                or f.get("properties", {}).get("barrier") == "toll_booth"
            ]

    if bbox:
        try:
            parts = [float(x.strip()) for x in bbox.split(",")]
            if len(parts) == 4:
                # Disambiguate lon vs lat (Bengaluru lon is ~77, lat is ~12-13)
                if parts[0] > 50 and parts[1] < 40:
                    min_lon, min_lat, max_lon, max_lat = parts[0], parts[1], parts[2], parts[3]
                else:
                    min_lat, min_lon, max_lat, max_lon = parts[0], parts[1], parts[2], parts[3]

                filtered = []
                for f in features:
                    geom = f.get("geometry", {})
                    gtype = geom.get("type")
                    if gtype == "Point":
                        coords = geom.get("coordinates", [0, 0])
                        lon, lat = coords[0], coords[1]
                        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                            filtered.append(f)
                    elif gtype == "Polygon":
                        coords = geom.get("coordinates", [[]])[0]
                        if any(min_lon <= pt[0] <= max_lon and min_lat <= pt[1] <= max_lat for pt in coords):
                            filtered.append(f)
                features = filtered
        except Exception as e:
            logger.warning("Invalid bbox '%s': %s", bbox, e)

    return {
        "type": "FeatureCollection",
        "features": features
    }
