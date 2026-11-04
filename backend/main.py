"""
OpenPark - Real-Time Smart Parking Backend API
----------------------------------------------
Implements Steps 5, 6, 13, and 14 from the OpenPark Build Guide:
- Spatial nearby search with PostGIS
- Availability status logic and confidence calculation
- Crowdsourced reports with rate limiting
- Real-time WebSocket pub/sub for lot status updates
- Vehicle tracking and proactive 1.5 km arrival / reroute notifications
"""

import os
import json
import asyncio
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set
import math

from dotenv import load_dotenv

# Load environment configuration
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

try:
    from backend.iiot_service import get_lot_telemetry
except ImportError:
    from iiot_service import get_lot_telemetry

try:
    from backend.traccar_service import (
        process_traccar_ping,
        get_all_devices,
        get_all_positions,
        get_position_history,
    )
except ImportError:
    from traccar_service import (
        process_traccar_ping,
        get_all_devices,
        get_all_positions,
        get_position_history,
    )

try:
    from backend.mappls_service import (
        get_mappls_config,
        set_mappls_rest_key,
        autosuggest as mappls_autosuggest_service,
        get_directions as mappls_get_directions_service,
    )
except ImportError:
    from mappls_service import (
        get_mappls_config,
        set_mappls_rest_key,
        autosuggest as mappls_autosuggest_service,
        get_directions as mappls_get_directions_service,
    )

API_KEY = os.getenv("OPENPARK_API_KEY", "dev-key")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://openpark:openpark@localhost:5432/openpark"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@contextmanager
def get_db():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=3)
        yield conn
    except Exception:
        yield None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


OPENCITY_DATA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "bengaluru_parking_opencity.json")
)


def load_opencity_fallback():
    if os.path.exists(OPENCITY_DATA_PATH):
        try:
            with open(OPENCITY_DATA_PATH, "r", encoding="utf-8") as f:
                lots = json.load(f)
                now = datetime.now(timezone.utc)
                for lot in lots:
                    lot["updated_at"] = now
                return lots
        except Exception:
            pass
    return [
        {"id": 1, "osm_ref": "way/blr_ub_city", "name": "UB City Multi-Level Car Parking", "city": "Bengaluru", "lat": 12.9719, "lon": 77.5958, "capacity": 1200, "price_note": "₹50/hr (cars), ₹20/hr (bikes)", "free_spots": 45, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 2, "osm_ref": "way/blr_brigade_rd", "name": "Brigade Road BBMP Smart Parking", "city": "Bengaluru", "lat": 12.9740, "lon": 77.6074, "capacity": 85, "price_note": "₹30/hr", "free_spots": 76, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 3, "osm_ref": "way/blr_church_st", "name": "Church Street Public Parking Lot", "city": "Bengaluru", "lat": 12.9751, "lon": 77.6047, "capacity": 60, "price_note": "₹30/hr", "free_spots": 57, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 4, "osm_ref": "way/blr_garuda_mall", "name": "Garuda Mall Basement Parking - Magrath Rd", "city": "Bengaluru", "lat": 12.9702, "lon": 77.6097, "capacity": 650, "price_note": "₹40/hr", "free_spots": 450, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 5, "osm_ref": "way/blr_commercial_st", "name": "Commercial Street Multi-Level Car Parking (MLCP)", "city": "Bengaluru", "lat": 12.9822, "lon": 77.6083, "capacity": 450, "price_note": "₹30/hr", "free_spots": 313, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 6, "osm_ref": "way/blr_majestic", "name": "Kempegowda (Majestic) Metro & Bus Interchange Parking", "city": "Bengaluru", "lat": 12.9774, "lon": 77.5726, "capacity": 800, "price_note": "₹30 for 4 hrs (Metro commuters)", "free_spots": 38, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 7, "osm_ref": "way/blr_cubbon_park", "name": "Cubbon Park High Court Gate Parking", "city": "Bengaluru", "lat": 12.9781, "lon": 77.5925, "capacity": 120, "price_note": "₹20/hr", "free_spots": 8, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 8, "osm_ref": "way/blr_indiranagar", "name": "Indiranagar 100ft Road Metro Parking", "city": "Bengaluru", "lat": 12.9784, "lon": 77.6387, "capacity": 150, "price_note": "₹30/hr", "free_spots": 67, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 9, "osm_ref": "way/blr_koramangala_forum", "name": "Nexus Mall (Forum) Parking - Koramangala", "city": "Bengaluru", "lat": 12.9348, "lon": 77.6111, "capacity": 750, "price_note": "₹40/hr", "free_spots": 112, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 10, "osm_ref": "way/blr_jayanagar_complex", "name": "Jayanagar 4th Block BDA Shopping Complex MLCP", "city": "Bengaluru", "lat": 12.9298, "lon": 77.5834, "capacity": 320, "price_note": "₹25/hr", "free_spots": 288, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 11, "osm_ref": "way/blr_malleshwaram_8th", "name": "Malleshwaram 8th Cross Public Parking", "city": "Bengaluru", "lat": 12.9989, "lon": 77.5704, "capacity": 90, "price_note": "₹20/hr", "free_spots": 62, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 12, "osm_ref": "way/blr_whitefield_itpl", "name": "ITPL Main Gate Parking - Whitefield", "city": "Bengaluru", "lat": 12.9866, "lon": 77.7381, "capacity": 500, "price_note": "₹30/hr", "free_spots": 240, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 13, "osm_ref": "way/blr_mg_road_metro", "name": "MG Road Boulevard Metro Parking", "city": "Bengaluru", "lat": 12.9754, "lon": 77.6066, "capacity": 110, "price_note": "₹30/hr", "free_spots": 96, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 14, "osm_ref": "way/blr_kr_market", "name": "KR Market Underground Parking Facility", "city": "Bengaluru", "lat": 12.9642, "lon": 77.5765, "capacity": 300, "price_note": "₹20/hr", "free_spots": 40, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
        {"id": 15, "osm_ref": "way/blr_cantonment_station", "name": "Bengaluru Cantonment Railway Station Parking", "city": "Bengaluru", "lat": 12.9937, "lon": 77.5983, "capacity": 180, "price_note": "₹20/hr", "free_spots": 82, "source": "sensor", "updated_at": datetime.now(timezone.utc)},
    ]


FALLBACK_LOTS = load_opencity_fallback()


# --------------------------------------------------------------------------
# Step 6 & 13: Availability & Confidence Logic
# --------------------------------------------------------------------------

SOURCE_WEIGHT = {
    "sensor": 0.95,
    "operator": 0.85,
    "crowd": 0.60,
    "predicted": 0.40,
}


def lot_status(free: Optional[int], capacity: Optional[int], updated_at: Optional[datetime]) -> str:
    """Computes simple, honest availability status label."""
    if free is None:
        return "unknown"
    if free == 0:
        return "full"
    ratio = free / capacity if capacity and capacity > 0 else None
    if free < 5 or (ratio is not None and ratio < 0.15):
        return "filling_up"
    if updated_at is not None:
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age_min = (datetime.now(timezone.utc) - updated_at).total_seconds() / 60.0
        if age_min > 180:
            return "unknown"  # truly ancient (> 3 hours without sensor ping)
    return "available"


def get_confidence(source: Optional[str], updated_at: Optional[datetime]):
    """Computes confidence score (0 to 1) and label (High, Medium, Low)."""
    if not source or not updated_at:
        return 0.0, "Low"
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age_min = (datetime.now(timezone.utc) - updated_at).total_seconds() / 60.0
    freshness = 2.718 ** (-age_min / 20.0)  # halves roughly every 14 minutes
    score = round(SOURCE_WEIGHT.get(source, 0.5) * freshness, 2)
    if score >= 0.7:
        level = "High"
    elif score >= 0.4:
        level = "Medium"
    else:
        level = "Low"
    return score, level


def human_time_ago(updated_at: Optional[datetime]) -> str:
    if not updated_at:
        return "Never"
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    seconds = int((datetime.now(timezone.utc) - updated_at).total_seconds())
    if seconds < 30:
        return "Just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    return f"{hours // 24} days ago"


# --------------------------------------------------------------------------
# WebSocket Connection Manager & Redis Bridge
# --------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        # lot_id -> set of WebSockets
        self.lot_subscribers: Dict[int, Set[WebSocket]] = {}
        # active vehicle trackers
        self.vehicle_sockets: Set[WebSocket] = set()

    async def connect_lot(self, lot_id: int, websocket: WebSocket):
        await websocket.accept()
        if lot_id not in self.lot_subscribers:
            self.lot_subscribers[lot_id] = set()
        self.lot_subscribers[lot_id].add(websocket)

    def disconnect_lot(self, lot_id: int, websocket: WebSocket):
        if lot_id in self.lot_subscribers:
            self.lot_subscribers[lot_id].discard(websocket)
            if not self.lot_subscribers[lot_id]:
                del self.lot_subscribers[lot_id]

    async def broadcast_lot(self, lot_id: int, data: dict):
        if lot_id in self.lot_subscribers:
            dead_sockets = set()
            for ws in self.lot_subscribers[lot_id]:
                try:
                    await ws.send_json(data)
                except Exception:
                    dead_sockets.add(ws)
            for ws in dead_sockets:
                self.lot_subscribers[lot_id].discard(ws)

    async def connect_vehicle(self, websocket: WebSocket):
        await websocket.accept()
        self.vehicle_sockets.add(websocket)

    def disconnect_vehicle(self, websocket: WebSocket):
        self.vehicle_sockets.discard(websocket)

    async def broadcast_vehicle(self, data: dict):
        dead_sockets = set()
        for ws in self.vehicle_sockets:
            try:
                await ws.send_json(data)
            except Exception:
                dead_sockets.add(ws)
        for ws in dead_sockets:
            self.vehicle_sockets.discard(ws)


manager = ConnectionManager()
redis_client: Optional[aioredis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        print("Connected to Redis successfully.")
    except Exception as e:
        print(f"Redis connection warning: {e}. Falling back to in-memory pub/sub.")
        redis_client = None
    yield
    if redis_client:
        await redis_client.close()


app = FastAPI(
    title="OpenPark API",
    description="Open-source real-time parking platform for metro cities",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "app"))
DASHBOARD_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "dashboard"))

if os.path.isdir(APP_DIR):
    app.mount("/app", StaticFiles(directory=APP_DIR, html=True), name="app")

if os.path.isdir(DASHBOARD_DIR):
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/app/")



# --------------------------------------------------------------------------
# Pydantic Schemas
# --------------------------------------------------------------------------

class AvailabilityPayload(BaseModel):
    free_spots: int = Field(..., ge=0, description="Count of free parking spots")
    source: str = Field(default="sensor", description="sensor | operator | crowd | predicted")


class ReportPayload(BaseModel):
    kind: str = Field(..., description="got_spot | lot_full | has_space")
    reporter_id: Optional[str] = Field(default="anonymous", description="Unique client or device identifier")


class LotEditPayload(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = None
    price_note: Optional[str] = None
    city: Optional[str] = None


# --------------------------------------------------------------------------
# MapLibre GL JS Open-Source Vector Map Configuration (https://maplibre.org/maplibre-gl-js/docs/API/)
# --------------------------------------------------------------------------

class MapStyleConfigPayload(BaseModel):
    default_style: Optional[str] = None


# --------------------------------------------------------------------------
# REST Endpoints
# --------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "OpenPark API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/config/map")
def get_map_config():
    return {
        "engine": "MapLibre GL JS",
        "api_docs": "https://maplibre.org/maplibre-gl-js/docs/API/",
        "requires_token": False,
        "default_style": "carto-dark",
        "supported_styles": [
            "carto-dark",
            "carto-voyager",
            "carto-positron",
            "maplibre-demo",
            "osm-standard"
        ]
    }


@app.post("/config/map")
def update_map_config(payload: MapStyleConfigPayload):
    return {
        "status": "ok",
        "default_style": payload.default_style or "carto-dark",
        "engine": "MapLibre GL JS",
        "requires_token": False
    }


# --------------------------------------------------------------------------
# Mappls (MapmyIndia) REST API (https://github.com/mappls-api/mapmyindia-rest-api)
# --------------------------------------------------------------------------

class MapplsConfigPayload(BaseModel):
    mappls_rest_key: Optional[str] = None


@app.get("/config/mappls")
def get_mappls_config_endpoint():
    return get_mappls_config()


@app.post("/config/mappls")
def update_mappls_config_endpoint(payload: MapplsConfigPayload):
    if payload.mappls_rest_key is not None:
        set_mappls_rest_key(payload.mappls_rest_key)
    return get_mappls_config()


@app.get("/api/mappls/autosuggest")
async def mappls_autosuggest_endpoint(
    query: str = Query(..., min_length=1),
    lat: float = Query(12.9716),
    lon: float = Query(77.5946)
):
    results = await mappls_autosuggest_service(query=query, lat=lat, lon=lon)
    return {"status": "ok", "query": query, "results": results}


@app.get("/api/mappls/route")
async def mappls_route_endpoint(
    start_lat: float = Query(...),
    start_lon: float = Query(...),
    dest_lat: float = Query(...),
    dest_lon: float = Query(...)
):
    route = await mappls_get_directions_service(
        start_lat=start_lat,
        start_lon=start_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon
    )
    return route


# --------------------------------------------------------------------------
# Traccar GPS Tracking Protocol & REST API (https://www.traccar.org/)
# --------------------------------------------------------------------------

class TraccarPingPayload(BaseModel):
    id: Optional[str] = None
    deviceId: Optional[str] = None
    lat: Optional[float] = None
    latitude: Optional[float] = None
    lon: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[str] = None
    speed: Optional[float] = None
    bearing: Optional[float] = None
    course: Optional[float] = None
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    batt: Optional[float] = None
    battery: Optional[float] = None
    charge: Optional[bool] = None


@app.get("/api/traccar")
@app.post("/api/traccar")
async def traccar_client_endpoint(
    id: Optional[str] = Query(None, description="Traccar device ID"),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    timestamp: Optional[str] = Query(None),
    speed: Optional[float] = Query(None),
    bearing: Optional[float] = Query(None),
    altitude: Optional[float] = Query(None),
    accuracy: Optional[float] = Query(None),
    batt: Optional[float] = Query(None),
    charge: Optional[bool] = Query(None),
    payload: Optional[TraccarPingPayload] = None
):
    """
    Standard Traccar Client / OsmAnd Protocol Ingestion.
    Supports official Traccar Client Android/iOS apps and hardware GPS trackers.
    """
    dev_id = id or (payload.deviceId if payload else None) or (payload.id if payload else None) or "OP-TRACKER-01"
    latitude = lat if lat is not None else (payload.latitude if payload and payload.latitude is not None else (payload.lat if payload else None))
    longitude = lon if lon is not None else (payload.longitude if payload and payload.longitude is not None else (payload.lon if payload else None))

    if latitude is None or longitude is None:
        return {"status": "ok", "message": "Traccar listener active. Waiting for coordinates."}

    spd = speed if speed is not None else (payload.speed if payload else None)
    course_val = bearing if bearing is not None else (payload.course if payload and payload.course is not None else (payload.bearing if payload else None))
    alt = altitude if altitude is not None else (payload.altitude if payload else None)
    acc = accuracy if accuracy is not None else (payload.accuracy if payload else None)
    battery_val = batt if batt is not None else (payload.battery if payload and payload.battery is not None else (payload.batt if payload else None))
    is_charging = charge if charge is not None else (payload.charge if payload else None)

    pos = process_traccar_ping(
        device_id=dev_id,
        lat=latitude,
        lon=longitude,
        timestamp=timestamp or (payload.timestamp if payload else None),
        speed=spd,
        bearing=course_val,
        altitude=alt,
        accuracy=acc,
        batt=battery_val,
        charge=is_charging
    )

    # Broadcast position update to all live vehicle listeners
    await manager.broadcast_vehicle({
        "type": "traccar_position",
        "position": pos.model_dump()
    })

    return {"status": "success", "device_id": dev_id, "position": pos.model_dump()}


@app.get("/api/devices")
def traccar_devices():
    """Traccar REST API: List all registered GPS tracking devices."""
    return get_all_devices()


@app.get("/api/positions")
def traccar_positions():
    """Traccar REST API: List latest positions for all devices."""
    return get_all_positions()


@app.get("/api/positions/history")
def traccar_position_history(deviceId: str = Query("OP-TRACKER-01")):
    """Traccar REST API: Return position trail history for trajectory breadcrumbs."""
    return get_position_history(deviceId)


@app.get("/lots")
def list_lots(city: Optional[str] = None):
    """Returns all parking lots for operators and selectors."""
    with get_db() as conn:
        if not conn:
            result = []
            for item in FALLBACK_LOTS:
                if city and item.get("city") != city:
                    continue
                st = lot_status(item["free_spots"], item["capacity"], item.get("updated_at"))
                score, level = get_confidence(item.get("source"), item.get("updated_at"))
                result.append({
                    "id": item["id"],
                    "name": item["name"],
                    "city": item.get("city", "Bengaluru"),
                    "capacity": item["capacity"],
                    "price_note": item["price_note"],
                    "lat": item["lat"],
                    "lon": item["lon"],
                    "free_spots": item["free_spots"],
                    "status": st,
                    "confidence_score": score,
                    "confidence": level,
                    "updated_at": item.get("updated_at").isoformat() if item.get("updated_at") else None,
                    "updated_human": human_time_ago(item.get("updated_at")),
                })
            return result

        with conn.cursor() as cur:
            if city:
                cur.execute(
                    """
                    SELECT l.id, l.name, l.city, l.capacity, l.price_note, l.source,
                           ST_Y(l.geom::geometry) AS lat, ST_X(l.geom::geometry) AS lon,
                           a.free_spots, a.source as availability_source, a.updated_at
                    FROM parking_lots l
                    LEFT JOIN LATERAL (
                        SELECT * FROM availability WHERE lot_id = l.id
                        ORDER BY updated_at DESC LIMIT 1
                    ) a ON true
                    WHERE l.city = %s
                    ORDER BY l.id ASC
                    """,
                    (city,)
                )
            else:
                cur.execute(
                    """
                    SELECT l.id, l.name, l.city, l.capacity, l.price_note, l.source,
                           ST_Y(l.geom::geometry) AS lat, ST_X(l.geom::geometry) AS lon,
                           a.free_spots, a.source as availability_source, a.updated_at
                    FROM parking_lots l
                    LEFT JOIN LATERAL (
                        SELECT * FROM availability WHERE lot_id = l.id
                        ORDER BY updated_at DESC LIMIT 1
                    ) a ON true
                    ORDER BY l.id ASC
                    """
                )
            rows = cur.fetchall()

    result = []
    for row in rows:
        st = lot_status(row["free_spots"], row["capacity"], row["updated_at"])
        score, level = get_confidence(row["availability_source"], row["updated_at"])
        result.append({
            "id": row["id"],
            "name": row["name"],
            "city": row["city"],
            "capacity": row["capacity"],
            "price_note": row["price_note"],
            "lat": row["lat"],
            "lon": row["lon"],
            "free_spots": row["free_spots"],
            "status": st,
            "confidence_score": score,
            "confidence": level,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "updated_human": human_time_ago(row["updated_at"]),
        })
    return result


@app.get("/lots/nearby")
def get_nearby_lots(
    lat: float = Query(..., description="Latitude of user/map center"),
    lon: float = Query(..., description="Longitude of user/map center"),
    radius: float = Query(5000.0, description="Search radius in meters (default 5000m)"),
):
    """
    Core PostGIS query to retrieve lots within radius, ordered by distance,
    with latest availability status and confidence score.
    """
    query = """
    SELECT l.id, l.osm_ref, l.name, l.capacity, l.price_note, l.city,
           ST_Y(l.geom::geometry) AS lat, ST_X(l.geom::geometry) AS lon,
           ST_Distance(l.geom, ST_MakePoint(%s, %s)::geography) AS distance_meters,
           a.free_spots, a.source, a.updated_at
    FROM parking_lots l
    LEFT JOIN LATERAL (
        SELECT * FROM availability WHERE lot_id = l.id
        ORDER BY updated_at DESC LIMIT 1
    ) a ON true
    WHERE ST_DWithin(l.geom, ST_MakePoint(%s, %s)::geography, %s)
    ORDER BY distance_meters ASC
    LIMIT 50;
    """
    conn = get_db()
    if conn:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(query, (lon, lat, lon, lat, radius))
                    rows = cur.fetchall()

            results = []
            for r in rows:
                st = lot_status(r["free_spots"], r["capacity"], r["updated_at"])
                conf_score, conf_level = get_confidence(r["source"], r["updated_at"])
                results.append({
                    "id": r["id"],
                    "osm_ref": r["osm_ref"],
                    "name": r["name"] or f"Parking Lot #{r['id']}",
                    "city": r["city"],
                    "capacity": r["capacity"] or 50,
                    "price_note": r["price_note"] or "Standard parking rates",
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "distance_meters": round(r["distance_meters"], 1),
                    "free_spots": r["free_spots"],
                    "source": r["source"] or "unknown",
                    "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                    "updated_human": human_time_ago(r["updated_at"]),
                    "status": st,
                    "confidence_score": conf_score,
                    "confidence": conf_level,
                })
            return results
        except Exception as e:
            print(f"Database query error: {e}. Falling back to in-memory store.")

    # High-availability fallback
    results = []
    for lot in FALLBACK_LOTS:
        dist = haversine_distance_meters(lat, lon, lot["lat"], lot["lon"])
        if dist <= radius or len(results) < 10:
            st = lot_status(lot["free_spots"], lot["capacity"], lot["updated_at"])
            conf_score, conf_level = get_confidence(lot["source"], lot["updated_at"])
            results.append({
                "id": lot["id"],
                "osm_ref": lot["osm_ref"],
                "name": lot["name"],
                "city": lot["city"],
                "capacity": lot["capacity"],
                "price_note": lot["price_note"],
                "lat": lot["lat"],
                "lon": lot["lon"],
                "distance_meters": round(dist, 1),
                "free_spots": lot["free_spots"],
                "source": lot["source"],
                "updated_at": lot["updated_at"].isoformat(),
                "updated_human": human_time_ago(lot["updated_at"]),
                "status": st,
                "confidence_score": conf_score,
                "confidence": conf_level,
            })
    results.sort(key=lambda x: x["distance_meters"])
    return results[:50]


@app.get("/lots/{lot_id}")
def get_lot_detail(lot_id: int):
    """Returns full details of a specific parking lot, latest status, and recent reports."""
    with get_db() as conn:
        if not conn:
            lot = next((item for item in FALLBACK_LOTS if item["id"] == lot_id), None)
            if not lot:
                raise HTTPException(status_code=404, detail="Parking lot not found")
            st = lot_status(lot["free_spots"], lot["capacity"], lot.get("updated_at"))
            score, level = get_confidence(lot.get("source"), lot.get("updated_at"))
            cap = lot["capacity"] or 50
            free = lot["free_spots"]
            telemetry = get_lot_telemetry(lot["id"], total_capacity=cap, free_spots=free)
            return {
                "id": lot["id"],
                "osm_ref": lot.get("osm_ref", f"way/blr_{lot_id}"),
                "name": lot["name"] or f"Parking #{lot['id']}",
                "city": lot.get("city", "Bengaluru"),
                "capacity": cap,
                "price_note": lot["price_note"] or "Standard parking rates",
                "lat": lot["lat"],
                "lon": lot["lon"],
                "free_spots": free,
                "source": lot.get("source", "sensor"),
                "updated_at": lot.get("updated_at").isoformat() if lot.get("updated_at") else None,
                "updated_human": human_time_ago(lot.get("updated_at")),
                "status": st,
                "confidence_score": score,
                "confidence": level,
                "recent_reports": [],
                "telemetry": telemetry
            }

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.id, l.osm_ref, l.name, l.city, l.capacity, l.price_note, l.source,
                       ST_Y(l.geom::geometry) AS lat, ST_X(l.geom::geometry) AS lon,
                       a.free_spots, a.source as availability_source, a.updated_at
                FROM parking_lots l
                LEFT JOIN LATERAL (
                    SELECT * FROM availability WHERE lot_id = l.id
                    ORDER BY updated_at DESC LIMIT 1
                ) a ON true
                WHERE l.id = %s
                """,
                (lot_id,)
            )
            lot = cur.fetchone()
            if not lot:
                raise HTTPException(status_code=404, detail="Parking lot not found")

            # Fetch last 5 reports
            cur.execute(
                """
                SELECT kind, created_at FROM reports
                WHERE lot_id = %s
                ORDER BY created_at DESC LIMIT 5
                """,
                (lot_id,)
            )
            reports = cur.fetchall()

    st = lot_status(lot["free_spots"], lot["capacity"], lot["updated_at"])
    conf_score, conf_level = get_confidence(lot["availability_source"], lot["updated_at"])
    cap = lot["capacity"] or 50
    free = lot["free_spots"]
    telemetry = get_lot_telemetry(lot["id"], total_capacity=cap, free_spots=free)

    return {
        "id": lot["id"],
        "osm_ref": lot["osm_ref"],
        "name": lot["name"] or f"Parking #{lot['id']}",
        "city": lot["city"],
        "capacity": cap,
        "price_note": lot["price_note"] or "Standard parking rates",
        "lat": lot["lat"],
        "lon": lot["lon"],
        "free_spots": free,
        "source": lot["availability_source"] or "unknown",
        "updated_at": lot["updated_at"].isoformat() if lot["updated_at"] else None,
        "updated_human": human_time_ago(lot["updated_at"]),
        "status": st,
        "confidence_score": conf_score,
        "confidence": conf_level,
        "recent_reports": [
            {"kind": r["kind"], "time": human_time_ago(r["created_at"])} for r in reports
        ],
        "telemetry": telemetry
    }


@app.get("/lots/{lot_id}/telemetry")
def get_lot_telemetry_endpoint(lot_id: int):
    """
    Returns real-time Industrial IoT (IIoT) telemetry for the lot:
    - Zone breakdown (Zone A, B, C, D)
    - EV Charging spots available
    - Dynamic Pricing Factor (0.8x - 1.5x)
    - Weather, traffic levels, and sensor readings (ultrasonic, pressure, noise)
    """
    lot = None
    with get_db() as conn:
        if conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT capacity, (SELECT free_spots FROM availability WHERE lot_id = %s ORDER BY updated_at DESC LIMIT 1) as free_spots FROM parking_lots WHERE id = %s",
                    (lot_id, lot_id)
                )
                lot = cur.fetchone()

    cap = lot["capacity"] if lot and lot.get("capacity") else 100
    free = lot["free_spots"] if lot and lot.get("free_spots") is not None else None
    return get_lot_telemetry(lot_id, total_capacity=cap, free_spots=free)


@app.put("/lots/{lot_id}")
def update_lot_details(
    lot_id: int,
    payload: LotEditPayload,
    x_api_key: Optional[str] = Header(None)
):
    """Allows operator to update lot name, capacity, and pricing note."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

    fields = []
    values = []
    if payload.name is not None:
        fields.append("name = %s")
        values.append(payload.name)
    if payload.capacity is not None:
        fields.append("capacity = %s")
        values.append(payload.capacity)
    if payload.price_note is not None:
        fields.append("price_note = %s")
        values.append(payload.price_note)
    if payload.city is not None:
        fields.append("city = %s")
        values.append(payload.city)

    if not fields:
        return {"status": "no change"}

    values.append(lot_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE parking_lots SET {', '.join(fields)} WHERE id = %s RETURNING id",
                tuple(values)
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Lot not found")
            conn.commit()

    return {"status": "updated", "lot_id": lot_id}


@app.post("/lots/{lot_id}/availability", status_code=status.HTTP_200_OK)
async def update_availability(
    lot_id: int,
    payload: AvailabilityPayload,
    x_api_key: Optional[str] = Header(None)
):
    """
    Operator or sensor sends free spot count.
    Requires valid x-api-key header.
    Inserts availability and notifies connected WebSockets immediately.
    """
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid x-api-key header"
        )

    with get_db() as conn:
        if not conn:
            lot = next((item for item in FALLBACK_LOTS if item["id"] == lot_id), None)
            if not lot:
                raise HTTPException(status_code=404, detail="Parking lot not found")
            lot["free_spots"] = payload.free_spots
            lot["source"] = payload.source
            lot["updated_at"] = datetime.now(timezone.utc)
            now = lot["updated_at"]
        else:
            with conn.cursor() as cur:
                # Check lot exists
                cur.execute("SELECT id, name, capacity FROM parking_lots WHERE id = %s", (lot_id,))
                lot = cur.fetchone()
                if not lot:
                    raise HTTPException(status_code=404, detail="Parking lot not found")

                cur.execute(
                    """
                    INSERT INTO availability (lot_id, free_spots, source, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    RETURNING id, updated_at
                    """,
                    (lot_id, payload.free_spots, payload.source)
                )
                row = cur.fetchone()
                conn.commit()
            now = row["updated_at"]
    st = lot_status(payload.free_spots, lot["capacity"], now)
    conf_score, conf_level = get_confidence(payload.source, now)

    event_data = {
        "type": "availability_update",
        "lot_id": lot_id,
        "name": lot["name"],
        "free_spots": payload.free_spots,
        "capacity": lot["capacity"],
        "status": st,
        "source": payload.source,
        "updated_at": now.isoformat(),
        "updated_human": human_time_ago(now),
        "confidence_score": conf_score,
        "confidence": conf_level,
    }

    # Broadcast to local subscribers
    await manager.broadcast_lot(lot_id, event_data)

    # Publish to Redis channel if available
    if redis_client:
        try:
            await redis_client.publish(f"lot:{lot_id}", json.dumps(event_data))
        except Exception as e:
            print(f"Redis publish error: {e}")

    return {
        "status": "success",
        "lot_id": lot_id,
        "free_spots": payload.free_spots,
        "status_label": st,
        "confidence": conf_level
    }


# Rate limiting dictionary: (reporter_id, lot_id) -> timestamp
REPORTS_RATE_LIMIT: Dict[tuple, datetime] = {}


@app.post("/lots/{lot_id}/reports", status_code=status.HTTP_201_CREATED)
async def submit_crowdsourced_report(lot_id: int, payload: ReportPayload):
    """
    Step 13: Drivers submit crowdsourced report:
    - got_spot, lot_full, or has_space
    - Rate limited to 1 report per user per lot per hour
    - Adjusts availability estimate if sensor/operator data is absent
    """
    if payload.kind not in ("got_spot", "lot_full", "has_space"):
        raise HTTPException(status_code=400, detail="Invalid report kind. Must be got_spot, lot_full, or has_space")

    key = (payload.reporter_id, lot_id)
    now = datetime.now(timezone.utc)
    if key in REPORTS_RATE_LIMIT:
        last_reported = REPORTS_RATE_LIMIT[key]
        if (now - last_reported) < timedelta(hours=1):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded: 1 report per lot per hour per user."
            )

    REPORTS_RATE_LIMIT[key] = now

    with get_db() as conn:
        if not conn:
            lot = next((item for item in FALLBACK_LOTS if item["id"] == lot_id), None)
            if not lot:
                raise HTTPException(status_code=404, detail="Parking lot not found")
            cap = lot["capacity"] or 50
            if payload.kind == "lot_full":
                lot["free_spots"] = 0
            elif payload.kind == "has_space":
                lot["free_spots"] = max(5, int(cap * 0.35))
            elif payload.kind == "got_spot":
                lot["free_spots"] = max(0, (lot["free_spots"] or 10) - 1)
            lot["updated_at"] = now
            return {
                "message": f"Report '{payload.kind}' recorded successfully",
                "lot_id": lot_id,
                "status": "received"
            }

        with conn.cursor() as cur:
            cur.execute("SELECT id, name, capacity FROM parking_lots WHERE id = %s", (lot_id,))
            lot = cur.fetchone()
            if not lot:
                raise HTTPException(status_code=404, detail="Parking lot not found")

            cur.execute(
                """
                INSERT INTO reports (lot_id, kind, reporter_id, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (lot_id, payload.kind, payload.reporter_id)
            )

            # Check latest availability source and age
            cur.execute(
                """
                SELECT free_spots, source, updated_at FROM availability
                WHERE lot_id = %s
                ORDER BY updated_at DESC LIMIT 1
                """,
                (lot_id,)
            )
            latest = cur.fetchone()

            capacity = lot["capacity"] or 50
            # If no recent sensor or operator update in the last 15 minutes, crowd report updates availability
            update_avail = False
            new_free = 0
            if not latest or (latest["source"] == "crowd") or (now - latest["updated_at"].replace(tzinfo=timezone.utc)).total_seconds() > 900:
                update_avail = True
                curr_free = latest["free_spots"] if latest else int(capacity * 0.3)
                if payload.kind == "lot_full":
                    new_free = 0
                elif payload.kind == "has_space":
                    new_free = max(5, int(capacity * 0.35))
                elif payload.kind == "got_spot":
                    new_free = max(0, curr_free - 1 if curr_free is not None else int(capacity * 0.2))

                cur.execute(
                    """
                    INSERT INTO availability (lot_id, free_spots, source, updated_at)
                    VALUES (%s, %s, 'crowd', NOW())
                    """,
                    (lot_id, new_free)
                )

            conn.commit()

    if update_avail:
        st = lot_status(new_free, lot["capacity"], now)
        conf_score, conf_level = get_confidence("crowd", now)
        event_data = {
            "type": "availability_update",
            "lot_id": lot_id,
            "name": lot["name"],
            "free_spots": new_free,
            "capacity": lot["capacity"],
            "status": st,
            "source": "crowd",
            "updated_at": now.isoformat(),
            "updated_human": "Just now",
            "confidence_score": conf_score,
            "confidence": conf_level,
        }
        await manager.broadcast_lot(lot_id, event_data)

    return {"status": "received", "kind": payload.kind, "lot_id": lot_id}


# --------------------------------------------------------------------------
# WebSockets: Real-Time Lot Updates & Vehicle Tracking
# --------------------------------------------------------------------------

@app.websocket("/ws/lots/{lot_id}")
async def websocket_lot_updates(websocket: WebSocket, lot_id: int):
    """
    Step 11: Real-time status subscription for a chosen parking lot.
    The app receives live changes without refreshing the page.
    """
    await manager.connect_lot(lot_id, websocket)
    try:
        # Send initial status right away
        detail = get_lot_detail(lot_id)
        await websocket.send_json({
            "type": "initial_state",
            "lot": detail
        })
        while True:
            # Keep socket alive and accept ping/pong or queries
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect_lot(lot_id, websocket)
    except Exception:
        manager.disconnect_lot(lot_id, websocket)


# Active trip alert states: trip_id -> bool (has alert been sent)
TRIP_ALERTED: Dict[str, bool] = {}


def haversine_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@app.websocket("/ws/vehicle")
async def websocket_vehicle_tracking(websocket: WebSocket):
    """
    Steps 9 & 14:
    - Receives driver live position: {lat, lon, speed, t, destination_lot_id, trip_id}
    - Does NOT persist location history (privacy protection)
    - Triggers arrival notification when vehicle is within 1.5 km of destination (alert sent once per trip)
    - Triggers proactive reroute notification if destination lot becomes Full
    """
    await manager.connect_vehicle(websocket)
    current_trip_id = None

    try:
        while True:
            message = await websocket.receive_json()
            lat = message.get("lat")
            lon = message.get("lon")
            dest_lot_id = message.get("destination_lot_id")
            trip_id = message.get("trip_id") or "default_trip"
            current_trip_id = trip_id

            if lat is None or lon is None:
                continue

            # Ingest to Traccar GPS telemetry engine
            trac_pos = process_traccar_ping(
                device_id=message.get("device_id") or "OP-TRACKER-01",
                lat=lat,
                lon=lon,
                speed=message.get("speed"),
                bearing=message.get("bearing") or message.get("course"),
                altitude=message.get("altitude"),
                accuracy=message.get("accuracy"),
                batt=message.get("battery") or message.get("batt"),
                charge=message.get("charge")
            )

            # If user has a selected destination lot, evaluate arrival & availability
            if dest_lot_id:
                try:
                    with get_db() as conn:
                        with conn.cursor() as cur:
                            # Check destination lot
                            cur.execute(
                                """
                                SELECT l.id, l.name, l.capacity,
                                       ST_Y(l.geom::geometry) AS dest_lat,
                                       ST_X(l.geom::geometry) AS dest_lon,
                                       ST_Distance(l.geom, ST_MakePoint(%s, %s)::geography) AS distance_meters,
                                       a.free_spots, a.source, a.updated_at
                                FROM parking_lots l
                                LEFT JOIN LATERAL (
                                    SELECT * FROM availability WHERE lot_id = l.id
                                    ORDER BY updated_at DESC LIMIT 1
                                ) a ON true
                                WHERE l.id = %s
                                """,
                                (lon, lat, dest_lot_id)
                            )
                            dest_lot = cur.fetchone()

                            if dest_lot:
                                dist = dest_lot["distance_meters"]
                                dest_status = lot_status(dest_lot["free_spots"], dest_lot["capacity"], dest_lot["updated_at"])

                                # 1. Check if destination became full -> trigger reroute alert!
                                if dest_status == "full":
                                    # Find next-nearest available lot
                                    cur.execute(
                                        """
                                        SELECT l.id, l.name, l.capacity, l.price_note,
                                               ST_Y(l.geom::geometry) AS lat, ST_X(l.geom::geometry) AS lon,
                                               ST_Distance(l.geom, ST_MakePoint(%s, %s)::geography) AS distance_meters,
                                               a.free_spots, a.source, a.updated_at
                                        FROM parking_lots l
                                        LEFT JOIN LATERAL (
                                            SELECT * FROM availability WHERE lot_id = l.id
                                            ORDER BY updated_at DESC LIMIT 1
                                        ) a ON true
                                        WHERE l.id != %s
                                        AND ST_DWithin(l.geom, ST_MakePoint(%s, %s)::geography, 3000)
                                        ORDER BY distance_meters ASC
                                        LIMIT 5
                                        """,
                                        (lon, lat, dest_lot_id, lon, lat)
                                    )
                                    alternatives = cur.fetchall()
                                    alt_lot = None
                                    for alt in alternatives:
                                        ast = lot_status(alt["free_spots"], alt["capacity"], alt["updated_at"])
                                        if ast in ("available", "filling_up") and alt["free_spots"] > 0:
                                            alt_lot = alt
                                            break

                                    if alt_lot:
                                        await websocket.send_json({
                                            "type": "lot_full_reroute",
                                            "message": f"Heads up! {dest_lot['name']} is now FULL. Would you like to switch to {alt_lot['name']} ({alt_lot['free_spots']} spots free)?",
                                            "original_lot_id": dest_lot_id,
                                            "alternative_lot": {
                                                "id": alt_lot["id"],
                                                "name": alt_lot["name"],
                                                "free_spots": alt_lot["free_spots"],
                                                "lat": alt_lot["lat"],
                                                "lon": alt_lot["lon"],
                                                "distance_meters": round(alt_lot["distance_meters"])
                                            }
                                        })

                                # 2. Step 14 Arrival Notification: within 1.5 km (1500m) and alert not yet sent
                                if dist <= 1500 and not TRIP_ALERTED.get(trip_id, False):
                                    TRIP_ALERTED[trip_id] = True
                                    # Rank best option
                                    conf_score, conf_level = get_confidence(dest_lot["source"], dest_lot["updated_at"])
                                    spots = dest_lot["free_spots"]
                                    if spots is not None and spots > 0:
                                        arrival_msg = f"Arriving in 1.5 km! {dest_lot['name']} has {spots} spots available."
                                    else:
                                        arrival_msg = f"Arriving near {dest_lot['name']}. Parking status: {dest_status}."

                                    await websocket.send_json({
                                        "type": "arrival_alert",
                                        "trip_id": trip_id,
                                        "distance_meters": round(dist),
                                        "message": arrival_msg,
                                        "lot": {
                                            "id": dest_lot["id"],
                                            "name": dest_lot["name"],
                                            "status": dest_status,
                                            "free_spots": spots,
                                            "lat": dest_lot["dest_lat"],
                                            "lon": dest_lot["dest_lon"]
                                        }
                                    })
                except Exception as db_err:
                    print(f"Vehicle location check error: {db_err}")

            # Send ack with distance
            await websocket.send_json({
                "type": "vehicle_ack",
                "t": message.get("t")
            })

    except WebSocketDisconnect:
        manager.disconnect_vehicle(websocket)
    except Exception:
        manager.disconnect_vehicle(websocket)
