#!/usr/bin/env python3
"""
Overture Maps Places Extractor & OpenPark Database Importer
-----------------------------------------------------------
Queries the latest Overture Maps S3 release directly via DuckDB HTTPFS (no AWS creds needed):
  1. Auto-detects the newest Overture Maps release from S3 XML listing.
  2. Extracts Greater Bengaluru high-confidence POIs + India-wide parking/mall/transit hubs.
  3. Saves a compact gzip archive (data/overture_places_openpark.json.gz) for zero-bloat git/Railway
     deployment and populates SQLite FTS5 (data/places_search.db).
"""

import argparse
import gzip
import json
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from places_db import insert_places_batch, get_places_stats

DEFAULT_RELEASE = "2026-10-21.0"
S3_LIST_URL = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/?list-type=2&delimiter=/&prefix=release/"
ARCHIVE_PATH = os.path.join(ROOT_DIR, "data", "overture_places_openpark.json.gz")

CATEGORY_BADGES = {
    "parking": "🅿️",
    "parking_lot": "🅿️",
    "parking_garage": "🅿️",
    "truck_stop": "🅿️",
    "rest_stop": "🅿️",
    "shopping_center": "🛍️",
    "shopping_mall": "🛍️",
    "mall": "🛍️",
    "department_store": "🛍️",
    "superstore": "🛍️",
    "supermarket": "🛒",
    "marketplace": "🛍️",
    "hospital": "🏥",
    "clinic": "🏥",
    "hotel": "🏨",
    "restaurant": "🍽️",
    "cafe": "☕",
    "airport": "✈️",
    "train_station": "🚆",
    "subway_station": "🚇",
    "bus_station": "🚌",
    "ev_charging_station": "⚡",
}


def resolve_latest_release() -> str:
    """Finds the newest Overture Maps release folder on public S3."""
    try:
        req = urllib.request.Request(S3_LIST_URL, headers={"User-Agent": "OpenPark/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            xml_text = resp.read().decode("utf-8")
        root = ET.fromstring(xml_text)
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        releases = [
            el.text.strip("/").split("/")[-1]
            for el in root.findall(".//s3:CommonPrefixes/s3:Prefix", ns)
            if el.text
        ]
        if releases:
            releases.sort()
            return releases[-1]
    except Exception as exc:
        print(f"⚠️ Could not list S3 releases, using default {DEFAULT_RELEASE}: {exc}")
    return DEFAULT_RELEASE


def extract_overture_places(release: str, include_all_blr: bool = True, limit_blr: int = 25000) -> List[Dict[str, Any]]:
    """Streams filtered India places from Overture Maps S3 via DuckDB HTTPFS."""
    import duckdb

    print(f"🛰️ Querying Overture Maps release '{release}' via DuckDB HTTPFS...")
    t0 = time.perf_counter()
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")

    parquet_glob = f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"

    blr_clause = (
        "(bbox.xmin BETWEEN 77.38 AND 77.82 AND bbox.ymin BETWEEN 12.78 AND 13.18)"
        if include_all_blr else "FALSE"
    )

    sql = f"""
    WITH filtered AS (
      SELECT
        id,
        names."primary"                 AS name,
        COALESCE(taxonomy."primary", basic_category, 'place') AS category,
        basic_category,
        confidence,
        addresses[1].freeform           AS address,
        addresses[1].locality           AS city,
        addresses[1].region             AS state,
        addresses[1].postcode           AS postcode,
        websites[1]                     AS website,
        phones[1]                       AS phone,
        bbox.xmin                       AS lon,
        bbox.ymin                       AS lat,
        ({blr_clause})                  AS is_blr
      FROM read_parquet('{parquet_glob}', hive_partitioning=1)
      WHERE bbox.xmin BETWEEN 68.0 AND 98.0
        AND bbox.ymin BETWEEN 6.0 AND 37.5
        AND addresses[1].country = 'IN'
        AND confidence >= 0.7
        AND (operating_status = 'open' OR operating_status IS NULL)
        AND names."primary" IS NOT NULL
        AND (
          {blr_clause}
          OR taxonomy."primary" ILIKE '%parking%'
          OR basic_category = 'parking'
          OR taxonomy."primary" IN (
            'shopping_center', 'shopping_mall', 'mall', 'department_store',
            'superstore', 'marketplace', 'airport', 'train_station', 'subway_station',
            'ev_charging_station'
          )
        )
    )
    SELECT id, name, category, basic_category, confidence, address, city, state, postcode, website, phone, lon, lat, is_blr
    FROM filtered
    QUALIFY
      (NOT is_blr)
      OR (ROW_NUMBER() OVER (
            PARTITION BY is_blr
            ORDER BY
              (CASE
                WHEN category ILIKE '%parking%' OR category IN ('shopping_center','shopping_mall','mall','department_store','superstore','ev_charging_station','hospital','train_station','subway_station') THEN 0
                ELSE 1
              END),
              confidence DESC
          ) <= {int(limit_blr)})
    """

    rows = con.sql(sql).fetchall()
    cols = ["id", "name", "category", "basic_category", "confidence", "address", "city", "state", "postcode", "website", "phone", "lon", "lat", "is_blr"]
    places: List[Dict[str, Any]] = []
    for r in rows:
        rec = dict(zip(cols, r))
        cat = str(rec["category"] or rec["basic_category"] or "place").strip()
        cat_clean = cat.replace("_", " ").title()
        badge = CATEGORY_BADGES.get(cat.lower()) or (
            "🅿️" if "parking" in cat.lower() else "🛍️" if "shop" in cat.lower() or "mall" in cat.lower() else "📍"
        )
        addr_parts = [p for p in (rec["address"], rec["city"], rec["state"], rec["postcode"]) if p]
        places.append({
            "id": f"ovt_{rec['id']}",
            "name": str(rec["name"]).strip(),
            "category": cat_clean,
            "badge": badge,
            "address": ", ".join(addr_parts)[:180],
            "city": str(rec["city"] or ("Bengaluru" if rec["is_blr"] else "India")).strip(),
            "state": str(rec["state"] or ("Karnataka" if rec["is_blr"] else "India")).strip(),
            "lat": round(float(rec["lat"]), 6),
            "lon": round(float(rec["lon"]), 6),
            "phone": str(rec["phone"] or "")[:32],
            "website": str(rec["website"] or "")[:120],
            "rating": round(4.0 + min(0.9, float(rec["confidence"] or 0.75) * 0.8), 1),
            "reviews_count": int(round(float(rec["confidence"] or 0.75) * 200)),
            "source": f"overture_{release}",
        })

    print(f"✅ Extracted {len(places)} Overture places in {time.perf_counter() - t0:.1f}s")
    return places


def save_and_import(places: List[Dict[str, Any]]) -> None:
    if not places:
        print("⚠️ No places extracted.")
        return

    os.makedirs(os.path.dirname(ARCHIVE_PATH), exist_ok=True)
    with gzip.open(ARCHIVE_PATH, "wt", encoding="utf-8") as gz:
        json.dump(places, gz, separators=(",", ":"))
    size_kb = os.path.getsize(ARCHIVE_PATH) // 1024
    print(f"💾 Saved compressed archive: {ARCHIVE_PATH} ({size_kb} KB)")

    inserted = insert_places_batch(places)
    stats = get_places_stats()
    print(f"📚 Imported {inserted} places into SQLite FTS5 -> total_places={stats['total_places']}")
    print("   Top categories:", stats["top_categories"])


def hydrate_from_archive() -> int:
    """Fast local hydration (~1s) from data/overture_places_openpark.json.gz without hitting S3."""
    if not os.path.exists(ARCHIVE_PATH):
        return 0
    with gzip.open(ARCHIVE_PATH, "rt", encoding="utf-8") as gz:
        places = json.load(gz)
    return insert_places_batch(places)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Overture Maps India Places Importer for OpenPark")
    parser.add_argument("--release", default=None, help="Overture release tag (default: latest on S3)")
    parser.add_argument("--hydrate-only", action="store_true", help="Import from local json.gz archive only")
    parser.add_argument("--limit-blr", type=int, default=20000, help="Max Bengaluru POIs to include")
    args = parser.parse_args()

    if args.hydrate_only:
        n = hydrate_from_archive()
        print(f"Hydrated {n} Overture places from archive.")
    else:
        rel = args.release or resolve_latest_release()
        extracted = extract_overture_places(rel, limit_blr=args.limit_blr)
        save_and_import(extracted)
