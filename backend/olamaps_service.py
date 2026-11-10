"""
Ola Maps API Integration Service
Provides Geocoding, Places Autocomplete, and Routing using Ola Maps (https://api.olamaps.io).
"""
import os
import urllib.parse
from typing import Dict, Any, Optional
import httpx

DEFAULT_OLAMAPS_KEY = os.getenv("OLAMAPS_API_KEY", "")

class OlaMapsClient:
    """Client for querying the Ola Maps API platform."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.olamaps.io"):
        self.api_key = api_key or os.getenv("OLAMAPS_API_KEY", DEFAULT_OLAMAPS_KEY)
        self.base_url = base_url.rstrip("/")

    async def autocomplete(self, query: str, location: Optional[str] = None, radius: Optional[int] = None) -> Dict[str, Any]:
        """
        Search for places and addresses matching a query text.
        """
        if not query or not query.strip():
            return {"status": "error", "message": "Query string is empty"}

        params = {
            "input": query.strip(),
            "api_key": self.api_key
        }
        if location:
            params["location"] = location
        if radius:
            params["radius"] = str(radius)

        url = f"{self.base_url}/places/v1/autocomplete"
        try:
            async with httpx.AsyncClient(timeout=4.0, verify=False) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "message": f"Ola Maps autocomplete returned status {resp.status_code}"
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def reverse_geocode(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Reverse geocode coordinates to find building, street name, and exact address.
        """
        params = {
            "latlng": f"{lat},{lon}",
            "api_key": self.api_key
        }
        url = f"{self.base_url}/places/v1/reverse-geocode"
        try:
            async with httpx.AsyncClient(timeout=4.0, verify=False) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "message": f"Ola Maps reverse geocode returned status {resp.status_code}"
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def get_directions(self, origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
        """
        Fetch driving directions and turn-by-turn geometry between origin and destination.
        """
        params = {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "api_key": self.api_key
        }
        url = f"{self.base_url}/routing/v1/directions"
        try:
            async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
                resp = await client.post(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                return {
                    "status": "error",
                    "code": resp.status_code,
                    "message": f"Ola Maps routing returned status {resp.status_code}"
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}
