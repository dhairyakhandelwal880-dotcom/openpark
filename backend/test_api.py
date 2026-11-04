"""
OpenPark API Tests
Tests for status logic, confidence metrics, spatial queries, and API endpoints.
"""

from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from main import app, lot_status, get_confidence

client = TestClient(app)


def test_lot_status_logic():
    now = datetime.now(timezone.utc)

    # 1. Unknown if free or updated_at is None
    assert lot_status(None, 100, now) == "unknown"
    assert lot_status(10, 100, None) == "unknown"

    # 2. Unknown if stale > 30 minutes
    stale_time = now - timedelta(minutes=35)
    assert lot_status(20, 100, stale_time) == "unknown"

    # 3. Full if free == 0
    assert lot_status(0, 100, now) == "full"

    # 4. Filling up if free < 5 or ratio < 0.15
    assert lot_status(3, 100, now) == "filling_up"
    assert lot_status(10, 100, now) == "filling_up"  # 10% < 15%

    # 5. Available otherwise
    assert lot_status(50, 100, now) == "available"


def test_confidence_metrics():
    now = datetime.now(timezone.utc)
    score_sensor, level_sensor = get_confidence("sensor", now)
    assert score_sensor >= 0.90
    assert level_sensor == "High"

    score_crowd, level_crowd = get_confidence("crowd", now)
    assert level_crowd == "Medium"

    old_time = now - timedelta(minutes=45)
    score_old, level_old = get_confidence("sensor", old_time)
    assert level_old in ("Low", "Medium")


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_list_lots():
    res = client.get("/lots")
    assert res.status_code == 200
    lots = res.json()
    assert isinstance(lots, list)
    assert len(lots) > 0


def test_nearby_lots_bengaluru():
    # Bengaluru center coordinates
    res = client.get("/lots/nearby?lat=12.9716&lon=77.5946&radius=5000")
    assert res.status_code == 200
    lots = res.json()
    assert isinstance(lots, list)
    assert len(lots) > 0
    first = lots[0]
    assert "distance_meters" in first
    assert "status" in first
    assert "confidence" in first


def test_update_availability_auth():
    # Unauthorized without header
    res = client.post("/lots/1/availability", json={"free_spots": 42, "source": "sensor"})
    assert res.status_code == 401

    # Authorized with header
    res = client.post(
        "/lots/1/availability",
        json={"free_spots": 42, "source": "sensor"},
        headers={"x-api-key": "dev-key"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["free_spots"] == 42
    assert data["status"] == "success"


def test_crowd_report():
    import uuid
    uid = str(uuid.uuid4())
    res = client.post(
        "/lots/1/reports",
        json={"kind": "got_spot", "reporter_id": uid}
    )
    assert res.status_code == 201
    assert res.json()["status"] == "received"
