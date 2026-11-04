# OpenPark API Specification

This document details the REST API and WebSocket protocols for OpenPark.

## Base URL
- Local: `http://localhost:8000`
- WebSockets: `ws://localhost:8000`

---

## Authentication
Sensitive operator and sensor endpoints require the `x-api-key` header:
```http
x-api-key: dev-key
```

---

## REST Endpoints

### 1. Health Check
- **GET** `/health`
- **Response**:
  ```json
  {
    "status": "healthy",
    "service": "OpenPark API",
    "timestamp": "2026-11-04T05:00:00Z"
  }
  ```

### 2. Search Nearby Parking Lots
- **GET** `/lots/nearby?lat={lat}&lon={lon}&radius={radius_in_meters}`
- **Parameters**:
  - `lat` (float, required): User or map center latitude (e.g. `12.9716`)
  - `lon` (float, required): User or map center longitude (e.g. `77.5946`)
  - `radius` (float, optional, default `5000`): Search radius in meters
- **Response**:
  ```json
  [
    {
      "id": 1,
      "osm_ref": "way/blr_ub_city",
      "name": "UB City Multi-Level Car Parking",
      "city": "Bengaluru",
      "capacity": 1200,
      "price_note": "₹50/hr",
      "lat": 12.9719,
      "lon": 77.5958,
      "distance_meters": 350.2,
      "free_spots": 45,
      "source": "sensor",
      "updated_at": "2026-11-04T05:00:00Z",
      "updated_human": "Just now",
      "status": "available",
      "confidence_score": 0.95,
      "confidence": "High"
    }
  ]
  ```

### 3. Get Single Lot Details
- **GET** `/lots/{id}`
- **Response**: Lot object including `recent_reports` array.

### 4. Update Lot Availability
- **POST** `/lots/{id}/availability`
- **Headers**: `x-api-key: dev-key`
- **Request Body**:
  ```json
  {
    "free_spots": 18,
    "source": "sensor"
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "lot_id": 1,
    "free_spots": 18,
    "status_label": "available",
    "confidence": "High"
  }
  ```

### 5. Submit Crowdsource Report
- **POST** `/lots/{id}/reports`
- **Request Body**:
  ```json
  {
    "kind": "got_spot",
    "reporter_id": "client_abc123"
  }
  ```
- **Valid `kind` values**: `got_spot`, `lot_full`, `has_space`.
- **Rate Limit**: 1 report per user per lot per hour.

### 6. Edit Lot Details
- **PUT** `/lots/{id}`
- **Headers**: `x-api-key: dev-key`
- **Request Body**:
  ```json
  {
    "name": "Updated Lot Name",
    "capacity": 150,
    "price_note": "₹40/hr"
  }
  ```

---

## WebSockets

### 1. Lot Status Stream
- **Endpoint**: `WS /ws/lots/{lot_id}`
- Pushes live `availability_update` events whenever a sensor, operator, or crowd report changes spot counts.
- **Message format**:
  ```json
  {
    "type": "availability_update",
    "lot_id": 1,
    "name": "UB City Multi-Level Car Parking",
    "free_spots": 22,
    "capacity": 1200,
    "status": "available",
    "source": "sensor",
    "updated_at": "2026-11-04T05:02:00Z",
    "updated_human": "Just now",
    "confidence_score": 0.95,
    "confidence": "High"
  }
  ```

### 2. Vehicle Location Tracking & Arrival Notifications
- **Endpoint**: `WS /ws/vehicle`
- **Driver sends**:
  ```json
  {
    "lat": 12.9716,
    "lon": 77.5850,
    "speed": 28,
    "destination_lot_id": 1,
    "trip_id": "trip_xyz789",
    "t": 1730700000000
  }
  ```
- **Server pushes**:
  - `arrival_alert`: Triggered once per trip when within 1.5 km of destination lot.
  - `lot_full_reroute`: Triggered if destination lot becomes Full while en route, suggesting the nearest alternative.
