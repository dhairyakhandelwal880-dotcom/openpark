"""
Outscraper Google Maps Places & Reviews Integration Service
Handles live querying and bulk dataset extraction of Google Maps places and reviews
via Outscraper REST API (https://api.app.outscraper.com).
"""

import os
import csv
import json
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger("openpark.outscraper")

OUTSCRAPER_API_BASE = "https://api.app.outscraper.com"


class OutscraperClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OUTSCRAPER_API_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    async def search_places(
        self,
        query: str,
        limit: int = 10,
        language: str = "en",
        region: str = "IN"
    ) -> Dict[str, Any]:
        """
        Searches Google Maps places via Outscraper Search API.
        Returns detailed places including name, rating, reviews count, phone, address, coords.
        """
        if not self.is_configured():
            return {
                "status": "error",
                "message": "Outscraper API key not configured. Get a free key at https://app.outscraper.com"
            }

        url = f"{OUTSCRAPER_API_BASE}/maps/search-v3"
        params = {
            "query": query,
            "limit": limit,
            "language": language,
            "region": region,
            "async": "false"
        }
        headers = {
            "X-API-KEY": self.api_key,
            "Accept": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=35.0, verify=False) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    raw_data = resp.json()
                    places = self._normalize_places_data(raw_data)
                    return {
                        "status": "success",
                        "query": query,
                        "total": len(places),
                        "data": places
                    }
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "message": resp.text
                }
        except Exception as e:
            logger.error("Outscraper search error: %s", e)
            return {"status": "error", "message": str(e)}

    async def get_place_reviews(
        self,
        query_or_place_id: str,
        reviews_limit: int = 20,
        limit: int = 1,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Extracts verified Google Maps user reviews for any place.
        """
        if not self.is_configured():
            return {
                "status": "error",
                "message": "Outscraper API key not configured. Get a free key at https://app.outscraper.com"
            }

        url = f"{OUTSCRAPER_API_BASE}/maps/reviews-v3"
        params = {
            "query": query_or_place_id,
            "reviewsLimit": reviews_limit,
            "limit": limit,
            "language": language,
            "async": "false"
        }
        headers = {
            "X-API-KEY": self.api_key,
            "Accept": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=45.0, verify=False) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    raw_data = resp.json()
                    results = self._normalize_reviews_data(raw_data)
                    return {
                        "status": "success",
                        "query": query_or_place_id,
                        "total_places": len(results),
                        "data": results
                    }
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "message": resp.text
                }
        except Exception as e:
            logger.error("Outscraper reviews error: %s", e)
            return {"status": "error", "message": str(e)}

    def _normalize_places_data(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Flattens and normalizes Outscraper maps response into standard schema."""
        results = []
        rows = raw_data.get("data", []) if isinstance(raw_data, dict) else raw_data
        if not isinstance(rows, list):
            return results

        for row in rows:
            # Outscraper may return lists of lists for queries
            items = row if isinstance(row, list) else [row]
            for item in items:
                if not isinstance(item, dict):
                    continue
                results.append({
                    "name": item.get("name"),
                    "place_id": item.get("place_id") or item.get("google_id"),
                    "category": item.get("type") or item.get("subtypes", ["Commercial"])[0] if item.get("subtypes") else "Commercial",
                    "rating": float(item.get("rating") or 4.5),
                    "reviews_count": int(item.get("reviews") or item.get("user_reviews") or 0),
                    "address": item.get("full_address") or item.get("address"),
                    "city": item.get("city"),
                    "state": item.get("state"),
                    "lat": float(item.get("latitude") or 0.0),
                    "lon": float(item.get("longitude") or 0.0),
                    "phone": item.get("phone"),
                    "website": item.get("site") or item.get("website"),
                    "working_hours": item.get("working_hours"),
                    "photos": item.get("photos", [])[:5] if item.get("photos") else [],
                    "reviews": [
                        {
                            "author": r.get("author_title") or "Google User",
                            "rating": r.get("review_rating") or 5,
                            "text": r.get("review_text") or "",
                            "published": r.get("review_datetime_utc") or r.get("review_timestamp")
                        }
                        for r in item.get("reviews_data", [])[:10]
                    ]
                })
        return results

    def _normalize_reviews_data(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Extracts list of places with their full reviews array."""
        return self._normalize_places_data(raw_data)


def export_places_to_csv(places: List[Dict[str, Any]], filepath: str) -> str:
    """Exports normalized places and summary reviews into CSV."""
    if not places:
        return ""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    fieldnames = [
        "name", "rating", "reviews_count", "category", "address",
        "city", "lat", "lon", "phone", "website", "sample_review"
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in places:
            sample_rev = p["reviews"][0]["text"] if p.get("reviews") else ""
            writer.writerow({
                "name": p.get("name"),
                "rating": p.get("rating"),
                "reviews_count": p.get("reviews_count"),
                "category": p.get("category"),
                "address": p.get("address"),
                "city": p.get("city"),
                "lat": p.get("lat"),
                "lon": p.get("lon"),
                "phone": p.get("phone"),
                "website": p.get("website"),
                "sample_review": sample_rev
            })
    return filepath
