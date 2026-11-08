#!/usr/bin/env python3
"""
Places Dataset Downloader & Local Search Indexer
Downloads and populates the offline Places Database (SQLite FTS5) with searchable places,
buildings, amenities, and POIs across Bengaluru and India.

Usage:
    # 1. Seed database with local Bengaluru places & parking catalog
    python3 scripts/download_places_dataset.py --seed

    # 2. Download live POIs for a specific city/area from OpenStreetMap Overpass
    python3 scripts/download_places_dataset.py --city "Kengeri, Bengaluru" --limit 500

    # 3. Check database stats
    python3 scripts/download_places_dataset.py --stats
"""

import os
import sys
import argparse
import json
import urllib.request
import urllib.parse
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from places_db import init_places_db, insert_places_batch, get_places_stats, search_places_fts
from traccar_service import BENGALURU_PLACES_CATALOG, load_opencity_places


def seed_local_places():
    """Seeds the catalog places and OpenCity places into the local SQLite database."""
    print("📦 Seeding local Bengaluru Places & Municipal Parking catalog...")
    places: List[Dict[str, Any]] = []

    # 1. Local Bengaluru Catalog (Hospitals, PGs, Hotels, IT Parks)
    for p in BENGALURU_PLACES_CATALOG:
        places.append({
            "id": f"cat_{p.get('lat')}_{p.get('lon')}",
            "name": p.get("name"),
            "category": p.get("category", "Commercial"),
            "badge": p.get("badge", "🏢"),
            "address": p.get("address", "Bengaluru, Karnataka"),
            "city": "Bengaluru",
            "state": "Karnataka",
            "lat": p.get("lat"),
            "lon": p.get("lon"),
            "source": "curated_catalog"
        })

    # 2. OpenCity 147 Bengaluru Municipal Parking and civic lots
    opencity_lots = load_opencity_places()
    for lot in opencity_lots:
        places.append({
            "id": f"opencity_{lot.get('lat')}_{lot.get('lon')}",
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

    inserted = insert_places_batch(places)
    print(f"✅ Successfully seeded {inserted} places into local FTS5 database!")
    return inserted


def download_overpass_places(city_bbox: str = "12.85,77.45,12.95,77.55", limit: int = 500) -> int:
    """
    Downloads places (amenities, shops, tourism, offices, buildings) via Overpass API
    for a bounding box (default: Kengeri / South-West Bengaluru).
    """
    print(f"🌐 Fetching POIs from OpenStreetMap Overpass (BBox: {city_bbox})...")
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"]({city_bbox});
      node["shop"]({city_bbox});
      node["tourism"]({city_bbox});
      node["office"]({city_bbox});
      node["building"]({city_bbox});
    );
    out body {limit};
    """
    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "OpenParkPlacesDataset/2.0 (openpark.blr)"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            elements = res_json.get("elements", [])
            print(f"📥 Received {len(elements)} raw OpenStreetMap nodes.")

            places = []
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue
                cat = tags.get("amenity") or tags.get("shop") or tags.get("tourism") or tags.get("office") or "Building"
                badge = "🏢"
                if "hospital" in cat or "clinic" in cat or "pharmacy" in cat:
                    badge = "🏥"
                elif "restaurant" in cat or "cafe" in cat or "fast_food" in cat:
                    badge = "🍔"
                elif "hotel" in cat or "hostel" in cat or "guest_house" in cat:
                    badge = "🏨"
                elif "fuel" in cat:
                    badge = "⛽"
                elif "school" in cat or "college" in cat or "university" in cat:
                    badge = "🎓"
                elif "shop" in tags:
                    badge = "🛍️"

                addr = tags.get("addr:full") or tags.get("addr:street") or "Bengaluru, Karnataka"
                places.append({
                    "id": f"osm_node_{el.get('id')}",
                    "name": name,
                    "category": cat.replace("_", " ").title(),
                    "badge": badge,
                    "address": addr,
                    "city": tags.get("addr:city", "Bengaluru"),
                    "state": "Karnataka",
                    "lat": el.get("lat"),
                    "lon": el.get("lon"),
                    "phone": tags.get("phone") or tags.get("contact:phone", ""),
                    "website": tags.get("website") or "",
                    "source": "openstreetmap_overpass"
                })

            if places:
                inserted = insert_places_batch(places)
                print(f"✅ Successfully inserted {inserted} named places into search index!")
                return inserted
            else:
                print("⚠️ No named places found in this query response.")
                return 0
    except Exception as e:
        print(f"❌ Failed to fetch from Overpass: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Places Dataset Downloader & Local Indexer")
    parser.add_argument("--seed", action="store_true", help="Seed database with local curated places and municipal parking")
    parser.add_argument("--download-osm", action="store_true", help="Download OSM places for Kengeri / Bengaluru bbox")
    parser.add_argument("--bbox", default="12.85,77.45,12.95,77.55", help="Bounding box: min_lat,min_lon,max_lat,max_lon")
    parser.add_argument("--limit", type=int, default=500, help="Max records to fetch (default: 500)")
    parser.add_argument("--stats", action="store_true", help="Show database place counts and categories")
    parser.add_argument("--search", "-s", default="", help="Test full-text search against the database")

    args = parser.parse_args()

    if args.seed:
        seed_local_places()

    if args.download_osm:
        download_overpass_places(city_bbox=args.bbox, limit=args.limit)

    if args.search:
        results = search_places_fts(args.search, limit=5)
        print(f"\n🔍 Search Results for '{args.search}': ({len(results)} found)")
        for idx, r in enumerate(results, 1):
            print(f" {idx}. {r['badge']} {r['name']} ({r['category']}) - {r['address']} [{r['lat']}, {r['lon']}]")

    if args.stats or (not args.seed and not args.download_osm and not args.search):
        stats = get_places_stats()
        print("\n" + "="*50)
        print("📊 OpenPark Offline Places Database Stats")
        print("="*50)
        print(f"Total Searchable Places: {stats['total_places']}")
        print(f"Database Path: {stats['database_path']}")
        print("Top Categories:")
        for cat, cnt in stats["top_categories"].items():
            print(f"  • {cat}: {cnt}")
        print("="*50 + "\n")


if __name__ == "__main__":
    main()
