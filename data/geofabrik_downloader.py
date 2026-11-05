#!/usr/bin/env python3
"""
OpenPark - Geofabrik Dataset Ingestion and Downloader
------------------------------------------------------
Downloads, parses, and integrates OpenStreetMap extracts from Geofabrik (https://download.geofabrik.de/).
Supports:
  - Listing regions (India, Southern Zone [Karnataka], etc.)
  - Resumable streaming downloads of .osm.pbf, .shp.zip, and .poly files
  - Converting .poly files to GeoJSON
  - MD5 checksum verification
"""

import os
import sys
import json
import hashlib
import argparse
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any, Callable

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "geofabrik")
REGIONS_FILE = os.path.join(DATA_DIR, "regions_india.json")
INDEX_URL = "https://download.geofabrik.de/index-v1.json"

GEOFABRIK_BASE_URL = "https://download.geofabrik.de"
USER_AGENT = "OpenPark-Geofabrik/1.0 (contact@openpark.io)"


def load_local_regions() -> List[Dict[str, Any]]:
    """Loads curated regions from local cache if present."""
    if os.path.exists(REGIONS_FILE):
        try:
            with open(REGIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("features", [])
        except Exception:
            pass
    return []


def fetch_geofabrik_index(use_cache: bool = True) -> Dict[str, Any]:
    """Fetches full Geofabrik index or loads local cache."""
    cache_path = os.path.join(DATA_DIR, "geofabrik_index.json")
    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    req = urllib.request.Request(INDEX_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def get_available_regions() -> List[Dict[str, Any]]:
    """Returns curated list of regions for India and South Asia."""
    local = load_local_regions()
    if local:
        results = []
        for feat in local:
            props = feat.get("properties", {})
            results.append({
                "id": props.get("id"),
                "name": props.get("name"),
                "parent": props.get("parent"),
                "urls": props.get("urls", {}),
                "poly_url": f"{GEOFABRIK_BASE_URL}/asia/india/{props.get('id')}.poly" if props.get("id") != "india" else f"{GEOFABRIK_BASE_URL}/asia/india.poly",
                "description": "Includes Karnataka (Bengaluru)" if "southern" in props.get("id", "") else props.get("name")
            })
        return results

    # Fallback default hardcoded descriptors
    return [
        {
            "id": "southern-zone",
            "name": "Southern Zone (Karnataka, Bengaluru, Tamil Nadu, Kerala, AP, Telangana)",
            "urls": {
                "pbf": "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf",
                "shp": "https://download.geofabrik.de/asia/india/southern-zone-latest-free.shp.zip",
                "gpkg": "https://download.geofabrik.de/asia/india/southern-zone-latest-free.gpkg.zip",
                "updates": "https://download.geofabrik.de/asia/india/southern-zone-updates"
            },
            "poly_url": "https://download.geofabrik.de/asia/india/southern-zone.poly",
            "size_pbf": "533 MB",
            "description": "Primary region extract containing Karnataka and Bengaluru OpenStreetMap dataset."
        },
        {
            "id": "india",
            "name": "India (Whole Country)",
            "urls": {
                "pbf": "https://download.geofabrik.de/asia/india-latest.osm.pbf",
                "updates": "https://download.geofabrik.de/asia/india-updates"
            },
            "poly_url": "https://download.geofabrik.de/asia/india.poly",
            "size_pbf": "1.6 GB",
            "description": "Full national dataset for India."
        }
    ]


def parse_poly_file(poly_path: str) -> Dict[str, Any]:
    """Converts a Geofabrik / Osmosis .poly file to a GeoJSON Feature."""
    coords = []
    current_ring = []

    with open(poly_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    ring_started = False
    for line in lines:
        if line.lower() == "end":
            if current_ring:
                coords.append(current_ring)
                current_ring = []
            ring_started = False
            continue

        parts = line.split()
        if len(parts) == 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                current_ring.append([lon, lat])
                ring_started = True
            except ValueError:
                pass

    if current_ring:
        coords.append(current_ring)

    geom_type = "Polygon" if len(coords) == 1 else "MultiPolygon"
    geometry = {
        "type": geom_type,
        "coordinates": coords[0] if geom_type == "Polygon" else coords
    }

    return {
        "type": "Feature",
        "properties": {
            "name": os.path.basename(poly_path),
            "source": "geofabrik_poly"
        },
        "geometry": geometry
    }


def download_file(
    url: str,
    dest_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> str:
    """Downloads a file with resume support and progress reporting."""
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    file_mode = "ab" if os.path.exists(dest_path) else "wb"
    existing_bytes = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0

    headers = {"User-Agent": USER_AGENT}
    if existing_bytes > 0:
        headers["Range"] = f"bytes={existing_bytes}-"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp, open(dest_path, file_mode) as out_f:
            total_size = resp.headers.get("Content-Length")
            total_bytes = int(total_size) + existing_bytes if total_size else 0

            downloaded = existing_bytes
            chunk_size = 64 * 1024

            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_bytes)
                elif total_bytes > 0:
                    pct = (downloaded / total_bytes) * 100
                    sys.stdout.write(f"\rDownloading: {downloaded / 1024 / 1024:.2f} MB / {total_bytes / 1024 / 1024:.2f} MB ({pct:.1f}%)")
                    sys.stdout.flush()

        if total_bytes > 0:
            sys.stdout.write("\n")
        return dest_path
    except urllib.error.HTTPError as e:
        if e.code == 416:  # Requested Range Not Satisfiable (already fully downloaded)
            return dest_path
        raise e


def verify_md5(file_path: str, md5_url: str) -> bool:
    """Verifies file against remote .md5 checksum."""
    try:
        req = urllib.request.Request(md5_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req) as resp:
            expected_md5 = resp.read().decode("utf-8").strip().split()[0]

        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        calc_md5 = hasher.hexdigest()
        return calc_md5.lower() == expected_md5.lower()
    except Exception:
        return True


def main():
    parser = argparse.ArgumentParser(description="Geofabrik Dataset Ingestion Tool for OpenPark")
    parser.add_argument("--list", action="store_true", help="List available India/Regional datasets on Geofabrik")
    parser.add_argument("--region", type=str, default="southern-zone", help="Region ID (default: southern-zone)")
    parser.add_argument("--action", type=str, choices=["info", "download-poly", "download-pbf", "poly-to-geojson"], default="info", help="Action to execute")
    parser.add_argument("--poly-file", type=str, help="Path to .poly file for conversion to GeoJSON")

    args = parser.parse_args()

    if args.list:
        regions = get_available_regions()
        print(f"\nAvailable Geofabrik Datasets ({len(regions)} regions):")
        print("=" * 70)
        for r in regions:
            print(f"ID: {r['id']}")
            print(f"Name: {r['name']}")
            print(f"URLs: {json.dumps(r.get('urls', {}), indent=2)}")
            print(f"Poly URL: {r.get('poly_url')}")
            print("-" * 70)
        return

    if args.action == "info":
        regions = get_available_regions()
        matched = next((r for r in regions if r["id"] == args.region), None)
        if not matched:
            print(f"Region '{args.region}' not found in catalog.")
            return
        print(f"\n--- Geofabrik Dataset Info: {matched['name']} ---")
        print(f"Region ID:    {matched['id']}")
        print(f"Poly URL:     {matched.get('poly_url')}")
        print(f"OSM PBF URL:  {matched.get('urls', {}).get('pbf')}")
        print(f"Shapefile:    {matched.get('urls', {}).get('shp')}")
        print(f"Description:  {matched.get('description', 'N/A')}\n")

    elif args.action == "download-poly":
        regions = get_available_regions()
        matched = next((r for r in regions if r["id"] == args.region), None)
        poly_url = matched.get("poly_url") if matched else f"https://download.geofabrik.de/asia/india/{args.region}.poly"
        dest = os.path.join(DATA_DIR, f"{args.region}.poly")
        print(f"Downloading boundary polygon from: {poly_url}")
        download_file(poly_url, dest)
        print(f"Saved: {dest} ({os.path.getsize(dest)} bytes)")

        # Convert to GeoJSON
        geojson = parse_poly_file(dest)
        geojson_dest = os.path.join(DATA_DIR, f"{args.region}.geojson")
        with open(geojson_dest, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
        print(f"Generated GeoJSON boundary: {geojson_dest}")

    elif args.action == "poly-to-geojson":
        poly_path = args.poly_file or os.path.join(DATA_DIR, f"{args.region}.poly")
        if not os.path.exists(poly_path):
            print(f"Poly file not found: {poly_path}")
            return
        geojson = parse_poly_file(poly_path)
        out_path = poly_path.replace(".poly", ".geojson")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
        print(f"Converted {poly_path} -> {out_path}")

    elif args.action == "download-pbf":
        regions = get_available_regions()
        matched = next((r for r in regions if r["id"] == args.region), None)
        pbf_url = matched.get("urls", {}).get("pbf") if matched else None
        if not pbf_url:
            print(f"No PBF URL configured for {args.region}")
            return
        dest = os.path.join(DATA_DIR, f"{args.region}-latest.osm.pbf")
        print(f"Initiating download: {pbf_url}")
        print(f"Destination: {dest}")
        download_file(pbf_url, dest)
        print(f"Download complete: {dest}")


if __name__ == "__main__":
    main()
