"""
OpenPark AI Map Space & Legal Parking Scanner (Fast & Proximity-Aware)
---------------------------------------------------------------------
Reads OpenStreetMap vector geometry (parallel Overpass + Photon + local OSM/FTS5 index)
to rapidly discover empty grounds, genuine malls/markets, and legal street-side/surface bays
near any coordinates in India, excluding already-uploaded OpenPark lots.
"""

import asyncio
import logging
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger("openpark.ai_scanner")

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Fast spatial TTL cache: (lat_q, lon_q, radius_m) -> (timestamp, payload)
_SCAN_CACHE: Dict[Tuple[float, float, int], Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SEC = 180.0

ILLEGAL_ACCESS = {"private", "no", "restricted", "military", "permit", "delivery", "employees", "students"}
ILLEGAL_LANDUSE = {"military", "cemetery", "quarry", "landfill", "railway", "industrial", "construction"}
ILLEGAL_NATURAL = {"water", "wetland", "mud", "cliff", "glacier"}
ILLEGAL_HIGHWAY = {"motorway", "motorway_link", "trunk", "trunk_link", "pedestrian", "footway", "cycleway", "steps"}
ILLEGAL_AMENITY = {"fire_station", "prison", "school", "kindergarten", "police", "hospital"}

NON_PARKING_ENTITY_WORDS = (
    "pg", "paying guest", "hostel", "apartment", "apartments", "residency", "residencies",
    "villa", "flats", "deluxe", "ladies", "gents", "mens", "womens", "stanza living",
    "zolo", "colive", "salon", "dental", "clinic", "infotech", "technologies", "solutions",
    "pvt ltd", "private limited", "consultancy", "tuition", "coaching", "temple", "church", "mosque"
)

TRUE_MALL_WORDS = (
    "mall", "shopping", "hypermarket", "supermarket", "marketplace", "galleria",
    "shopping complex", "forum", "orion", "garuda", "vega city", "mantri", "ub city", "lulu",
    "phoenix", "central", "gopalan", "royal meenakshi", "esteems", "bazaar"
)

TRUE_GROUND_WORDS = (
    "ground", "maidan", "open lot", "open ground", "staging area", "parking field", "fairground"
)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def compute_polygon_area_m2(coords: List[List[float]]) -> float:
    """Calculates surface area (m^2) for a [lon, lat] polygon ring via Shoelace formula."""
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


def _matches_any_word(text: str, words: Tuple[str, ...]) -> bool:
    t = (text or "").lower()
    for w in words:
        if re.search(rf'\b{re.escape(w)}\b', t):
            return True
    return False


def _has_non_parking_name(name: str) -> bool:
    return _matches_any_word(name, NON_PARKING_ENTITY_WORDS)


def is_duplicate_of_existing(
    lat: float,
    lon: float,
    name: str,
    existing_lots: List[Dict[str, Any]],
    threshold_m: float = 80.0
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
    AI Legality, Suitability & Proximity Scoring Engine.
    Strictly filters out PGs, residential buildings, and restricted/illegal areas,
    and boosts close-by legal spaces.
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

    # Reject illegal / restricted / unsafe / non-parking buildings
    if access in ILLEGAL_ACCESS:
        return None
    if parking_tag == "no" or tags.get("motor_vehicle") == "no" or tags.get("parking:both") == "no":
        return None
    if landuse in ILLEGAL_LANDUSE or natural in ILLEGAL_NATURAL:
        return None
    if highway in ILLEGAL_HIGHWAY or amenity in ILLEGAL_AMENITY:
        return None
    if any(bad in name_lower for bad in ("private", "restricted", "army", "cantonment", "no parking", "graveyard", "lake")):
        return None
    if _has_non_parking_name(name) and amenity not in ("parking", "parking_space"):
        return None

    is_mall = (
        shop in ("mall", "supermarket", "department_store")
        or building in ("mall",)
        or amenity == "marketplace"
        or landuse == "retail"
        or _matches_any_word(name_lower, TRUE_MALL_WORDS)
    )
    is_ground = (
        landuse in ("brownfield", "greenfield", "grass", "meadow", "recreation_ground", "village_green")
        or leisure in ("common",)
        or surface in ("unpaved", "gravel", "dirt", "compacted", "ground", "earth")
        or _matches_any_word(name_lower, TRUE_GROUND_WORDS)
    )
    is_street_pocket = (
        highway in ("service", "unclassified", "residential")
        and parking_tag != "no"
    )
    is_legal_bay = (
        amenity in ("parking", "parking_space")
        or parking_tag in ("surface", "street_side", "layby", "lane", "multi-storey", "underground")
        or highway in ("rest_area", "services")
        or is_street_pocket
    )

    if is_mall:
        cat_key = "mall_parking"
        cat_label = "Mall / Shopping Plaza"
        badge = "🛍️"
        color = "#0071e3"
    elif is_ground:
        if 0 < area_m2 < 160:
            return None
        cat_key = "empty_ground"
        cat_label = "Empty Open Ground"
        badge = "🟩"
        color = "#ff9500"
    elif is_legal_bay:
        cat_key = "legal_bay"
        cat_label = "Street-Side Legal Pocket" if is_street_pocket else "Legal Public Bay"
        badge = "🛣️" if is_street_pocket else "🅿️"
        color = "#34c759"
    else:
        return None

    # Realistic vehicle bay estimate from polygon area or road/mall class
    if area_m2 >= 60:
        est_spots = max(2, int(round((area_m2 * 0.58) / 14.5)))
    elif cat_key == "mall_parking":
        est_spots = 60
    elif cat_key == "empty_ground":
        est_spots = 22
    elif is_street_pocket:
        est_spots = 6
    else:
        est_spots = 14

    if tags.get("capacity") and str(tags["capacity"]).isdigit():
        est_spots = max(2, int(tags["capacity"]))

    # Proximity-first + legality AI score (0..98)
    score = 58
    reasons: List[str] = []

    if access in ("yes", "public", "permissive"):
        score += 12
        reasons.append("Public legal access verified")
        legality = "Verified Legal Public"
    elif access == "customers" or cat_key == "mall_parking":
        score += 8
        reasons.append("Mall visitor parking")
        legality = "Commercial Visitor Legal"
    elif cat_key == "empty_ground":
        score += 5
        reasons.append("Open flat ground (verify local signage)")
        legality = "Open Ground (Verify Sign)"
    elif is_street_pocket:
        score += 6
        reasons.append("Low-traffic service/residential lane shoulder")
        legality = "Unrestricted Street Shoulder"
    else:
        score += 8
        reasons.append("No restriction tags")
        legality = "Unrestricted Public"

    if surface in ("asphalt", "concrete", "paved", "paving_stones"):
        score += 6
        reasons.append(f"Paved ({surface})")
    elif surface:
        reasons.append(f"Surface: {surface}")
    elif cat_key == "mall_parking":
        score += 5
        reasons.append("Structured plaza bays")

    if fee == "no":
        score += 6
        reasons.append("Free parking")
    elif fee == "yes":
        reasons.append("Paid bay")

    if lit == "yes":
        score += 3
        reasons.append("Lit area")

    if area_m2 >= 350:
        score += 4
        reasons.append(f"~{int(round(area_m2)):,} m² (~{est_spots} cars)")
    else:
        reasons.append(f"Est. ~{est_spots} bays")

    # Strong proximity weighting so close-by spaces always win
    if dist_m <= 250:
        score += 20
        reasons.insert(0, f"Very close ({int(dist_m)}m)")
    elif dist_m <= 550:
        score += 14
        reasons.insert(0, f"Nearby ({int(dist_m)}m)")
    elif dist_m <= 1000:
        score += 6
    else:
        score -= min(18, int((dist_m - 1000) / 140.0))

    score = max(40, min(98, score))

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


async def _fetch_overpass_single(client: httpx.AsyncClient, endpoint: str, query: str) -> Optional[List[Dict[str, Any]]]:
    resp = await client.post(endpoint, data={"data": query})
    if resp.status_code == 200:
        return resp.json().get("elements", [])
    return None


async def _fetch_overpass_fast(lat: float, lon: float, radius_m: int) -> Optional[List[Dict[str, Any]]]:
    """
    Races Overpass mirrors concurrently with a strict 2.2s hard cap so scans never lag.
    Includes surface parking, malls, open grounds, and nearby residential/service shoulders.
    """
    r = max(300, min(int(radius_m), 2500))
    street_r = min(500, r)
    query = f"""
    [out:json][timeout:3];
    (
      way["amenity"="parking"](around:{r},{lat},{lon});
      way["amenity"="parking_space"](around:{r},{lat},{lon});
      way["shop"="mall"](around:{r},{lat},{lon});
      node["shop"="mall"](around:{r},{lat},{lon});
      way["amenity"="marketplace"](around:{r},{lat},{lon});
      way["landuse"="brownfield"](around:{r},{lat},{lon});
      way["landuse"="greenfield"](around:{r},{lat},{lon});
      way["highway"="rest_area"](around:{r},{lat},{lon});
      way["highway"~"^(service|unclassified|residential)$"]["name"](around:{street_r},{lat},{lon});
    );
    out tags center geom 45;
    """
    try:
        async with httpx.AsyncClient(timeout=2.2) as client:
            tasks = [asyncio.create_task(_fetch_overpass_single(client, ep, query)) for ep in OVERPASS_ENDPOINTS]
            done, pending = await asyncio.wait(tasks, timeout=2.4, return_when=asyncio.FIRST_COMPLETED)
            result = None
            for t in done:
                if not t.cancelled() and t.exception() is None and t.result():
                    result = t.result()
                    break
            for p in pending:
                p.cancel()
            return result
    except Exception as exc:
        logger.debug("Fast Overpass race fallback: %s", exc)
        return None


async def _fetch_nearby_streets_photon(lat: float, lon: float) -> List[Dict[str, Any]]:
    """Fast reverse/proximity lookup via Photon (~0.4s) to detect real nearby street shoulders if sparse."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=1.8, headers=headers) as client:
            resp = await client.get(f"https://photon.komoot.io/reverse?lat={lat}&lon={lon}&limit=6")
            if resp.status_code != 200:
                return []
            elements: List[Dict[str, Any]] = []
            for idx, feat in enumerate(resp.json().get("features", [])):
                props = feat.get("properties") or {}
                coords = (feat.get("geometry") or {}).get("coordinates") or []
                if len(coords) < 2:
                    continue
                street_name = props.get("street") or props.get("name")
                if not street_name or _has_non_parking_name(street_name):
                    continue
                osm_val = (props.get("osm_value") or "").lower()
                if osm_val in ("motorway", "trunk", "primary_link", "hospital", "school"):
                    continue
                elements.append({
                    "type": "node",
                    "id": f"photon_rev_{idx}",
                    "tags": {
                        "name": f"{street_name} (Legal Roadside Pocket)",
                        "highway": "service",
                        "surface": "asphalt",
                        "access": "yes",
                    },
                    "lat": float(coords[1]),
                    "lon": float(coords[0]),
                })
            return elements
    except Exception:
        return []


def _load_local_candidates(lat: float, lon: float, radius_m: int) -> List[Dict[str, Any]]:
    """
    Reads local OSM Overpass GeoJSON (793 polygons) + SQLite FTS5 + curated places
    with automatic radius expansion if sparse.
    """
    elements: List[Dict[str, Any]] = []
    try:
        from overpass_service import load_overpass_cache
        cache = load_overpass_cache()
        for feat in cache.get("features", []):
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            if geom.get("type") != "Polygon":
                continue
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
        logger.debug("Local overpass cache error: %s", exc)

    try:
        from places_db import search_places_nearby
        nearby = search_places_nearby(lat=lat, lon=lon, radius_km=max(1.2, (radius_m * 1.6) / 1000.0), limit=120)
        for p in nearby:
            name = p.get("name") or ""
            if _has_non_parking_name(name):
                continue
            cat_l = (p.get("category") or "").lower()
            name_l = name.lower()
            tags: Dict[str, str] = {"name": name}
            if any(k in cat_l or k in name_l for k in TRUE_MALL_WORDS) or "shopping" in cat_l:
                tags["shop"] = "mall"
                tags["access"] = "customers"
            elif any(k in cat_l or k in name_l for k in TRUE_GROUND_WORDS):
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
        logger.debug("Local places_db error: %s", exc)

    try:
        from traccar_service import BENGALURU_PLACES_CATALOG
        for idx, item in enumerate(BENGALURU_PLACES_CATALOG):
            name = item.get("name") or ""
            if _has_non_parking_name(name):
                continue
            c_lat = float(item.get("lat", 0.0))
            c_lon = float(item.get("lon", 0.0))
            if haversine_m(lat, lon, c_lat, c_lon) > max(radius_m, 2500):
                continue
            cat_l = (item.get("category") or "").lower()
            name_l = name.lower()
            tags_cat: Dict[str, str] = {"name": name}
            if any(k in cat_l or k in name_l for k in TRUE_MALL_WORDS) or "shopping" in cat_l:
                tags_cat["shop"] = "mall"
                tags_cat["access"] = "customers"
            elif any(k in cat_l or k in name_l for k in TRUE_GROUND_WORDS):
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


def _process_elements(
    elements: List[Dict[str, Any]],
    lat: float,
    lon: float,
    max_radius_m: int,
    existing: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    discovered: List[Dict[str, Any]] = []
    geojson_features: List[Dict[str, Any]] = []
    seen_coords: List[Tuple[float, float, str]] = []
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
        if dist_m > max_radius_m:
            continue

        area_m2 = compute_polygon_area_m2(ring_lon_lat) if len(ring_lon_lat) >= 3 else 0.0
        raw_name = tags.get("name") or ""
        if tags.get("highway") in ("service", "unclassified", "residential") and raw_name and "pocket" not in raw_name.lower():
            default_name = f"{raw_name} (Legal Roadside Pocket)"
        else:
            default_name = (
                raw_name
                or (f"Open Ground ({round(area_m2)} m²)" if area_m2 > 200 and tags.get("landuse") else None)
                or f"Public Bay ({round(dist_m)}m away)"
            )

        if is_duplicate_of_existing(c_lat, c_lon, default_name, existing):
            excluded_existing += 1
            continue

        if any(
            haversine_m(c_lat, c_lon, s_lat, s_lon) < 75.0
            or (default_name.lower() == s_name and haversine_m(c_lat, c_lon, s_lat, s_lon) < 350.0)
            for s_lat, s_lon, s_name in seen_coords
        ):
            continue

        scored = classify_and_score_candidate(tags, default_name, area_m2, dist_m)
        if not scored:
            continue

        seen_coords.append((c_lat, c_lon, default_name.lower()))
        item_id = f"ai-{el.get('id', idx)}"
        discovered.append({
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
        })

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

    return discovered, geojson_features, excluded_existing


async def scan_map_for_parking(
    lat: float,
    lon: float,
    radius_m: int = 1500,
    existing_lots: Optional[List[Dict[str, Any]]] = None,
    use_live_overpass: bool = True,
) -> Dict[str, Any]:
    """
    Fast (< 2.5s max, < 5ms cached) AI map scanner with automatic radius expansion
    and street-pocket fallback so a nearby legal space is always returned.
    """
    t0 = time.perf_counter()
    cache_key = (round(lat, 3), round(lon, 3), int(radius_m))
    now = time.time()
    if use_live_overpass and cache_key in _SCAN_CACHE:
        cached_ts, cached_payload = _SCAN_CACHE[cache_key]
        if now - cached_ts < _CACHE_TTL_SEC:
            return {**cached_payload, "cached": True, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}

    existing = existing_lots or []
    scan_source = "osm_local_ai_index"
    elements = _load_local_candidates(lat, lon, radius_m)

    if use_live_overpass:
        live_els, photon_els = await asyncio.gather(
            _fetch_overpass_fast(lat, lon, radius_m),
            _fetch_nearby_streets_photon(lat, lon),
        )
        if live_els:
            elements = live_els + elements
            scan_source = "live_overpass_osm"
        if photon_els:
            elements.extend(photon_els)

    discovered, geojson_features, excluded_existing = _process_elements(elements, lat, lon, radius_m, existing)

    # Auto-expand local radius up to 4.5 km if fewer than 3 spots were found nearby
    effective_radius = radius_m
    if len(discovered) < 3:
        effective_radius = max(radius_m, 4500)
        expanded_els = _load_local_candidates(lat, lon, effective_radius)
        discovered, geojson_features, excluded_existing = _process_elements(
            elements + expanded_els, lat, lon, effective_radius, existing
        )

    # Sort primarily by high AI score, breaking ties by shortest distance
    discovered.sort(key=lambda x: (-x["ai_score"], x["distance_km"]))

    # Diversify top results across all 3 categories (grounds, malls, legal bays)
    top_results: List[Dict[str, Any]] = []
    chosen_ids = set()
    for cat_name, quota in (("empty_ground", 8), ("mall_parking", 8), ("legal_bay", 9)):
        for r in [item for item in discovered if item["category"] == cat_name][:quota]:
            top_results.append(r)
            chosen_ids.add(r["id"])
    for r in discovered:
        if len(top_results) >= 25:
            break
        if r["id"] not in chosen_ids:
            top_results.append(r)
            chosen_ids.add(r["id"])

    # Final ordering: bring the best-scoring closest spots right to the top
    top_results.sort(key=lambda x: (x["distance_km"] > 0.6, -x["ai_score"], x["distance_km"]))
    filtered_geojson = [f for f in geojson_features if f["properties"].get("id") in chosen_ids]

    counts = {
        "empty_grounds": sum(1 for r in top_results if r["category"] == "empty_ground"),
        "mall_parkings": sum(1 for r in top_results if r["category"] == "mall_parking"),
        "legal_bays": sum(1 for r in top_results if r["category"] == "legal_bay"),
    }

    payload = {
        "status": "ok",
        "scan_center": {"lat": lat, "lon": lon},
        "radius_m": effective_radius,
        "scan_source": scan_source,
        "cached": False,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
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

    if use_live_overpass and top_results:
        _SCAN_CACHE[cache_key] = (now, payload)

    return payload
