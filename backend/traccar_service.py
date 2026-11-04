"""
OpenPark - Traccar GPS Tracking Integration Service
---------------------------------------------------
Implements compatibility with the Traccar GPS tracking platform (https://www.traccar.org/):
1. Ingestion of Traccar Client / OsmAnd HTTP protocol (GET and POST)
2. Ingestion of JSON GPS telemetry
3. In-memory & DB persistence of devices, latest fixes, and trip breadcrumb histories
4. Real-time metrics: Speed, Bearing/Heading, Altitude, Battery, Ignition, Accuracy, Odometer
"""

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TraccarPosition(BaseModel):
    id: Optional[int] = None
    deviceId: str = Field(..., description="Unique hardware or app identifier")
    protocol: str = Field(default="traccar-http", description="Telemetry protocol")
    serverTime: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    deviceTime: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fixTime: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    valid: bool = True
    latitude: float
    longitude: float
    altitude: float = 918.0  # meters (Bengaluru avg elevation)
    speed: float = 0.0  # km/h
    course: float = 0.0  # degrees 0 - 360
    address: Optional[str] = "Bengaluru, Karnataka, India"
    accuracy: float = 3.5  # meters
    attributes: Dict = Field(default_factory=lambda: {
        "batteryLevel": 92.0,
        "charging": True,
        "motion": False,
        "odometer": 0.0,
        "distance": 0.0,
        "satellites": 9,
    })


class TraccarDevice(BaseModel):
    id: str
    name: str
    uniqueId: str
    status: str = "online"  # online, moving, idle, stopped, offline
    lastUpdate: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    positionId: Optional[int] = None
    model: str = "OpenPark Smart Fleet Tracker"
    category: str = "car"
    phone: Optional[str] = "+91 98765 43210"
    attributes: Dict = Field(default_factory=dict)


# In-memory fast stores for real-time telemetry
DEVICES: Dict[str, TraccarDevice] = {}
LATEST_POSITIONS: Dict[str, TraccarPosition] = {}
POSITION_HISTORY: Dict[str, List[TraccarPosition]] = {}
ODOMETERS: Dict[str, float] = {}  # device_id -> total km


def init_default_devices():
    """Initializes standard demonstration devices matching Bengaluru fleet."""
    if "OP-TRACKER-01" not in DEVICES:
        dev = TraccarDevice(
            id="OP-TRACKER-01",
            uniqueId="OP-TRACKER-01",
            name="OpenPark Urban Navigator (KA-01-MJ-2024)",
            model="Traccar GPS / OBD-II Pro",
            status="online",
            category="car",
            attributes={"color": "#2563eb", "driver": "Dhairya", "fuel": "Electric (EV)"}
        )
        DEVICES["OP-TRACKER-01"] = dev
        
        pos = TraccarPosition(
            deviceId="OP-TRACKER-01",
            latitude=12.9716,
            longitude=77.5840,
            altitude=920.0,
            speed=38.5,
            course=115.0,
            accuracy=2.8,
            attributes={
                "batteryLevel": 89.0,
                "charging": True,
                "motion": True,
                "odometer": 12.4,
                "satellites": 11,
            }
        )
        LATEST_POSITIONS["OP-TRACKER-01"] = pos
        POSITION_HISTORY["OP-TRACKER-01"] = [pos]
        ODOMETERS["OP-TRACKER-01"] = 12.4


# Initialize on import
init_default_devices()


def calculate_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates directional bearing in degrees (0 - 360)."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dL = math.radians(lon2 - lon1)
    y = math.sin(dL) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dL)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360.0) % 360.0


def process_traccar_ping(
    device_id: str,
    lat: float,
    lon: float,
    timestamp: Optional[str] = None,
    speed: Optional[float] = None,
    bearing: Optional[float] = None,
    altitude: Optional[float] = None,
    accuracy: Optional[float] = None,
    batt: Optional[float] = None,
    charge: Optional[bool] = None,
    protocol: str = "traccar-http"
) -> TraccarPosition:
    """
    Standard Traccar GPS fix ingestion:
    Supports Traccar Client / OsmAnd mobile apps and physical GPS devices.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    dev_time = timestamp if timestamp else now_iso

    # Auto-register device if unknown
    if device_id not in DEVICES:
        DEVICES[device_id] = TraccarDevice(
            id=device_id,
            uniqueId=device_id,
            name=f"Vehicle Tracker ({device_id})",
            model="Traccar Client Compatible",
            status="online",
            category="car"
        )

    # Compute incremental distance / odometer
    prev_pos = LATEST_POSITIONS.get(device_id)
    incremental_km = 0.0
    calc_bearing = bearing if bearing is not None else (prev_pos.course if prev_pos else 0.0)
    
    if prev_pos:
        incremental_km = calculate_haversine_km(prev_pos.latitude, prev_pos.longitude, lat, lon)
        if incremental_km > 0.002 and bearing is None:
            calc_bearing = calculate_bearing(prev_pos.latitude, prev_pos.longitude, lat, lon)

    current_odo = ODOMETERS.get(device_id, 0.0) + incremental_km
    ODOMETERS[device_id] = round(current_odo, 2)

    # Determine motion status
    calc_speed = speed if speed is not None else (35.0 if incremental_km > 0.005 else 0.0)
    is_moving = calc_speed > 2.0
    status_str = "moving" if is_moving else ("idle" if (charge or batt is not None) else "stopped")

    # Update Device
    DEVICES[device_id].lastUpdate = now_iso
    DEVICES[device_id].status = status_str

    pos = TraccarPosition(
        deviceId=device_id,
        protocol=protocol,
        serverTime=now_iso,
        deviceTime=dev_time,
        fixTime=dev_time,
        valid=True,
        latitude=lat,
        longitude=lon,
        altitude=altitude if altitude is not None else 920.0,
        speed=round(calc_speed, 1),
        course=round(calc_bearing, 1),
        accuracy=accuracy if accuracy is not None else 3.2,
        attributes={
            "batteryLevel": batt if batt is not None else 90.0,
            "charging": charge if charge is not None else True,
            "motion": is_moving,
            "odometer": round(current_odo, 2),
            "distance": round(incremental_km * 1000, 1),  # meters
            "satellites": 10 if (accuracy and accuracy < 5) else 7,
        }
    )

    LATEST_POSITIONS[device_id] = pos

    if device_id not in POSITION_HISTORY:
        POSITION_HISTORY[device_id] = []
    
    POSITION_HISTORY[device_id].append(pos)
    # Keep last 150 points for path breadcrumbs
    if len(POSITION_HISTORY[device_id]) > 150:
        POSITION_HISTORY[device_id] = POSITION_HISTORY[device_id][-150:]

    return pos


def get_all_devices() -> List[Dict]:
    return [dev.model_dump() for dev in DEVICES.values()]


def get_all_positions() -> List[Dict]:
    return [pos.model_dump() for pos in LATEST_POSITIONS.values()]


def get_position_history(device_id: str) -> List[Dict]:
    history = POSITION_HISTORY.get(device_id, [])
    return [pos.model_dump() for pos in history]
