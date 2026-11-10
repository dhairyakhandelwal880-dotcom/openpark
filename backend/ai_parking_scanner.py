"""
OpenPark AI Map Space & Legal Parking Scanner
---------------------------------------------
Reads OpenStreetMap vector geometry (live Overpass API + local OSM & FTS5 fallback)
to discover empty grounds, mall/commercial plazas, and legal street/surface bays
that are NOT already in the uploaded OpenPark parking dataset.
"""

import math
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger("openpark.ai_scanner")

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

ILLEGAL_ACCESS = {"private", "no", "restricted", "military", "permit", "delivery", "employees", "students"}
ILLEGAL_LANDUSE = {"military", "cemetery", "quarry", "landfill", "railway", "industrial", "construction"}
ILLEGAL_NATURAL = {"water", "wetland", "mud", "cliff", "glacier"}
ILLEGAL_HIGHWAY = {"motorway", "motorway_link", "trunk", "trunk_link", "pedestrian", "footway", "cycleway", "steps"}
ILLEGAL_AMENITY = {"fire_station", "prison", "school", "kindergarten", "police"}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def compute_polygon_area_m2(coords: List[List[float]]) -> float:
    """
    Calculates approximate surface area (m^2) for a [lon, lat] polygon ring
    using equirectangular projection around the ring centroid + Shoelace formula.
    """
    if not coords or len(coords) < 3:
        return 0.0
    avg_lat = sum(pt[1] for pt in coords) / len(coords)
    m_per_lat = 111132.92
    m_per_lon = 111412.84 * max(0.1, math.cos(math.radians(avg_lat)))

    proj = [(pt[0] * m_per_lon, pt[1] * m_per_lat) for pt in coords]
    area = 0.0
    n = len(proj)
    for i in range(n):
        x1, y1 = proj[i]
        x2, y2 = proj[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def compute_centroid(coords: List[List[float]]) -> Tuple[float, float]:
    """Returns (lat, lon) centroid for a ring of [lon, lat] points."""
    if not coords:
        return (0.0, 0.0)
    ring = coords[:-1] if len(coords) > 1 and coords[0] == coords[-1] else coords
    lon = sum(pt[0] for pt in ring) / len(ring)
    lat = sum(pt[1] for pt in ring) / len(ring)
    return (lat, lon)


def is_duplicate_of_existing(
    lat: float,
    lon: float,
    name: str,
    existing_lots: List[Dict[str, Any]],
    threshold_m: float = 85.0
) -> bool:
    """Returns True if candidate overlaps already-uploaded OpenPark parking lots."""
    name_clean = (name or "").strip().lower()
    for lot in existing_lots:
        l_lat = lot.get("lat")
        l_lon = lot.get("lon")
        if l_lat is None or l_lon is None:
            continue
        dist = haversine_m(lat, lon, float(l_lat), float(l_lon))
        if dist < threshold_m:
            return True
        lot_name = (lot.get("name") or "").strip().lower()
        if name_clean and lot_name and name_clean == lot_name and dist < 250.0:
            return True
    return False


def classify_and_score_candidate(
    tags: Dict[str, str],
    name: str,
    area_m2: float,
    dist_m: float
) -> Optional[Dict[str, Any]]:
    """
    AI Legality, Suitability & Surface Reasoning Engine.
    Filters out restricted/private/illegal areas and scores valid empty grounds,
    mall plazas, and legal public parking areas.
    """
    access = (tags.get("access") or "").lower()
    parking_tag = (tags.get("parking") or "").lower()
    landuse = (tags.get("landuse") or "").lower()
    natural = (tags.get("natural") or "").lower()
    highway = (tags.get("highway") or "").lower()
    amenity = (tags.get("amenity") or "").lower()
    shop = (tags.get("shop") or "").lower()
    building = (tags.get("building") or "").lower()
    leisure = (tags.get("leisure") or "").lower()
    surface = (tags.get("surface") or "").lower()
    fee = (tags.get("fee") or "").lower()
    lit = (tags.get("lit") or "").lower()
    name_lower = (name or "").lower()

    # Hard rejection of illegal / restricted / unsafe zones
    if access in ILLEGAL_ACCESS:
        return None
    if parking_tag == "no" or tags.get("motor_vehicle") == "no":
        return None
    if landuse in ILLEGAL_LANDUSE or natural in ILLEGAL_NATURAL:
        return None
    if highway in ILLEGAL_HIGHWAY or amenity in ILLEGAL_AMENITY:
        return None
    if any(bad in name_lower for bad in ("private", "restricted", "army", "cantonment", "no parking", "graveyard", "lake")):
        return None

    # Determine category
    cat_key = None
    cat_label = ""
    badge = "🅿️"
    color = "#34c759"

    is_mall = (
        shop == "mall"
        or building in ("mall", "commercial", "retail", "supermarket")
        or amenity == "marketplace"
        or landuse == "retail"
        or any(k in name_lower for k in ("mall", "plaza", "centre", "center", "market", "complex", "galleria", "arcade"))
    )
    is_ground = (
        landuse in ("brownfield", "greenfield", "grass", "meadow", "recreation_ground", "village_green")
        or leisure in ("common",)
        or surface in ("unpaved", "gravel", "dirt", "compacted", "ground", "earth")
        or any(k in name_lower for k in ("ground", "maidan", "open lot", "field"))
    )
    is_legal_bay = (
        amenity in ("parking", "parking_space")
        or parking_tag in ("surface", "street_side", "layby", "lane", "multi-storey", "underground")
        or highway in ("rest_area", "services")
        or landuse == "commercial"
    )

    if is_mall:
        cat_key = "mall_parking"
        cat_label = "Mall / Commercial Plaza"
        badge = "🛍️"
        color = "#0071e3"
    elif is_ground:
        # Ignore tiny turf patches (< 180 m^2) that cannot legally hold vehicles
        if 0 < area_m2 < 180:
            return None
        cat_key = "empty_ground"
        cat_label = "Empty Open Ground"
        badge = "🟩"
        color = "#ff9500"
    elif is_legal_bay:
        cat_key = "legal_bay"
        cat_label = "Legal Public Bay"
        badge = "🅿️"
        color = "#34c759"
    else:
        return None

    # Estimate bay capacity from real polygon area (~28 m^2 per bay including aisles)
    if area_m2 >= 60:
        est_spots = max(2, int(round((area_m2 * 0.58) / 14.5)))
    elif cat_key == "mall_parking":
        est_spots = 65
    elif cat_key == "empty_ground":
        est_spots = 24
    else:
        est_spots = 14

    if tags.get("capacity") and str(tags["capacity"]).isdigit():
        est_spots = max(2, int(tags["capacity"]))

    # Compute AI Score (0..100)
    score = 62
    reasons: List[str] = []

    if access in ("yes", "public", "permissive"):
        score += 14
        reasons.append("Public legal access verified")
        legality = "Verified Legal Public"
    elif access == "customers" or cat_key == "mall_parking":
        score += 9
        reasons.append("Commercial visitor parking")
        legality = "Commercial Visitor Legal"
    elif cat_key == "empty_ground":
        score += 4
        reasons.append("Unrestricted open ground (check local signage)")
        legality = "Open Ground (Verify Sign)"
    else:
        score += 8
        reasons.append("No no-parking restriction tags")
        legality = "Unrestricted Public"

    if surface in ("asphalt", "concrete", "paved", "paving_stones"):
        score += 8
        reasons.append(f"Paved ({surface})")
    elif surface:
        reasons.append(f"Surface: {surface}")
    elif cat_key == "mall_parking":
        score += 6
        reasons.append("Structured plaza surface")

    if fee == "no":
        score += 7
        reasons.append("Free parking")
    elif fee == "yes":
        reasons.append("Paid bay")

    if lit == "yes":
        score += 4
        reasons.append("Street/lot lighting")

    if area_m2 >= 400:
        score += 5
        reasons.append(f"~{int(round(area_m2)):,} m² (~{est_spots} cars)")
    else:
        reasons.append(f"Est. ~{est_spots} bays")

    # Distance penalty so closer usable spots rank higher
    score -= min(18, int(dist_m / 120.0))
    score = max(35, min(98, score))

    return {
        "category": cat_key,
        "category_label": cat_label,
        "badge": badge,
        "color": color,
        "ai_score": score,
        "legality_status": legality,
        "estimated_spots": est_spots,
        "surface": surface or ("paved" if cat_key == "mall_parking" else "unpaved" if cat_key == "empty_ground" else "asphalt"),
        "fee": "Free" if fee == "no" else ("Paid" if fee == "yes" else ("Mall Rates" if cat_key == "mall_parking" else "Free / Unmetered")),
        "reason": " • ".join(reasons)
    }


async def _fetch_overpass_candidates(lat: float, lon: float, radius_m: int) -> Optional[List[Dict[str, Any]]]:
    """Queries live Overpass API for parking polygons, malls, commercial plazas & open grounds."""
    r = max(300, min(int(radius_m), 2500))
    query = f"""
    [out:json][timeout:6];
    (
      way["amenity"="parking"](around:{r},{lat},{lon});
      way["amenity"="parking_space"](around:{r},{lat},{lon});
      way["shop"="mall"](around:{r},{lat},{lon});
      node["shop"="mall"](around:{r},{lat},{lon});
      way["amenity"="marketplace"](around:{r},{lat},{lon});
      way["landuse"="brownfield"](around:{r},{lat},{lon});
      way["landuse"="greenfield"](around:{r},{lat},{lon});
      way["landuse"="commercial"](around:{r},{lat},{lon});
      way["highway"="rest_area"](around:{r},{lat},{lon});
    );
    out tags center geom;
    """
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            async with httpx.AsyncClient(timeout=5.5) as client:
                resp = await client.post(endpoint, data={"data": query})
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("elements", [])
        except Exception as exc:
            logger.debug("Overpass scan endpoint %s unavailable: %s", endpoint, exc)
    return None


def _load_local_fallback_candidates(lat: float, lon: float, radius_m: int) -> List[Dict[str, Any]]:
    """
    Reads local cached OSM Overpass GeoJSON (793 polygons) + offline FTS5 places DB
    so AI Map Scan stays fast and functional even offline or if Overpass rate-limits.
    """
    elements: List[Dict[str, Any]] = []
    try:
        from overpass_service import load_overpass_cache
        cache = load_overpass_cache()
        for feat in cache.get("features", []):
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            if gtype == "Polygon":
                ring = (geom.get("coordinates") or [[]])[0]
                if not ring:
                    continue
                c_lat, c_lon = compute_centroid(ring)
                if haversine_m(lat, lon, c_lat, c_lon) <= radius_m:
                    elements.append({
                        "type": "way",
                        "id": f"cache_{props.get('id') or len(elements)}",
                        "tags": {
                            "name": props.get("name") or "Discovered Surface Lot",
                            "amenity": props.get("amenity") or ("parking" if props.get("category") == "parking_outline" else ""),
                            "surface": props.get("surface") or "asphalt",
                            "access": props.get("access") or "yes",
                            "fee": props.get("fee") or "",
                        },
                        "center": {"lat": c_lat, "lon": c_lon},
                        "geometry": [{"lat": pt[1], "lon": pt[0]} for pt in ring],
                    })
    except Exception as exc:
        logger.debug("Local overpass cache fallback error: %s", exc)

    try:
        from places_db import search_places_nearby
        nearby = search_places_nearby(lat=lat, lon=lon, radius_km=max(0.8, (radius_m * 1.3) / 1000.0), limit=100)
        for p in nearby:
            cat_l = (p.get("category") or "").lower()
            name_l = (p.get("name") or "").lower()
            tags: Dict[str, str] = {"name": p.get("name") or "Area"}
            if any(k in cat_l or k in name_l for k in ("mall", "shopping", "market", "plaza", "commercial", "complex", "galleria", "centre", "center")):
                tags["shop"] = "mall"
                tags["access"] = "customers"
            elif any(k in cat_l or k in name_l for k in ("ground", "maidan", "stadium", "open", "field")):
                tags["landuse"] = "brownfield"
                tags["surface"] = "unpaved"
            elif "parking" in cat_l or "parking" in name_l:
                tags["amenity"] = "parking"
                tags["access"] = "yes"
            else:
                continue

            elements.append({
                "type": "node",
                "id": f"db_{p.get('id')}",
                "tags": tags,
                "lat": float(p["lat"]),
                "lon": float(p["lon"]),
            })
    except Exception as exc:
        logger.debug("Local places_db fallback error: %s", exc)

    try:
        from traccar_service import BENGALURU_PLACES_CATALOG
        for idx, item in enumerate(BENGALURU_PLACES_CATALOG):
            c_lat = float(item.get("lat", 0.0))
            c_lon = float(item.get("lon", 0.0))
            if haversine_m(lat, lon, c_lat, c_lon) > max(radius_m, 2000):
                continue
            cat_l = (item.get("category") or "").lower()
            name_l = (item.get("name") or "").lower()
            tags_cat: Dict[str, str] = {"name": item["name"]}
            if any(k in cat_l or k in name_l for k in ("mall", "shopping", "plaza", "commercial", "forum", "orion", "ub city", "mantri", "garuda", "vega")):
                tags_cat["shop"] = "mall"
                tags_cat["access"] = "customers"
            elif any(k in cat_l or k in name_l for k in ("ground", "maidan", "stadium", "sports", "palace")):
                tags_cat["landuse"] = "brownfield"
                tags_cat["surface"] = "unpaved"
            elif "parking" in cat_l or "parking" in name_l:
                tags_cat["amenity"] = "parking"
                tags_cat["access"] = "yes"
            else:
                continue
            elements.append({
                "type": "node",
                "id": f"cat_{idx}",
                "tags": tags_cat,
                "lat": c_lat,
                "lon": c_lon,
            })
    except Exception as exc:
        logger.debug("Catalog enrichment error: %s", exc)

    return elements


async def scan_map_for_parking(
    lat: float,
    lon: float,
    radius_m: int = 1500,
    existing_lots: Optional[List[Dict[str, Any]]] = None,
    use_live_overpass: bool = True,
) -> Dict[str, Any]:
    """
    Scans map features around (lat, lon) within radius_m for empty grounds,
    mall plazas, and legal public parking areas NOT present in existing_lots.
    """
    existing = existing_lots or []
    scan_source = "live_overpass_osm"

    elements = await _fetch_overpass_candidates(lat, lon, radius_m) if use_live_overpass else None
    if not elements:
        elements = _load_local_fallback_candidates(lat, lon, radius_m)
        scan_source = "osm_local_ai_index"
    else:
        # Merge local DB mall/ground hints to enrich live Overpass scan
        elements.extend(_load_local_fallback_candidates(lat, lon, radius_m))

    discovered: List[Dict[str, Any]] = []
    geojson_features: List[Dict[str, Any]] = []
    seen_coords: List[Tuple[float, float]] = []
    excluded_existing = 0

    for idx, el in enumerate(elements):
        tags = el.get("tags") or {}
        geom_pts = el.get("geometry") or []
        ring_lon_lat: List[List[float]] = []

        if geom_pts and isinstance(geom_pts, list):
            ring_lon_lat = [[float(pt["lon"]), float(pt["lat"])] for pt in geom_pts if "lat" in pt and "lon" in pt]
            if len(ring_lon_lat) >= 3 and ring_lon_lat[0] != ring_lon_lat[-1]:
                ring_lon_lat.append(ring_lon_lat[0])

        center = el.get("center") or {}
        c_lat = float(center.get("lat") or el.get("lat") or 0.0)
        c_lon = float(center.get("lon") or el.get("lon") or 0.0)
        if (c_lat == 0.0 or c_lon == 0.0) and ring_lon_lat:
            c_lat, c_lon = compute_centroid(ring_lon_lat)
        if c_lat == 0.0 and c_lon == 0.0:
            continue

        dist_m = haversine_m(lat, lon, c_lat, c_lon)
        if dist_m > radius_m:
            continue

        area_m2 = compute_polygon_area_m2(ring_lon_lat) if len(ring_lon_lat) >= 3 else 0.0
        default_name = (
            tags.get("name")
            or (f"Open Ground ({round(area_m2)} m²)" if area_m2 > 200 and tags.get("landuse") else None)
            or (f"Public Bay ({round(dist_m)}m away)")
        )

        # Exclude lots already in uploaded OpenPark dataset
        if is_duplicate_of_existing(c_lat, c_lon, default_name, existing):
            excluded_existing += 1
            continue

        # Deduplicate overlapping Overpass/local hits within 55m
        if any(haversine_m(c_lat, c_lon, s_lat, s_lon) < 55.0 for s_lat, s_lon in seen_coords):
            continue

        scored = classify_and_score_candidate(tags, default_name, area_m2, dist_m)
        if not scored:
            continue

        seen_coords.append((c_lat, c_lon))
        item_id = f"ai-{el.get('id', idx)}"
        item = {
            "id": item_id,
            "name": default_name,
            "category": scored["category"],
            "category_label": scored["category_label"],
            "badge": scored["badge"],
            "color": scored["color"],
            "lat": round(c_lat, 6),
            "lon": round(c_lon, 6),
            "distance_km": round(dist_m / 1000.0, 2),
            "eta_mins": max(1, int(round((dist_m / 1000.0) / 0.4))),
            "area_m2": round(area_m2, 1),
            "estimated_spots": scored["estimated_spots"],
            "ai_score": scored["ai_score"],
            "legality_status": scored["legality_status"],
            "surface": scored["surface"],
            "fee": scored["fee"],
            "reason": scored["reason"],
            "has_polygon": len(ring_lon_lat) >= 3,
        }
        discovered.append(item)

        if len(ring_lon_lat) >= 3:
            geojson_features.append({
                "type": "Feature",
                "properties": {
                    "id": item_id,
                    "name": default_name,
                    "category": scored["category"],
                    "color": scored["color"],
                    "ai_score": scored["ai_score"],
                    "estimated_spots": scored["estimated_spots"],
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [ring_lon_lat],
                },
            })

    discovered.sort(key=lambda x: (-x["ai_score"], x["distance_km"]))

    # Diversify top results so malls & empty grounds appear alongside legal street/surface bays
    top_results: List[Dict[str, Any]] = []
    chosen_ids = set()
    for cat_name, quota in (("empty_ground", 8), ("mall_parking", 8), ("legal_bay", 9)):
        bucket = [r for r in discovered if r["category"] == cat_name][:quota]
        for r in bucket:
            top_results.append(r)
            chosen_ids.add(r["id"])
    for r in discovered:
        if len(top_results) >= 25:
            break
        if r["id"] not in chosen_ids:
            top_results.append(r)
            chosen_ids.add(r["id"])

    top_results.sort(key=lambda x: (-x["ai_score"], x["distance_km"]))
    filtered_geojson = [f for f in geojson_features if f["properties"].get("id") in chosen_ids]

    counts = {
        "empty_grounds": sum(1 for r in top_results if r["category"] == "empty_ground"),
        "mall_parkings": sum(1 for r in top_results if r["category"] == "mall_parking"),
        "legal_bays": sum(1 for r in top_results if r["category"] == "legal_bay"),
    }

    return {
        "status": "ok",
        "scan_center": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "scan_source": scan_source,
        "summary": {
            "total_found": len(top_results),
            **counts,
            "excluded_existing": excluded_existing,
            "total_estimated_spots": sum(r["estimated_spots"] for r in top_results),
        },
        "results": top_results,
        "geojson": {
            "type": "FeatureCollection",
            "features": filtered_geojson,
        },
    }
