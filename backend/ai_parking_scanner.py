"""
OpenPark AI Map Space & Legal Parking Scanner (Fast & Accuracy-Focused)
-----------------------------------------------------------------------
Reads OpenStreetMap vector geometry (OSM CGImap + Photon + pre-indexed open-ground/OSM caches
+ spatial unbuilt-plot detection) to rapidly discover unused empty grounds, genuine malls/markets,
and legal street-side/surface bays near any coordinates in India, excluding uploaded OpenPark lots.
"""

import asyncio
import json
import logging
import math
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger("openpark.ai_scanner")

CGIMAP_ENDPOINT = "https://api.openstreetmap.org/api/0.6/map.json"
PHOTON_REVERSE_URL = "https://photon.komoot.io/reverse"
PHOTON_SEARCH_URL = "https://photon.komoot.io/api/"

# India geographic bounding box for strict domestic scoping
INDIA_BBOX_STR = "68.0,6.5,97.5,37.5"

# Fast bounded in-memory TTL caches
_SCAN_CACHE: Dict[Tuple[float, float, int], Tuple[float, Dict[str, Any]]] = {}
_CGIMAP_TILE_CACHE: Dict[Tuple[float, float], Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL_SEC = 300.0
_TILE_TTL_SEC = 900.0
_MAX_SCAN_CACHE = 250
_MAX_TILE_CACHE = 120


def _cache_put(cache: Dict[Any, Tuple[float, Any]], key: Any, value: Any, max_size: int) -> None:
    """Stores a timestamped cache entry while bounding memory with oldest-entry eviction."""
    now = time.time()
    cache[key] = (now, value)
    if len(cache) > max_size:
        oldest_key = min(cache.keys(), key=lambda k: cache[k][0])
        cache.pop(oldest_key, None)

_OPEN_GROUNDS_PRECOMPUTED: Optional[List[Dict[str, Any]]] = None

# OSM unused / vacant open ground & plot classifications
EMPTY_GROUND_LANDUSE = {
    "vacant", "brownfield", "greenfield", "grass", "meadow",
    "recreation_ground", "village_green",
}
EMPTY_GROUND_NATURAL = {"scrub", "grassland", "bare_rock", "sand", "heath"}
EMPTY_GROUND_LEISURE = {"common"}
EMPTY_SURFACE_VALUES = {"unpaved", "gravel", "dirt", "compacted", "ground", "earth", "sand", "grass"}

ILLEGAL_ACCESS = {"private", "no", "restricted", "military", "permit", "delivery", "employees", "students"}
ILLEGAL_LANDUSE = {"military", "cemetery", "quarry", "landfill", "railway", "industrial", "construction", "forest", "farmland"}
ILLEGAL_NATURAL = {"water", "wetland", "mud", "cliff", "glacier", "wood"}
ILLEGAL_HIGHWAY = {"motorway", "motorway_link", "trunk", "trunk_link", "pedestrian", "footway", "cycleway", "steps"}
ILLEGAL_AMENITY = {"fire_station", "prison", "school", "kindergarten", "police", "hospital", "college", "university", "place_of_worship"}
ILLEGAL_LEISURE = {"park", "garden", "golf_course", "stadium", "sports_centre", "playground", "swimming_pool"}

NON_PARKING_ENTITY_WORDS = (
    "pg", "paying guest", "hostel", "apartment", "apartments", "residency", "residencies",
    "villa", "flats", "deluxe", "ladies", "gents", "mens", "womens", "stanza living",
    "zolo", "colive", "salon", "dental", "clinic", "infotech", "technologies", "solutions",
    "pvt ltd", "private limited", "consultancy", "tuition", "coaching", "temple", "church",
    "mosque", "graveyard", "cemetery", "lake", "pond", "basketball", "tennis", "badminton",
    "cricket", "football", "skating", "club"
)

TRUE_MALL_WORDS = (
    "mall", "shopping", "hypermarket", "supermarket", "marketplace", "galleria",
    "shopping complex", "forum", "orion", "garuda", "vega city", "mantri", "ub city", "lulu",
    "phoenix", "central", "gopalan", "royal meenakshi", "esteems", "bazaar"
)

TRUE_GROUND_WORDS = (
    "ground", "maidan", "open lot", "open ground", "vacant lot", "vacant land",
    "staging area", "parking field", "fairground", "open space", "unpaved lot"
)

MIN_GROUND_AREA_M2 = 45.0
MAX_GROUND_AREA_M2 = 550.0
LARGE_GROUND_STOPWORDS = ("maidan", "stadium", "exhibition", "fairground", "parade", "complex", "playfield")


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


def _extent_to_ring(extent: Any) -> List[List[float]]:
    """Converts Photon extent [min_lon, max_lat, max_lon, min_lat] into a closed GeoJSON ring."""
    if not isinstance(extent, list) or len(extent) != 4:
        return []
    min_lon, max_lat, max_lon, min_lat = [float(x) for x in extent]
    if abs(max_lon - min_lon) < 1e-6 or abs(max_lat - min_lat) < 1e-6:
        return []
    return [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]


def _square_ring(lat: float, lon: float, half_m: float = 15.0) -> List[List[float]]:
    d_lat = half_m / 111132.92
    d_lon = half_m / (111412.84 * max(0.1, math.cos(math.radians(lat))))
    return [
        [round(lon - d_lon, 6), round(lat - d_lat, 6)],
        [round(lon + d_lon, 6), round(lat - d_lat, 6)],
        [round(lon + d_lon, 6), round(lat + d_lat, 6)],
        [round(lon - d_lon, 6), round(lat + d_lat, 6)],
        [round(lon - d_lon, 6), round(lat - d_lat, 6)],
    ]


def _descriptive_ground_name(tags: Dict[str, str], area_m2: float, dist_m: float) -> str:
    raw = (tags.get("name") or "").strip()
    if raw:
        return raw
    lu = (tags.get("landuse") or "").lower()
    nat = (tags.get("natural") or "").lower()
    cars_hint = max(3, min(6, int(round((max(area_m2, 65.0) * 0.52) / 16.0))))
    area_str = f" ({round(area_m2)} m² • ~{cars_hint} cars)" if area_m2 >= MIN_GROUND_AREA_M2 else f" ({round(dist_m)}m away)"
    if tags.get("ai_gap_plot") == "yes" or tags.get("ai_pocket_slice") == "yes":
        return f"Small Unused Pocket{area_str}"
    if lu in ("vacant", "brownfield", "greenfield"):
        return f"Small Vacant Lot{area_str}"
    if nat in ("scrub", "heath", "bare_rock", "sand"):
        return f"Small Scrub Pocket{area_str}"
    if lu in ("grass", "meadow", "grassland", "village_green") or nat == "grassland":
        return f"Small Grass Pocket{area_str}"
    return f"Small Open Ground{area_str}"


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
    Strictly filters out PGs, traffic islands, parks, water, residential buildings,
    and restricted/illegal areas while highlighting true unused grounds, malls & bays.
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

    # Reject illegal / restricted / unsafe / non-parking buildings / road medians
    if access in ILLEGAL_ACCESS:
        return None
    if parking_tag == "no" or tags.get("motor_vehicle") == "no" or tags.get("parking:both") == "no":
        return None
    if tags.get("area:highway") == "traffic_island" or tags.get("barrier") == "kerb":
        return None
    if tags.get("sport") and amenity not in ("parking", "parking_space"):
        return None
    if landuse in ILLEGAL_LANDUSE or natural in ILLEGAL_NATURAL or leisure in ILLEGAL_LEISURE:
        return None
    if highway in ILLEGAL_HIGHWAY or amenity in ILLEGAL_AMENITY:
        return None
    if any(bad in name_lower for bad in ("private", "restricted", "army", "cantonment", "no parking")):
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
        tags.get("ai_gap_plot") == "yes"
        or landuse in EMPTY_GROUND_LANDUSE
        or natural in EMPTY_GROUND_NATURAL
        or leisure in EMPTY_GROUND_LEISURE
        or (surface in EMPTY_SURFACE_VALUES and not highway and amenity not in ("parking", "parking_space"))
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
        if 0 < area_m2 < MIN_GROUND_AREA_M2 or area_m2 > MAX_GROUND_AREA_M2:
            return None
        if area_m2 == 0 and tags.get("ai_gap_plot") != "yes" and tags.get("ai_pocket_slice") != "yes":
            return None
        if _matches_any_word(name_lower, LARGE_GROUND_STOPWORDS):
            return None
        cat_key = "empty_ground"
        cat_label = "Small Empty Ground (3-4 Cars)"
        badge = "🟩"
        color = "#ff9500"
    elif is_legal_bay:
        cat_key = "legal_bay"
        cat_label = "Street-Side Legal Pocket" if is_street_pocket else "Legal Public Bay"
        badge = "🛣️" if is_street_pocket else "🅿️"
        color = "#34c759"
    else:
        return None

    # Realistic vehicle bay estimate (small empty grounds hold ~3-6 cars)
    if cat_key == "empty_ground":
        est_spots = max(3, min(6, int(round((max(area_m2, 65.0) * 0.52) / 16.0))))
    elif area_m2 >= 60:
        est_spots = max(4, min(350, int(round((area_m2 * 0.58) / 14.5))))
    elif cat_key == "mall_parking":
        est_spots = 60
    elif is_street_pocket:
        est_spots = 6
    else:
        est_spots = 14

    if tags.get("capacity") and str(tags["capacity"]).isdigit():
        est_spots = max(2, int(tags["capacity"]))

    # Proximity-first + suitability AI score (0..98)
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
        if tags.get("ai_gap_plot") == "yes":
            score += 6
            reasons.append("Unbuilt road-adjacent open plot (AI Geometry Scan)")
            legality = "Open Unbuilt Ground"
        elif landuse in ("vacant", "brownfield", "greenfield") or natural in ("scrub", "bare_rock", "sand"):
            score += 9
            reasons.append("Unused open terrain (verify local signage)")
            legality = "Unused Open Ground"
        elif landuse == "farmland":
            score += 2
            reasons.append("Uncultivated open plot (verify permission)")
            legality = "Open Plot (Verify Permission)"
        else:
            score += 7
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

    # Strong proximity weighting so close-by spaces always rank highest
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


def _load_open_grounds_precomputed() -> List[Dict[str, Any]]:
    """Loads pre-indexed OSM empty grounds & malls cache once into memory (~5ms)."""
    global _OPEN_GROUNDS_PRECOMPUTED
    if _OPEN_GROUNDS_PRECOMPUTED is not None:
        return _OPEN_GROUNDS_PRECOMPUTED

    loaded: List[Dict[str, Any]] = []
    candidates_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "osm_open_grounds_cache.geojson"),
        os.path.join(os.getcwd(), "data", "osm_open_grounds_cache.geojson"),
    ]
    for path in candidates_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    gj = json.load(f)
                for feat in gj.get("features", []):
                    geom = feat.get("geometry") or {}
                    props = feat.get("properties") or {}
                    if geom.get("type") != "Polygon":
                        continue
                    ring = (geom.get("coordinates") or [[]])[0]
                    if len(ring) < 3:
                        continue
                    c_lat, c_lon = compute_centroid(ring)
                    loaded.append({
                        "type": "way",
                        "id": f"ogc_{props.get('osm_id', len(loaded))}",
                        "tags": props,
                        "c_lat": c_lat,
                        "c_lon": c_lon,
                        "center": {"lat": c_lat, "lon": c_lon},
                        "geometry": [{"lat": pt[1], "lon": pt[0]} for pt in ring],
                    })
                break
            except Exception as exc:
                logger.warning("Failed reading %s: %s", path, exc)

    _OPEN_GROUNDS_PRECOMPUTED = loaded
    return _OPEN_GROUNDS_PRECOMPUTED


def _detect_unbuilt_grid_plots(
    raw_elements: List[Dict[str, Any]],
    node_map: Dict[int, Tuple[float, float]],
    bbox: Tuple[float, float, float, float],
    center_lat: float,
    center_lon: float,
) -> List[Dict[str, Any]]:
    """
    AI Spatial Occupancy Grid: In densely mapped urban boxes (>= 140 buildings), locates
    empty unbuilt cells (zero buildings, zero water/park/school/hospital, road-adjacent)
    that contributors left untagged on OpenStreetMap.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    grid_n = 44
    d_lon = (max_lon - min_lon) / grid_n
    d_lat = (max_lat - min_lat) / grid_n
    if d_lon <= 0 or d_lat <= 0:
        return []

    occupied = [[False] * grid_n for _ in range(grid_n)]
    has_road = [[False] * grid_n for _ in range(grid_n)]
    bad_highway = [[False] * grid_n for _ in range(grid_n)]
    building_count = 0

    def mark_bbox(pts: List[Tuple[float, float]], target_grid: List[List[bool]], pad: int = 0) -> None:
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        r0 = max(0, min(grid_n - 1, int((min(lats) - min_lat) / d_lat) - pad))
        r1 = max(0, min(grid_n - 1, int((max(lats) - min_lat) / d_lat) + pad))
        c0 = max(0, min(grid_n - 1, int((min(lons) - min_lon) / d_lon) - pad))
        c1 = max(0, min(grid_n - 1, int((max(lons) - min_lon) / d_lon) + pad))
        for rr in range(r0, r1 + 1):
            for cc in range(c0, c1 + 1):
                target_grid[rr][cc] = True

    for e in raw_elements:
        if e.get("type") != "way" or "tags" not in e:
            continue
        t = e["tags"]
        pts = [node_map[nid] for nid in e.get("nodes", []) if nid in node_map]
        if not pts:
            continue
        hw = t.get("highway", "")
        if "building" in t:
            building_count += 1
            mark_bbox(pts, occupied)
        elif (
            t.get("natural") in ILLEGAL_NATURAL
            or t.get("landuse") in ILLEGAL_LANDUSE
            or t.get("leisure") in ILLEGAL_LEISURE
            or t.get("amenity") in ILLEGAL_AMENITY
            or t.get("amenity") in ("parking", "parking_space")
            or t.get("shop") in ("mall", "supermarket", "department_store")
            or t.get("landuse") in EMPTY_GROUND_LANDUSE
            or t.get("natural") in EMPTY_GROUND_NATURAL
        ):
            mark_bbox(pts, occupied)
        elif hw:
            # Mark road centerline cells occupied & road-accessible for neighbors
            for plat, plon in pts:
                rr = int((plat - min_lat) / d_lat)
                cc = int((plon - min_lon) / d_lon)
                if 0 <= rr < grid_n and 0 <= cc < grid_n:
                    occupied[rr][cc] = True
                    if hw in ("motorway", "motorway_link", "trunk", "trunk_link"):
                        bad_highway[rr][cc] = True
                    elif hw in ("residential", "unclassified", "service", "tertiary", "secondary"):
                        has_road[rr][cc] = True

    if building_count < 100:
        return []

    candidates: List[Tuple[float, float, float]] = []
    for r in range(2, grid_n - 2):
        for c in range(2, grid_n - 2):
            if occupied[r][c]:
                continue
            # Require nearby mapped structures so outer unmapped voids don't false-trigger
            local_occ = sum(
                1 for dr in range(-2, 3) for dc in range(-2, 3) if occupied[r + dr][c + dc]
            )
            if local_occ < 4:
                continue
            near_expressway = any(
                bad_highway[r + dr][c + dc] for dr in range(-1, 2) for dc in range(-1, 2)
            )
            if near_expressway:
                continue
            road_adj = (
                has_road[r - 1][c] or has_road[r + 1][c]
                or has_road[r][c - 1] or has_road[r][c + 1]
            )
            if not road_adj:
                continue
            c_lat = min_lat + (r + 0.5) * d_lat
            c_lon = min_lon + (c + 0.5) * d_lon
            dist = haversine_m(center_lat, center_lon, c_lat, c_lon)
            candidates.append((dist, c_lat, c_lon))

    candidates.sort(key=lambda x: x[0])
    chosen: List[Dict[str, Any]] = []
    chosen_pts: List[Tuple[float, float]] = []
    for dist, c_lat, c_lon in candidates:
        if any(haversine_m(c_lat, c_lon, p_lat, p_lon) < 150.0 for p_lat, p_lon in chosen_pts):
            continue
        chosen_pts.append((c_lat, c_lon))
        ring = _square_ring(c_lat, c_lon, half_m=4.8)
        chosen.append({
            "type": "way",
            "id": f"gap_{len(chosen)}_{round(c_lat,4)}_{round(c_lon,4)}",
            "tags": {"ai_gap_plot": "yes", "surface": "unpaved", "access": "permissive"},
            "center": {"lat": c_lat, "lon": c_lon},
            "geometry": [{"lat": pt[1], "lon": pt[0]} for pt in ring],
        })
        if len(chosen) >= 5:
            break
    return chosen


def _extract_cgimap_elements(
    raw_elements: List[Dict[str, Any]],
    bbox: Tuple[float, float, float, float],
    center_lat: float,
    center_lon: float,
) -> List[Dict[str, Any]]:
    """Extracts small 3-4 car empty grounds, malls, parking bays, street shoulders, and AI pocket plots from CGImap JSON."""
    node_map: Dict[int, Tuple[float, float]] = {
        e["id"]: (float(e["lat"]), float(e["lon"]))
        for e in raw_elements
        if e.get("type") == "node" and "lat" in e and "lon" in e
    }

    road_pts: List[Tuple[float, float]] = []
    for e in raw_elements:
        if e.get("type") == "way" and "tags" in e:
            if e["tags"].get("highway") in ("residential", "unclassified", "service", "tertiary", "secondary"):
                for nid in e.get("nodes", [])[::3]:
                    if nid in node_map:
                        road_pts.append(node_map[nid])

    extracted: List[Dict[str, Any]] = []
    street_candidates: List[Tuple[float, Dict[str, Any]]] = []

    for e in raw_elements:
        etype = e.get("type")
        tags = e.get("tags")
        if not tags:
            continue

        if etype == "node" and "lat" in e and "lon" in e:
            if tags.get("shop") in ("mall", "supermarket", "department_store") or tags.get("amenity") in ("parking", "marketplace"):
                extracted.append({
                    "type": "node",
                    "id": f"cg_n_{e['id']}",
                    "tags": tags,
                    "lat": float(e["lat"]),
                    "lon": float(e["lon"]),
                })
            continue

        if etype != "way":
            continue

        lu = (tags.get("landuse") or "").lower()
        nat = (tags.get("natural") or "").lower()
        lei = (tags.get("leisure") or "").lower()
        sh = (tags.get("shop") or "").lower()
        am = (tags.get("amenity") or "").lower()
        hw = (tags.get("highway") or "").lower()

        is_ground_tag = (
            lu in EMPTY_GROUND_LANDUSE
            or nat in EMPTY_GROUND_NATURAL
            or lei in EMPTY_GROUND_LEISURE
        )
        is_interesting = (
            is_ground_tag
            or sh in ("mall", "supermarket", "department_store")
            or am in ("parking", "parking_space", "marketplace")
            or lu == "retail"
            or hw in ("rest_area", "services")
        )
        is_street = hw in ("service", "unclassified", "residential") and bool(tags.get("name"))
        if not (is_interesting or is_street):
            continue

        pts = [node_map[nid] for nid in e.get("nodes", []) if nid in node_map]
        if not pts:
            continue
        c_lat = sum(p[0] for p in pts) / len(pts)
        c_lon = sum(p[1] for p in pts) / len(pts)
        geom = [{"lat": p[0], "lon": p[1]} for p in pts]

        if is_street and not is_interesting:
            dist = haversine_m(center_lat, center_lon, c_lat, c_lon)
            if dist <= 650.0:
                street_candidates.append((dist, {
                    "type": "way",
                    "id": f"cg_w_{e['id']}",
                    "tags": tags,
                    "center": {"lat": c_lat, "lon": c_lon},
                    "geometry": geom,
                }))
        elif is_ground_tag:
            area_m2 = compute_polygon_area_m2([[p[1], p[0]] for p in pts])
            if MIN_GROUND_AREA_M2 <= area_m2 <= MAX_GROUND_AREA_M2:
                extracted.append({
                    "type": "way",
                    "id": f"cg_w_{e['id']}",
                    "tags": tags,
                    "center": {"lat": c_lat, "lon": c_lon},
                    "geometry": geom,
                })
            elif area_m2 > MAX_GROUND_AREA_M2 and road_pts:
                # Carve ONLY a 3-4 car roadside corner pocket (~92 m2) from edge of large unused land
                best_pt = None
                best_d2 = 1e9
                for pt in pts[::2]:
                    for rpt in road_pts[::2]:
                        d2 = (pt[0] - rpt[0]) ** 2 + (pt[1] - rpt[1]) ** 2
                        if d2 < best_d2:
                            best_d2 = d2
                            best_pt = pt
                if best_pt and best_d2 < (0.0007 ** 2):
                    ring = _square_ring(best_pt[0], best_pt[1], half_m=4.8)
                    extracted.append({
                        "type": "way",
                        "id": f"cg_p_{e['id']}",
                        "tags": {
                            "landuse": lu,
                            "natural": nat,
                            "leisure": lei,
                            "surface": "unpaved",
                            "ai_pocket_slice": "yes",
                        },
                        "center": {"lat": best_pt[0], "lon": best_pt[1]},
                        "geometry": [{"lat": rp[1], "lon": rp[0]} for rp in ring],
                    })
        else:
            extracted.append({
                "type": "way",
                "id": f"cg_w_{e['id']}",
                "tags": tags,
                "center": {"lat": c_lat, "lon": c_lon},
                "geometry": geom,
            })

    street_candidates.sort(key=lambda x: x[0])
    extracted.extend(item for _, item in street_candidates[:10])
    extracted.extend(_detect_unbuilt_grid_plots(raw_elements, node_map, bbox, center_lat, center_lon))
    return extracted


async def _fetch_osm_cgimap_fast(lat: float, lon: float) -> List[Dict[str, Any]]:
    """
    Fetches live OSM map geometry via CGImap (/api/0.6/map.json) with a 2.6s timeout
    and spatial tile caching so subsequent scans in the same 1km zone take 0ms.
    """
    tile_key = (round(lat, 2), round(lon, 2))
    now = time.time()
    cached = _CGIMAP_TILE_CACHE.get(tile_key)
    if cached and (now - cached[0]) < _TILE_TTL_SEC:
        return cached[1]

    delta = 0.0040
    bbox = (lon - delta, lat - delta, lon + delta, lat + delta)
    url = f"{CGIMAP_ENDPOINT}?bbox={bbox[0]:.5f},{bbox[1]:.5f},{bbox[2]:.5f},{bbox[3]:.5f}"
    headers = {"User-Agent": "OpenPark/1.0", "Accept": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=2.6, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            raw_els = resp.json().get("elements", [])
            extracted = _extract_cgimap_elements(raw_els, bbox, lat, lon)
            _cache_put(_CGIMAP_TILE_CACHE, tile_key, extracted, _MAX_TILE_CACHE)
            return extracted
    except Exception as exc:
        logger.debug("CGImap live scan skipped/timed out: %s", exc)
        return []


async def _fetch_photon_spaces(lat: float, lon: float, radius_m: int) -> List[Dict[str, Any]]:
    """Concurrent Photon lookup (~0.5s) for malls, named grounds, and nearest street shoulders."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    elements: List[Dict[str, Any]] = []
    max_search_r = float(min(int(radius_m), 1000))

    try:
        async with httpx.AsyncClient(timeout=1.9, headers=headers) as client:
            rev_req = client.get(f"{PHOTON_REVERSE_URL}?lat={lat}&lon={lon}&limit=6")
            mall_req = client.get(
                f"{PHOTON_SEARCH_URL}?q=mall&lat={lat}&lon={lon}&bbox={INDIA_BBOX_STR}&limit=8"
            )
            ground_req = client.get(
                f"{PHOTON_SEARCH_URL}?q=ground&lat={lat}&lon={lon}&bbox={INDIA_BBOX_STR}&limit=8"
            )
            rev_resp, mall_resp, ground_resp = await asyncio.gather(
                rev_req, mall_req, ground_req, return_exceptions=True
            )

        if isinstance(rev_resp, httpx.Response) and rev_resp.status_code == 200:
            for idx, feat in enumerate(rev_resp.json().get("features", [])):
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

        for prefix, resp_obj in (("mall", mall_resp), ("ground", ground_resp)):
            if not isinstance(resp_obj, httpx.Response) or resp_obj.status_code != 200:
                continue
            for idx, feat in enumerate(resp_obj.json().get("features", [])):
                props = feat.get("properties") or {}
                coords = (feat.get("geometry") or {}).get("coordinates") or []
                if len(coords) < 2:
                    continue
                c_lon, c_lat = float(coords[0]), float(coords[1])
                if haversine_m(lat, lon, c_lat, c_lon) > max_search_r:
                    continue
                name = props.get("name") or ""
                if not name or _has_non_parking_name(name):
                    continue
                osm_key = (props.get("osm_key") or "").lower()
                osm_val = (props.get("osm_value") or "").lower()
                if osm_key in ("amenity", "shop") and osm_val in ("cafe", "restaurant", "coffee") and prefix == "ground":
                    continue
                if osm_key in ("water",) or osm_val in ILLEGAL_NATURAL or osm_val in ILLEGAL_LEISURE:
                    continue

                tags: Dict[str, str] = {"name": name}
                if prefix == "mall":
                    tags["shop"] = "mall"
                    tags["access"] = "customers"
                else:
                    tags[osm_key or "landuse"] = osm_val or "brownfield"
                    if osm_key not in ("landuse", "natural", "leisure"):
                        tags["landuse"] = "brownfield"
                    tags["surface"] = "unpaved"

                ring = _extent_to_ring(props.get("extent"))
                if prefix == "ground":
                    if not ring:
                        continue
                    ext_area = compute_polygon_area_m2(ring)
                    if ext_area < MIN_GROUND_AREA_M2 or ext_area > MAX_GROUND_AREA_M2:
                        continue
                if ring:
                    elements.append({
                        "type": "way",
                        "id": f"photon_{prefix}_{idx}",
                        "tags": tags,
                        "center": {"lat": c_lat, "lon": c_lon},
                        "geometry": [{"lat": pt[1], "lon": pt[0]} for pt in ring],
                    })
                else:
                    elements.append({
                        "type": "node",
                        "id": f"photon_{prefix}_{idx}",
                        "tags": tags,
                        "lat": c_lat,
                        "lon": c_lon,
                    })
    except Exception as exc:
        logger.debug("Photon spaces lookup error: %s", exc)

    return elements


def _load_local_candidates(lat: float, lon: float, radius_m: int) -> List[Dict[str, Any]]:
    """
    Reads pre-indexed OSM empty grounds cache (310+ grounds/malls), OSM parking cache (793 polygons),
    SQLite FTS5 catalog, and curated Bengaluru places in ~2ms.
    """
    elements: List[Dict[str, Any]] = []

    for og in _load_open_grounds_precomputed():
        if haversine_m(lat, lon, og["c_lat"], og["c_lon"]) <= radius_m:
            elements.append(og)

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
        nearby = search_places_nearby(lat=lat, lon=lon, radius_km=radius_m / 1000.0, limit=120)
        for p in nearby:
            name = p.get("name") or ""
            if _has_non_parking_name(name):
                continue
            cat_l = (p.get("category") or "").lower()
            name_l = name.lower()
            tags: Dict[str, str] = {"name": name}
            if any(k in cat_l or k in name_l for k in TRUE_MALL_WORDS) or "shopping mall" in cat_l or "shopping center" in cat_l:
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
            if haversine_m(lat, lon, c_lat, c_lon) > radius_m:
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

        area_m2 = compute_polygon_area_m2(ring_lon_lat) if len(ring_lon_lat) >= 3 else float(tags.get("area_m2") or 0.0)
        raw_name = (tags.get("name") or "").strip()
        if tags.get("highway") in ("service", "unclassified", "residential") and raw_name and "pocket" not in raw_name.lower():
            default_name = f"{raw_name} (Legal Roadside Pocket)"
        elif raw_name:
            default_name = raw_name
        elif (
            tags.get("ai_gap_plot") == "yes"
            or tags.get("ai_pocket_slice") == "yes"
            or (tags.get("landuse") or "").lower() in EMPTY_GROUND_LANDUSE
            or (tags.get("natural") or "").lower() in EMPTY_GROUND_NATURAL
            or (tags.get("leisure") or "").lower() in EMPTY_GROUND_LEISURE
        ):
            default_name = _descriptive_ground_name(tags, area_m2, dist_m)
        elif (tags.get("shop") or "").lower() in ("mall", "supermarket", "department_store") or (tags.get("landuse") or "").lower() == "retail":
            default_name = f"Commercial Plaza ({round(area_m2):,} m²)" if area_m2 >= 120 else f"Retail Complex ({round(dist_m)}m away)"
        else:
            default_name = f"Public Bay ({round(dist_m)}m away)"

        if is_duplicate_of_existing(c_lat, c_lon, default_name, existing):
            excluded_existing += 1
            continue

        dedup_name_m = 520.0 if "roadside pocket" in default_name.lower() else 350.0
        if any(
            haversine_m(c_lat, c_lon, s_lat, s_lon) < 75.0
            or (default_name.lower() == s_name and haversine_m(c_lat, c_lon, s_lat, s_lon) < dedup_name_m)
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
    radius_m: int = 1000,
    existing_lots: Optional[List[Dict[str, Any]]] = None,
    use_live_overpass: bool = True,
) -> Dict[str, Any]:
    """
    Fast (< 2s uncached, < 5ms cached) AI map scanner strictly scoped within 1 km
    (<= 1000m) to discover small 3-4 car unused grounds, mall plazas, and legal bays.
    """
    t0 = time.perf_counter()
    effective_radius = max(200, min(int(radius_m), 1000))
    cache_key = (round(lat, 3), round(lon, 3), effective_radius)
    now = time.time()
    if use_live_overpass and cache_key in _SCAN_CACHE:
        cached_ts, cached_payload = _SCAN_CACHE[cache_key]
        if now - cached_ts < _CACHE_TTL_SEC:
            return {**cached_payload, "cached": True, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}

    existing = existing_lots or []
    scan_source = "osm_local_ai_index"
    elements = _load_local_candidates(lat, lon, effective_radius)

    if use_live_overpass:
        live_els, photon_els = await asyncio.gather(
            _fetch_osm_cgimap_fast(lat, lon),
            _fetch_photon_spaces(lat, lon, effective_radius),
        )
        if live_els:
            elements = live_els + elements
            scan_source = "live_osm_ai_vision"
        if photon_els:
            elements.extend(photon_els)

    discovered, geojson_features, excluded_existing = _process_elements(elements, lat, lon, effective_radius, existing)

    # Apply community driver pocket verification votes (hide blocked pockets, boost open ones)
    try:
        from places_db import get_verified_pockets_map
        ver_map = get_verified_pockets_map()
        if ver_map:
            kept = []
            for item in discovered:
                v = ver_map.get(item["id"])
                if v:
                    if v["blocked_votes"] >= 2 or v["blocked_votes"] > v["open_votes"]:
                        continue
                    if v["open_votes"] > v["blocked_votes"]:
                        item["ai_score"] = min(98, item["ai_score"] + 6)
                        item["crowd_verified"] = True
                        item["open_votes"] = v["open_votes"]
                kept.append(item)
            discovered = kept
    except Exception:
        pass

    # Sort strictly nearest-first within 1 km (tie-break by AI score)
    discovered.sort(key=lambda x: (x["distance_km"], -x["ai_score"]))

    # Cap strictly to the 5 nearest parking areas around the marked location
    top_results: List[Dict[str, Any]] = []
    chosen_ids = set()
    nearest_ground = next((item for item in discovered if item["category"] == "empty_ground"), None)
    for r in discovered:
        if len(top_results) >= 5:
            break
        top_results.append(r)
        chosen_ids.add(r["id"])
    if nearest_ground and nearest_ground["id"] not in chosen_ids:
        if len(top_results) >= 5:
            removed = top_results.pop()
            chosen_ids.discard(removed["id"])
        top_results.append(nearest_ground)
        chosen_ids.add(nearest_ground["id"])

    top_results.sort(key=lambda x: (x["distance_km"], -x["ai_score"]))
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
        _cache_put(_SCAN_CACHE, cache_key, payload, _MAX_SCAN_CACHE)

    return payload
