"""
OpenPark - Geofabrik Dataset Service
-------------------------------------
Provides programmatic access to Geofabrik OpenStreetMap extracts:
- Subregion catalog (India, Southern Zone [Karnataka], etc.)
- Metadata, file sizes, and download URLs (OSM PBF, Shapefile, Poly)
- Boundary GeoJSON polygons
"""

import os
import json
from typing import Dict, List, Optional, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "geofabrik")
REGIONS_FILE = os.path.join(DATA_DIR, "regions_india.json")


def list_geofabrik_regions() -> List[Dict[str, Any]]:
    """Returns available Geofabrik regional extracts for India and sub-zones."""
    if os.path.exists(REGIONS_FILE):
        try:
            with open(REGIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                features = data.get("features", [])
                results = []
                for feat in features:
                    props = feat.get("properties", {})
                    rid = props.get("id", "")
                    results.append({
                        "id": rid,
                        "name": props.get("name", rid.title()),
                        "parent": props.get("parent", "asia/india"),
                        "urls": props.get("urls", {}),
                        "poly_url": f"https://download.geofabrik.de/asia/india/{rid}.poly" if rid != "india" else "https://download.geofabrik.de/asia/india.poly",
                        "has_local_poly": os.path.exists(os.path.join(DATA_DIR, f"{rid}.poly")),
                        "has_local_geojson": os.path.exists(os.path.join(DATA_DIR, f"{rid}.geojson")),
                        "has_local_pbf": os.path.exists(os.path.join(DATA_DIR, f"{rid}-latest.osm.pbf")),
                        "is_primary": rid == "southern-zone"  # Karnataka & Bengaluru
                    })
                return results
        except Exception:
            pass

    # Default fallback
    return [
        {
            "id": "southern-zone",
            "name": "Southern Zone (Karnataka, Bengaluru, Tamil Nadu, Kerala, AP, Telangana)",
            "parent": "asia/india",
            "urls": {
                "pbf": "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf",
                "shp": "https://download.geofabrik.de/asia/india/southern-zone-latest-free.shp.zip",
                "gpkg": "https://download.geofabrik.de/asia/india/southern-zone-latest-free.gpkg.zip",
                "updates": "https://download.geofabrik.de/asia/india/southern-zone-updates"
            },
            "poly_url": "https://download.geofabrik.de/asia/india/southern-zone.poly",
            "has_local_poly": os.path.exists(os.path.join(DATA_DIR, "southern-zone.poly")),
            "has_local_geojson": os.path.exists(os.path.join(DATA_DIR, "southern-zone.geojson")),
            "has_local_pbf": os.path.exists(os.path.join(DATA_DIR, "southern-zone-latest.osm.pbf")),
            "is_primary": True
        },
        {
            "id": "india",
            "name": "India (Whole Country)",
            "parent": "asia",
            "urls": {
                "pbf": "https://download.geofabrik.de/asia/india-latest.osm.pbf",
                "updates": "https://download.geofabrik.de/asia/india-updates"
            },
            "poly_url": "https://download.geofabrik.de/asia/india.poly",
            "has_local_poly": os.path.exists(os.path.join(DATA_DIR, "india.poly")),
            "has_local_geojson": os.path.exists(os.path.join(DATA_DIR, "india.geojson")),
            "has_local_pbf": os.path.exists(os.path.join(DATA_DIR, "india-latest.osm.pbf")),
            "is_primary": False
        }
    ]


def get_region_details(region_id: str) -> Optional[Dict[str, Any]]:
    """Returns details and boundary geometry for a specific Geofabrik region."""
    regions = list_geofabrik_regions()
    matched = next((r for r in regions if r["id"] == region_id), None)
    if not matched:
        return None

    detail = dict(matched)
    geojson_path = os.path.join(DATA_DIR, f"{region_id}.geojson")
    if os.path.exists(geojson_path):
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                detail["boundary_geojson"] = json.load(f)
        except Exception:
            pass

    return detail


def get_geofabrik_status() -> Dict[str, Any]:
    """Returns local cache status for Geofabrik downloads."""
    regions = list_geofabrik_regions()
    local_files = []
    if os.path.exists(DATA_DIR):
        for f in os.listdir(DATA_DIR):
            p = os.path.join(DATA_DIR, f)
            if os.path.isfile(p):
                local_files.append({
                    "filename": f,
                    "size_bytes": os.path.getsize(p),
                    "size_mb": round(os.path.getsize(p) / (1024 * 1024), 2)
                })

    return {
        "status": "available",
        "provider": "Geofabrik GmbH (https://download.geofabrik.de/)",
        "license": "ODbL 1.0 (OpenStreetMap contributors)",
        "primary_region": "southern-zone (Karnataka / Bengaluru)",
        "available_regions_count": len(regions),
        "local_files": local_files
    }
