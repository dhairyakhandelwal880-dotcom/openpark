#!/usr/bin/env python3
"""
Outscraper Google Maps Places & Reviews Collector
Command-line utility to search any places and extract full reviews from Google Maps.

Usage:
    python3 scripts/outscraper_collector.py --query "Hostels near BGS Hospital Bangalore" --limit 5 --reviews 10 --format csv
    python3 scripts/outscraper_collector.py --query "Stanza Living Debrecan House" --reviews 20 --format json
"""

import sys
import os
import argparse
import asyncio
import json

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from outscraper_service import OutscraperClient, export_places_to_csv


async def main():
    parser = argparse.ArgumentParser(description="Collect Google Maps Places and Reviews with Outscraper")
    parser.add_argument("--query", "-q", required=True, help="Search query (e.g. 'Debrecan House Bangalore' or 'Cafes in Indiranagar')")
    parser.add_argument("--api-key", "-k", default=os.getenv("OUTSCRAPER_API_KEY", ""), help="Outscraper API Key (from https://app.outscraper.com)")
    parser.add_argument("--limit", "-l", type=int, default=5, help="Number of places to extract (default: 5)")
    parser.add_argument("--reviews", "-r", type=int, default=10, help="Max reviews per place (default: 10)")
    parser.add_argument("--format", "-f", choices=["json", "csv"], default="json", help="Output format (json or csv)")
    parser.add_argument("--output", "-o", default="", help="Custom output file path")

    args = parser.parse_args()

    api_key = args.api_key.strip()
    if not api_key:
        print("\n" + "="*70)
        print("⚠️  OUTSCRAPER API KEY REQUIRED")
        print("="*70)
        print("To fetch live Google Maps places and reviews at scale:")
        print("1. Get your free Outscraper API key from: https://app.outscraper.com")
        print("2. Set it in your terminal:")
        print("   export OUTSCRAPER_API_KEY='your_api_key_here'")
        print("3. Or pass it directly via --api-key:")
        print(f"   python3 scripts/outscraper_collector.py -q \"{args.query}\" --api-key YOUR_KEY\n")
        sys.exit(1)

    print(f"\n🔍 Querying Outscraper Google Maps API for: \"{args.query}\"...")
    client = OutscraperClient(api_key=api_key)

    result = await client.get_place_reviews(
        query_or_place_id=args.query,
        reviews_limit=args.reviews,
        limit=args.limit
    )

    if result.get("status") != "success":
        print(f"❌ Failed: {result.get('message', 'Unknown error')}")
        sys.exit(1)

    places = result.get("data", [])
    print(f"✅ Found {len(places)} place(s) with user reviews!")

    # Determine output file path
    clean_q = "".join(c if c.isalnum() else "_" for c in args.query.lower())[:30]
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(out_dir, exist_ok=True)

    if args.format == "csv":
        out_path = args.output or os.path.join(out_dir, f"outscraper_{clean_q}.csv")
        export_places_to_csv(places, out_path)
        print(f"📁 Exported dataset to CSV: {out_path}")
    else:
        out_path = args.output or os.path.join(out_dir, f"outscraper_{clean_q}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(places, f, indent=2, ensure_ascii=False)
        print(f"📁 Exported dataset to JSON: {out_path}")

    # Print summary of first place
    if places:
        p0 = places[0]
        print("\n" + "-"*50)
        print(f"📍 Name: {p0.get('name')}")
        print(f"⭐ Rating: {p0.get('rating')} ({p0.get('reviews_count')} reviews)")
        print(f"📌 Address: {p0.get('address')}")
        print(f"📞 Phone: {p0.get('phone') or 'N/A'}")
        print(f"🌐 Website: {p0.get('website') or 'N/A'}")
        print(f"💬 Top Review:")
        if p0.get("reviews"):
            r = p0["reviews"][0]
            print(f"   [{r.get('rating')}★ by {r.get('author')}]: \"{r.get('text')[:120]}...\"")
        print("-"*50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
