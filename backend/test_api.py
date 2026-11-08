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

    # 1. Unknown if free is None
    assert lot_status(None, 100, now) == "unknown"

    # 2. Unknown if stale > 180 minutes
    stale_time = now - timedelta(minutes=200)
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

    res_det = client.get("/health/details")
    assert res_det.status_code == 200
    details = res_det.json()
    assert details["status"] == "healthy"
    assert "database" in details
    assert "places_indexed" in details["database"]


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


def test_lot_telemetry_endpoint():
    res = client.get("/lots/1/telemetry")
    assert res.status_code == 200
    tel = res.json()
    assert "zones" in tel
    assert "Zone A" in tel["zones"]
    assert "dynamic_pricing" in tel
    assert "factor" in tel["dynamic_pricing"]
    assert "traffic_level" in tel
    assert "sensors" in tel
    assert "status" in tel["sensors"]
    assert "ev_charging" in tel


def test_maplibre_config_endpoints():
    res = client.get("/config/map")
    assert res.status_code == 200
    data = res.json()
    assert data["engine"] == "MapLibre GL JS"
    assert data["requires_token"] is False
    assert "carto-dark" in data["supported_styles"]

    # Test updating style configuration
    post_res = client.post("/config/map", json={"default_style": "carto-voyager"})
    assert post_res.status_code == 200
    assert post_res.json()["default_style"] == "carto-voyager"
    assert post_res.json()["requires_token"] is False

    # Test ultra-detail vector style endpoint
    style_res = client.get("/api/map/style/ultra-detail")
    assert style_res.status_code == 200
    style_data = style_res.json()
    assert style_data["version"] == 8
    assert len(style_data["layers"]) > 50

    # Test reverse building lookup endpoint
    lookup_res = client.get("/api/places/lookup?lat=12.9716&lon=77.5946")
    assert lookup_res.status_code == 200
    lookup_data = lookup_res.json()
    assert lookup_data["status"] == "ok"
    assert "place" in lookup_data
    assert "name" in lookup_data["place"]


def test_mappls_rest_api_endpoints():
    # 1. Test Mappls config endpoint (delegated to Traccar)
    res = client.get("/config/mappls")
    assert res.status_code == 200
    data = res.json()
    assert "Traccar" in data["engine"]
    assert "has_rest_key" in data

    # 2. Test updating Mappls REST key
    post_res = client.post("/config/mappls", json={"mappls_rest_key": "test_dummy_mappls_key_12345"})
    assert post_res.status_code == 200
    assert post_res.json()["has_rest_key"] is True

    # 3. Test Mappls AutoSuggest endpoint
    sugg_res = client.get("/api/mappls/autosuggest?query=MG%20Road&lat=12.9716&lon=77.5946")
    assert sugg_res.status_code == 200
    sugg_data = sugg_res.json()
    assert sugg_data["status"] == "ok"
    assert len(sugg_data["results"]) >= 1
    assert "name" in sugg_data["results"][0]
    assert "lat" in sugg_data["results"][0]

    # 4. Test Mappls Route Directions endpoint
    route_res = client.get("/api/mappls/route?start_lat=12.9716&start_lon=77.5946&dest_lat=12.9750&dest_lon=77.6000")
    assert route_res.status_code == 200
    route_data = route_res.json()
    assert route_data["status"] == "ok"
    assert len(route_data["coordinates"]) >= 2
    assert "steps" in route_data
    assert "distance_km" in route_data


def test_traccar_endpoints():
    # 1. Test Traccar Client GET protocol (OsmAnd format)
    res = client.get("/api/traccar?id=OP-TRACKER-01&lat=12.9719&lon=77.5958&speed=45.2&bearing=120.0&altitude=922&batt=95")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["device_id"] == "OP-TRACKER-01"
    assert data["position"]["latitude"] == 12.9719
    assert data["position"]["speed"] == 45.2

    # 2. Test Traccar Client POST protocol (JSON)
    post_res = client.post("/api/traccar", json={
        "id": "OP-TRACKER-02",
        "lat": 12.9740,
        "lon": 77.6074,
        "speed": 30.0,
        "bearing": 90.0,
        "altitude": 918.5,
        "accuracy": 3.0,
        "batt": 88.0,
        "charge": True
    })
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "success"

    # 3. Test Traccar /api/devices
    dev_res = client.get("/api/devices")
    assert dev_res.status_code == 200
    devices = dev_res.json()
    assert len(devices) >= 2

    # 4. Test Traccar /api/positions
    pos_res = client.get("/api/positions")
    assert pos_res.status_code == 200
    positions = pos_res.json()
    assert len(positions) >= 2

    # 5. Test Traccar /api/positions/history
    hist_res = client.get("/api/positions/history?deviceId=OP-TRACKER-01")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1

    # 6. Test Traccar official /api/server info
    srv_res = client.get("/api/server")
    assert srv_res.status_code == 200
    assert "version" in srv_res.json()
    assert srv_res.json()["registration"] is True

    # 7. Test Traccar official /api/session
    sess_res = client.get("/api/session")
    assert sess_res.status_code == 200
    assert "id" in sess_res.json()

    # 8. Test specific device and position lookup
    d_res = client.get("/api/devices/OP-TRACKER-01")
    assert d_res.status_code == 200
    assert d_res.json()["uniqueId"] == "OP-TRACKER-01"

    p_res = client.get("/api/positions/OP-TRACKER-01")
    assert p_res.status_code == 200
    assert p_res.json()["deviceId"] == "OP-TRACKER-01"

    # 9. Test root OsmAnd ingestion
    root_ping = client.get("/?id=OP-TRACKER-01&lat=12.9716&lon=77.5946&speed=20.0&bearing=45.0")
    assert root_ping.status_code == 200
    assert root_ping.text == "OK"

    # 10. Test Traccar OSRM Driving Road Routing
    route_res = client.get("/api/traccar/route?start_lat=12.9716&start_lon=77.5946&dest_lat=12.9750&dest_lon=77.6000")
    assert route_res.status_code == 200
    route_data = route_res.json()
    assert route_data["status"] == "ok"
    assert len(route_data["coordinates"]) >= 2
    assert "steps" in route_data
    assert "distance_km" in route_data

    # 11. Test Traccar Places Search (OSM Nominatim + Local Catalog)
    search_res = client.get("/api/traccar/search?query=Koramangala")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["status"] == "ok"
    assert len(search_data["results"]) >= 1
    assert "name" in search_data["results"][0]

    # 12. Test Traccar Device Road Trail
    trail_res = client.get("/api/traccar/devices/OP-TRACKER-01/trail")
    assert trail_res.status_code == 200
    trail_data = trail_res.json()
    assert trail_data["type"] == "FeatureCollection"
    assert len(trail_data["features"]) >= 1
    assert trail_data["features"][0]["geometry"]["type"] == "LineString"


def test_osm_overpass_features():
    # 1. Test full features endpoint
    res = client.get("/api/osm/overpass")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 700

    # 2. Test category filtering (parking, fuel, toll)
    res_parking = client.get("/api/osm/overpass?category=parking")
    assert res_parking.status_code == 200
    parking_data = res_parking.json()
    assert len(parking_data["features"]) >= 700
    assert parking_data["features"][0]["geometry"]["type"] == "Polygon"
    # Ensure [lon, lat] ordering
    first_pt = parking_data["features"][0]["geometry"]["coordinates"][0][0]
    assert 70.0 <= first_pt[0] <= 85.0  # Longitude
    assert 10.0 <= first_pt[1] <= 20.0  # Latitude

    res_fuel = client.get("/api/osm/overpass?category=fuel")
    assert res_fuel.status_code == 200
    fuel_data = res_fuel.json()
    assert len(fuel_data["features"]) >= 10
    assert fuel_data["features"][0]["geometry"]["type"] == "Point"

    res_toll = client.get("/api/osm/overpass?category=toll")
    assert res_toll.status_code == 200
    toll_data = res_toll.json()
    assert len(toll_data["features"]) >= 10
    assert toll_data["features"][0]["geometry"]["type"] == "Point"


def test_websocket_ping_pong():
    with client.websocket_connect("/ws/vehicle") as ws:
        # Send text ping
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"

        # Send JSON ping
        ws.send_json({"type": "ping", "timestamp": 123456789})
        json_data = ws.receive_json()
        assert json_data["type"] == "pong"
        assert "time" in json_data


def test_geofabrik_endpoints():
    # 1. Test Geofabrik status endpoint
    status_res = client.get("/api/geofabrik/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "available"
    assert "Geofabrik" in status_data["provider"]
    assert status_data["available_regions_count"] >= 2
    assert len(status_data["local_files"]) >= 1

    # 2. Test Geofabrik list regions
    regions_res = client.get("/api/geofabrik/regions")
    assert regions_res.status_code == 200
    regions_data = regions_res.json()
    assert regions_data["status"] == "ok"
    regions = regions_data["regions"]
    assert any(r["id"] == "southern-zone" for r in regions)
    assert any(r["id"] == "india" for r in regions)

    # 3. Test specific region details (Southern Zone - Karnataka / Bengaluru)
    sz_res = client.get("/api/geofabrik/regions/southern-zone")
    assert sz_res.status_code == 200
    sz_data = sz_res.json()
    assert sz_data["status"] == "ok"
    reg = sz_data["region"]
    assert reg["id"] == "southern-zone"
    assert "urls" in reg
    assert "pbf" in reg["urls"]
    assert "poly_url" in reg
    assert reg["has_local_poly"] is True

    # 4. Test 404 for nonexistent region
    not_found_res = client.get("/api/geofabrik/regions/nonexistent-region-xyz")
    assert not_found_res.status_code == 404


def test_google_maps_place_details_enrichment():
    from traccar_service import enrich_place_details

    # 1. Hospital archetype enrichment
    hosp_raw = {"name": "Apollo Speciality Hospital", "category": "Hospital", "badge": "🏥", "lat": 12.895, "lon": 77.598}
    hosp = enrich_place_details(hosp_raw)
    assert hosp["archetype"] == "hospital"
    assert hosp["rating"] >= 4.0 and hosp["rating"] <= 5.0
    assert hosp["reviews_count"] >= 300
    assert "24 hours" in hosp["open_status"].lower()
    assert hosp["is_open"] is True
    assert any("emergency" in a.lower() for a in hosp["amenities"])
    assert any("pharmacy" in a.lower() for a in hosp["amenities"])
    assert hosp["phone"].startswith("+91")
    assert "unsplash" in hosp["banner_url"]
    assert len(hosp["reviews"]) >= 2

    # 2. Cafe archetype enrichment
    cafe_raw = {"name": "Starbucks Coffee", "category": "Cafe", "badge": "☕", "lat": 12.971, "lon": 77.640}
    cafe = enrich_place_details(cafe_raw)
    assert cafe["archetype"] == "cafe"
    assert cafe["rating"] >= 4.0
    assert "₹" in cafe["price_tier"]
    assert any("coffee" in a.lower() for a in cafe["amenities"])
    assert any("wi-fi" in a.lower() for a in cafe["amenities"])
    assert "starbucks" in cafe["website"]
    assert len(cafe["reviews"]) >= 2

    # 3. Restaurant archetype enrichment
    rest_raw = {"name": "Truffles", "category": "Restaurant", "badge": "🍔", "lat": 12.935, "lon": 77.624}
    rest = enrich_place_details(rest_raw)
    assert rest["archetype"] == "restaurant"
    assert any("dine-in" in a.lower() for a in rest["amenities"])
    assert any("delivery" in a.lower() for a in rest["amenities"])

    # 4. Fuel Station archetype enrichment
    fuel_raw = {"name": "Shell Petrol Bunk", "category": "Fuel", "badge": "⛽", "lat": 12.920, "lon": 77.610}
    fuel = enrich_place_details(fuel_raw)
    assert fuel["archetype"] == "fuel"
    assert "24 hours" in fuel["open_status"].lower()
    assert any("ev charging" in a.lower() for a in fuel["amenities"])

    # 5. Verify /api/traccar/search returns fully enriched Google Maps payload
    res = client.get("/api/traccar/search?query=Apollo&lat=12.9716&lon=77.5946")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert len(data["results"]) > 0
    first = data["results"][0]
    assert "rating" in first
    assert "reviews_count" in first
    assert "open_status" in first
    assert "amenities" in first
    assert "banner_url" in first
    assert "reviews" in first


def test_outscraper_endpoints():
    """Verify Outscraper search and reviews endpoints."""
    # Test without API key gives friendly error
    r1 = client.get("/api/outscraper/search?query=Debrecan+House")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "error"
    assert "Outscraper API key not configured" in d1["message"]

    r2 = client.get("/api/outscraper/reviews?query=Debrecan+House")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "error"
    assert "Outscraper API key not configured" in d2["message"]


def test_offline_places_database():
    """Verify local SQLite FTS5 places database search and stats endpoints."""
    # 1. Stats endpoint
    r_stats = client.get("/api/places/stats")
    assert r_stats.status_code == 200
    d_stats = r_stats.json()
    assert d_stats["status"] == "ok"
    assert "stats" in d_stats
    assert d_stats["stats"]["total_places"] > 0

    # 2. Search endpoint
    r_search = client.get("/api/places/search?query=Debrecan")
    assert r_search.status_code == 200
    d_search = r_search.json()
    assert d_search["status"] == "ok"
    assert d_search["total"] >= 1
    found = d_search["results"][0]
    assert "Debrecan" in found["name"]
    assert "Uttarahalli" in found["address"]







