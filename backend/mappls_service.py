"""
OpenPark — Mappls (MapmyIndia) REST API Service
Integrates location intelligence, search, and routing based on:
https://github.com/mappls-api/mapmyindia-rest-api
"""

import os
import math
import httpx
from typing import Optional, List, Dict, Any

MAPPLS_REST_KEY = os.getenv("MAPPLS_REST_KEY", "").strip()
MAPPLS_CLIENT_ID = os.getenv("MAPPLS_CLIENT_ID", "").strip()
MAPPLS_CLIENT_SECRET = os.getenv("MAPPLS_CLIENT_SECRET", "").strip()

HTTP_TIMEOUT = 6.0


def get_mappls_config() -> Dict[str, Any]:
    global MAPPLS_REST_KEY
    key = os.getenv("MAPPLS_REST_KEY", MAPPLS_REST_KEY).strip()
    return {
        "engine": "Mappls REST API (MapmyIndia)",
        "api_docs": "https://github.com/mappls-api/mapmyindia-rest-api",
        "has_rest_key": bool(key),
        "rest_key_preview": f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else ("configured" if key else ""),
        "endpoints": {
            "autosuggest": "/api/mappls/autosuggest",
            "route": "/api/mappls/route",
            "nearby": "/api/mappls/nearby",
            "rev_geocode": "/api/mappls/rev_geocode"
        }
    }


def set_mappls_rest_key(key: str) -> bool:
    global MAPPLS_REST_KEY
    MAPPLS_REST_KEY = key.strip()
    os.environ["MAPPLS_REST_KEY"] = MAPPLS_REST_KEY

    # Persist to .env if present
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            found = False
            new_lines = []
            for line in lines:
                if line.startswith("MAPPLS_REST_KEY="):
                    new_lines.append(f"MAPPLS_REST_KEY={MAPPLS_REST_KEY}\n")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"MAPPLS_REST_KEY={MAPPLS_REST_KEY}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
        except Exception as e:
            print(f"Error persisting MAPPLS_REST_KEY to .env: {e}")
    return True


async def autosuggest(query: str, lat: float = 12.9716, lon: float = 77.5946) -> List[Dict[str, Any]]:
    """
    Search places and parking using Mappls AutoSuggest REST API:
    https://github.com/mappls-api/mapmyindia-rest-api/tree/master/docs
    Fallback: Photon OSM geocoder + local municipal lots.
    """
    key = os.getenv("MAPPLS_REST_KEY", MAPPLS_REST_KEY).strip()
    if key and len(query) >= 2:
        try:
            url = f"https://apis.mappls.com/advancedmaps/v1/{key}/autosuggest"
            params = {
                "query": query,
                "location": f"{lat},{lon}",
                "bridge": "true"
            }
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    results = []
                    # Mappls format: data.suggestedLocations
                    for item in data.get("suggestedLocations", []):
                        item_lat = item.get("latitude")
                        item_lon = item.get("longitude")
                        if item_lat and item_lon:
                            results.append({
                                "name": item.get("placeName", query),
                                "address": item.get("placeAddress", ""),
                                "lat": float(item_lat),
                                "lon": float(item_lon),
                                "eLoc": item.get("eLoc", ""),
                                "source": "mappls"
                            })
                    if results:
                        return results
        except Exception as e:
            print(f"Mappls AutoSuggest notice: {e}, falling back to local/OSM")

    # Fallback to Photon OpenStreetMap geocoder
    try:
        url = "https://photon.komoot.io/api/"
        params = {"q": query, "lat": lat, "lon": lon, "limit": 6}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                results = []
                for feat in data.get("features", []):
                    p = feat.get("properties", {})
                    coords = feat.get("geometry", {}).get("coordinates", [])
                    if len(coords) >= 2:
                        name = p.get("name") or query
                        addr_parts = [p.get("street"), p.get("city"), p.get("state")]
                        addr = ", ".join([a for a in addr_parts if a]) or "Bengaluru"
                        results.append({
                            "name": name,
                            "address": addr,
                            "lat": coords[1],
                            "lon": coords[0],
                            "source": "osm_photon"
                        })
                if results:
                    return results
    except Exception:
        pass

    # Fallback simulated response around current location
    return [
        {
            "name": f"{query} Plaza",
            "address": "MG Road, Bengaluru",
            "lat": lat + 0.003,
            "lon": lon + 0.004,
            "source": "fallback"
        },
        {
            "name": f"{query} Commercial Center",
            "address": "Brigade Road, Bengaluru",
            "lat": lat - 0.004,
            "lon": lon - 0.003,
            "source": "fallback"
        }
    ]


async def get_directions(
    start_lat: float,
    start_lon: float,
    dest_lat: float,
    dest_lon: float
) -> Dict[str, Any]:
    """
    Computes driving navigation route using Mappls Advanced Routing REST API:
    https://github.com/mappls-api/mapmyindia-rest-api
    Fallback: OSRM or smooth road spline.
    """
    key = os.getenv("MAPPLS_REST_KEY", MAPPLS_REST_KEY).strip()
    if key:
        try:
            # Mappls Advanced Route API driving endpoint:
            # https://apis.mappls.com/advancedmaps/v1/{REST_KEY}/route_adv/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson&steps=true
            url = f"https://apis.mappls.com/advancedmaps/v1/{key}/route_adv/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}"
            params = {
                "overview": "full",
                "geometries": "geojson",
                "steps": "true"
            }
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    routes = data.get("routes", [])
                    if routes:
                        r0 = routes[0]
                        coords = r0.get("geometry", {}).get("coordinates", [])
                        duration_sec = r0.get("duration", 0)
                        distance_m = r0.get("distance", 0)
                        legs = r0.get("legs", [])
                        steps = []
                        if legs:
                            for st in legs[0].get("steps", []):
                                instruction = st.get("maneuver", {}).get("instruction") or st.get("name") or "Continue"
                                dist_step = st.get("distance", 0)
                                steps.append({
                                    "instruction": instruction,
                                    "dist": f"{int(dist_step)} m" if dist_step < 1000 else f"{dist_step/1000:.1f} km"
                                })
                        return {
                            "status": "ok",
                            "source": "mappls_rest_api",
                            "coordinates": coords,
                            "distance_km": round(distance_m / 1000.0, 2),
                            "duration_min": max(1, math.ceil(duration_sec / 60.0)),
                            "steps": steps or [
                                {"instruction": "Head towards destination", "dist": "300 m"},
                                {"instruction": "Turn into parking gate", "dist": "Destination on right"}
                            ]
                        }
        except Exception as e:
            print(f"Mappls Directions notice: {e}, falling back to OSRM/spline")

    # Fallback to local OSRM or public OSRM
    osrm_url = os.getenv("OSRM_URL", "http://router.project-osrm.org")
    try:
        route_url = f"{osrm_url}/route/v1/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson&steps=true"
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            res = await client.get(route_url)
            if res.status_code == 200:
                data = res.json()
                if data.get("routes"):
                    r = data["routes"][0]
                    coords = r.get("geometry", {}).get("coordinates", [])
                    steps = []
                    for leg in r.get("legs", []):
                        for st in leg.get("steps", []):
                            man = st.get("maneuver", {})
                            instr = man.get("instruction") or f"Continue along {st.get('name') or 'road'}"
                            d = st.get("distance", 0)
                            steps.append({
                                "instruction": instr,
                                "dist": f"{int(d)} m" if d < 1000 else f"{d/1000:.1f} km"
                            })
                    return {
                        "status": "ok",
                        "source": "osrm",
                        "coordinates": coords,
                        "distance_km": round(r.get("distance", 0) / 1000.0, 2),
                        "duration_min": max(1, math.ceil(r.get("duration", 0) / 60.0)),
                        "steps": steps
                    }
    except Exception:
        pass

    # Smooth organic road spline generator (Zero dependency fallback)
    coords = []
    n_points = 80
    for i in range(n_points + 1):
        t = i / n_points
        # Add slight natural road curvi-linear curvature
        curve_lon = math.sin(t * math.pi) * 0.0018
        curve_lat = math.sin(t * math.pi * 2) * 0.0012
        lon = start_lon + (dest_lon - start_lon) * t + curve_lon
        lat = start_lat + (dest_lat - start_lat) * t + curve_lat
        coords.append([round(lon, 6), round(lat, 6)])

    # Haversine distance
    R = 6371.0
    dlat = math.radians(dest_lat - start_lat)
    dlon = math.radians(dest_lon - start_lon)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(start_lat)) * math.cos(math.radians(dest_lat)) *
         math.sin(dlon / 2) ** 2)
    dist_km = 2 * R * math.asin(math.sqrt(max(0, a)))

    return {
        "status": "ok",
        "source": "road_spline",
        "coordinates": coords,
        "distance_km": round(max(0.2, dist_km), 2),
        "duration_min": max(2, math.ceil(dist_km / 0.45)),
        "steps": [
            {"instruction": "Head along main route", "dist": "450 m"},
            {"instruction": "Turn towards destination street", "dist": "700 m"},
            {"instruction": "Slow down approaching entrance", "dist": "150 m"},
            {"instruction": "Arrive at parking entrance", "dist": "Destination on right"}
        ]
    }
