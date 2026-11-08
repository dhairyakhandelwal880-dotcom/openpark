#!/usr/bin/env python3
"""
Places Dataset Downloader & Local Search Indexer
Downloads, ingests, and populates the offline Places Database (SQLite FTS5)
with thousands of real-world places, buildings, amenities, PGs, and POIs across
Bengaluru, Karnataka, and India.

Usage:
    # Build complete offline places dataset
    python3 scripts/download_places_dataset.py --all

    # Search the database
    python3 scripts/download_places_dataset.py --search "Debrecan"
"""

import os
import sys
import argparse
import json
import time
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Set

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from places_db import init_places_db, insert_places_batch, get_places_stats, search_places_fts
from traccar_service import BENGALURU_PLACES_CATALOG, load_opencity_places, resolve_place_badge


def seed_local_and_cached_places() -> int:
    """Ingests curated places catalog, municipal lots, and local cached GeoJSON."""
    print("📦 Step 1: Ingesting local Bengaluru Catalogs & Municipal Datasets...")
    places: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    # 1. Local Bengaluru Catalog (Debrecan House, OYO Golden Grand, BGS Hospital, etc.)
    for p in BENGALURU_PLACES_CATALOG:
        key = f"{p.get('name')}_{round(p.get('lat', 0), 4)}_{round(p.get('lon', 0), 4)}"
        if key not in seen:
            seen.add(key)
            places.append({
                "id": f"cat_{round(p.get('lat', 0), 5)}_{round(p.get('lon', 0), 5)}",
                "name": p.get("name"),
                "category": p.get("category", "Commercial"),
                "badge": p.get("badge", "🏢"),
                "address": p.get("address", "Uttarahalli Main Rd, Kengeri, Bengaluru"),
                "city": "Bengaluru",
                "state": "Karnataka",
                "lat": p.get("lat"),
                "lon": p.get("lon"),
                "source": "curated_catalog"
            })

    # 2. OpenCity 147 Bengaluru Municipal Parking and civic lots
    opencity_lots = load_opencity_places()
    for lot in opencity_lots:
        key = f"{lot.get('name')}_{round(lot.get('lat', 0), 4)}_{round(lot.get('lon', 0), 4)}"
        if key not in seen:
            seen.add(key)
            places.append({
                "id": f"opencity_{round(lot.get('lat', 0), 5)}_{round(lot.get('lon', 0), 5)}",
                "name": lot.get("name"),
                "category": "Parking & Civic Facility",
                "badge": "🅿️",
                "address": lot.get("address", "Bengaluru"),
                "city": "Bengaluru",
                "state": "Karnataka",
                "lat": lot.get("lat"),
                "lon": lot.get("lon"),
                "source": "opencity_bengaluru"
            })

    # 3. Cached Overpass GeoJSON
    geojson_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "osm_overpass_cache.geojson")
    )
    if os.path.exists(geojson_path):
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                geo_data = json.load(f)
                features = geo_data.get("features", [])
                for feat in features:
                    props = feat.get("properties", {})
                    name = props.get("name") or props.get("lot_name")
                    lat = props.get("lat") or props.get("latitude")
                    lon = props.get("lon") or props.get("longitude")
                    if not (lat and lon) and feat.get("geometry"):
                        coords = feat["geometry"].get("coordinates")
                        if coords:
                            # If Polygon, take centroid or first point
                            if feat["geometry"].get("type") == "Polygon" and coords[0]:
                                lon, lat = coords[0][0][0], coords[0][0][1]
                            elif feat["geometry"].get("type") == "Point":
                                lon, lat = coords[0], coords[1]
                    if name and lat and lon:
                        key = f"{name}_{round(lat, 4)}_{round(lon, 4)}"
                        if key not in seen:
                            seen.add(key)
                            places.append({
                                "id": f"cached_geo_{feat.get('id', len(places))}",
                                "name": name,
                                "category": props.get("amenity") or "Parking Facility",
                                "badge": "🅿️",
                                "address": props.get("address") or "Bengaluru, Karnataka",
                                "city": "Bengaluru",
                                "state": "Karnataka",
                                "lat": float(lat),
                                "lon": float(lon),
                                "source": "osm_cache"
                            })
        except Exception as e:
            print(f"⚠️ Notice: could not load local geojson cache: {e}")

    inserted = insert_places_batch(places)
    print(f"✅ Ingested {inserted} local places into offline search index.")
    return inserted


def download_live_photon_dataset() -> int:
    """
    Downloads comprehensive POIs from Photon Geocoder covering all categories:
    PGs, Hostels, Hotels, Hospitals, Clinics, Colleges, Schools, Restaurants,
    Cafes, Malls, Tech Parks, Supermarkets, Fuel Stations, and Metro Stations.
    """
    print("\n🌐 Step 2: Downloading Comprehensive Places Dataset via Photon (OpenStreetMap)...")

    # Categories to harvest with high density
    queries = [
        # Accommodation & PGs
        ("pg boys kengeri", 12.9048, 77.5018),
        ("pg ladies kengeri", 12.9048, 77.5018),
        ("stanza living bangalore", 12.9048, 77.5018),
        ("hostel kengeri", 12.9048, 77.5018),
        ("hotel uttarahalli", 12.9048, 77.5018),
        ("hotel kengeri", 12.9048, 77.5018),
        ("hotel bangalore", 12.9716, 77.5946),
        ("resort bangalore", 12.9716, 77.5946),
        # Healthcare
        ("hospital kengeri", 12.9048, 77.5018),
        ("bgs hospital bangalore", 12.9048, 77.5018),
        ("hospital bangalore", 12.9716, 77.5946),
        ("clinic bangalore", 12.9716, 77.5946),
        ("pharmacy bangalore", 12.9048, 77.5018),
        # Dining & Food
        ("restaurant kengeri", 12.9048, 77.5018),
        ("cafe kengeri", 12.9048, 77.5018),
        ("restaurant bangalore", 12.9716, 77.5946),
        ("cafe bangalore", 12.9716, 77.5946),
        ("bakery bangalore", 12.9716, 77.5946),
        # Education & Tech
        ("college kengeri", 12.9048, 77.5018),
        ("school kengeri", 12.9048, 77.5018),
        ("university bangalore", 12.9716, 77.5946),
        ("tech park bangalore", 12.9716, 77.5946),
        ("manyata tech park", 13.0450, 77.6200),
        ("itpl whitefield", 12.9866, 77.7381),
        ("electronic city bangalore", 12.8450, 77.6600),
        # Shopping & Transit
        ("mall bangalore", 12.9716, 77.5946),
        ("supermarket kengeri", 12.9048, 77.5018),
        ("metro station bangalore", 12.9716, 77.5946),
        ("railway station bangalore", 12.9716, 77.5946),
        ("petrol pump bangalore", 12.9048, 77.5018),
        ("temple bangalore", 12.9716, 77.5946),
        ("park bangalore", 12.9716, 77.5946),
        # Major Indian Cities Landmark Centers
        ("hospital delhi", 28.6139, 77.2090),
        ("hotel mumbai", 19.0760, 72.8777),
        ("mall hyderabad", 17.3850, 78.4867),
        ("hotel chennai", 13.0827, 80.2707)
    ]

    total_fetched = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    for idx, (q, lat, lon) in enumerate(queries, 1):
        url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(q)}&lat={lat}&lon={lon}&limit=35"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                features = data.get("features", [])
                places = []
                for feat in features:
                    props = feat.get("properties", {})
                    name = props.get("name")
                    if not name:
                        continue
                    coords = feat.get("geometry", {}).get("coordinates", [])
                    if len(coords) < 2:
                        continue
                    p_lon, p_lat = float(coords[0]), float(coords[1])
                    osm_val = props.get("osm_value", "")
                    osm_key = props.get("osm_key", "")
                    badge = resolve_place_badge(osm_val, osm_key)

                    addr_parts = []
                    if props.get("street"):
                        addr_parts.append(f"{props.get('housenumber', '')} {props['street']}".strip())
                    if props.get("district") or props.get("locality"):
                        addr_parts.append(props.get("locality") or props.get("district"))
                    if props.get("city"):
                        addr_parts.append(props["city"])
                    if props.get("state"):
                        addr_parts.append(props["state"])

                    full_addr = ", ".join(addr_parts) if addr_parts else f"Coordinates: {round(p_lat, 4)}, {round(p_lon, 4)}"
                    cat = (props.get("osm_value") or props.get("type") or "Commercial").replace("_", " ").title()

                    places.append({
                        "id": f"photon_{props.get('osm_id', f'{p_lat}_{p_lon}')}",
                        "name": name,
                        "category": cat,
                        "badge": badge,
                        "address": full_addr,
                        "city": props.get("city", "Bengaluru"),
                        "state": props.get("state", "Karnataka"),
                        "lat": p_lat,
                        "lon": p_lon,
                        "source": "photon_openstreetmap"
                    })

                if places:
                    c = insert_places_batch(places)
                    total_fetched += c
                    print(f" [{idx}/{len(queries)}] '{q}': +{c} places (Running Total: {total_fetched})")
            time.sleep(0.3)  # Gentle rate limiting
        except Exception as e:
            print(f" [{idx}/{len(queries)}] '{q}' notice: {e}")

    print(f"\n🎉 Successfully downloaded and indexed {total_fetched} live places!")
    return total_fetched


def main():
    parser = argparse.ArgumentParser(description="Build and Search Offline Places Database")
    parser.add_argument("--all", action="store_true", help="Download and build the complete places dataset")
    parser.add_argument("--seed", action="store_true", help="Ingest local catalogs only")
    parser.add_argument("--search", "-s", default="", help="Search places in the database")
    parser.add_argument("--stats", action="store_true", help="Display database summary")

    args = parser.parse_args()

    if args.all:
        seed_local_and_cached_places()
        download_live_photon_dataset()
        stats = get_places_stats()
        print("\n" + "="*50)
        print("📊 DATASET READY: Database Statistics")
        print("="*50)
        print(f"Total Places in Database: {stats['total_places']}")
        print("Top Categories:")
        for cat, cnt in stats["top_categories"].items():
            print(f"  • {cat}: {cnt}")
        print("="*50)
        return

    if args.seed:
        seed_local_and_cached_places()

    if args.search:
        results = search_places_fts(args.search, limit=8)
        print(f"\n🔍 Results for '{args.search}': ({len(results)} found)")
        for idx, r in enumerate(results, 1):
            print(f" {idx}. {r['badge']} {r['name']} [{r['category']}] - {r['address']} ({r['lat']}, {r['lon']})")

    if args.stats or (not args.all and not args.seed and not args.search):
        stats = get_places_stats()
        print(f"\nTotal Places: {stats['total_places']}")
        print(f"Database: {stats['database_path']}")


if __name__ == "__main__":
    main()
