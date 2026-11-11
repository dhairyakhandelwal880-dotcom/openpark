# OpenPark 🅿️

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![MapLibre GL](https://img.shields.io/badge/MapLibre%20GL%20JS-4.7-396afc.svg)](https://maplibre.org/maplibre-gl-js/docs/API/)
[![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5%20Overture%20India-003B57.svg)](https://www.sqlite.org/fts5.html)
[![Tests](https://img.shields.io/badge/Tests-22%2F22%20Passing-success.svg)](backend/test_api.py)

**OpenPark** is an open-source smart parking, 1 km AI small-ground finder, India place search, OSRM routing, and Traccar GPS telemetry platform built with **FastAPI** and **MapLibre GL JS**. It discovers nearby parking facilities and unused `45–550 m²` (`3–6` car) pockets within a strict `1 km` radius, indexes Indian POIs in SQLite FTS5 from Overture Maps, calculates turn-by-turn routes via OSRM, and provides 15-minute spot holds plus an operator touch dashboard.

> **Note:** An upgraded customer-focused edition using OpenFreeMap defaults, total trip-time ranking, service worker offline caching, and privacy controls is maintained separately in `openpark-customer`.

---

## 🚀 Live Deployment & URLs

- **Driver Web App**: [https://openpark-web-production.up.railway.app/app/](https://openpark-web-production.up.railway.app/app/)
- **Operator Touch Dashboard**: [https://openpark-web-production.up.railway.app/dashboard/](https://openpark-web-production.up.railway.app/dashboard/)
- **Interactive API Docs (Swagger)**: [https://openpark-web-production.up.railway.app/docs](https://openpark-web-production.up.railway.app/docs)
- **Container**: `docker build -t openpark . && docker run -p 8000:8000 openpark`

---

## 🌟 Core Features

1. **Unified 1 km Find Parking & AI Small-Ground Scanner (`/api/ai/scan-parking`)**
   - Strictly scoped to a `<= 1 km` radius around the searched destination or user location.
   - Identifies small unused pockets (`45–550 m²`, ~3–6 cars), mall plazas, and legal surface bays using local OSM/Overpass caches plus fast CGImap and Photon enrichment, backed by bounded LRU caches (`_cache_put`).
   - Supports crowd verification (`✅ Parkable` / `🚫 Blocked`) via `POST /api/ai/verify-pocket`.

2. **India-Scoped Offline & Live Place Search (`/api/places/search`)**
   - Full-text SQLite FTS5 index (`backend/places_db.py`) hydrated on startup from [data/overture_places_openpark.json.gz](data/overture_places_openpark.json.gz) and constrained to the India bounding box (`6.5 <= lat <= 37.5`, `68.0 <= lon <= 97.5`).

3. **MapLibre GL JS Basemaps & Overlays (`app/index.html`)**
   - Defaults to **Google Maps Satellite Hybrid** with a non-destructive 1-tap switcher to **GMap Full Detail Retina**, preserving camera state, routes, and AI polygons.
   - Renders Overpass parking outlines, fuel stations, and toll plazas via `/api/osm/overpass`.

4. **Parking Availability, 15-Minute Holds & Operator Dashboard (`dashboard/index.html`)**
   - Pre-seeded Bengaluru parking dataset (`data/bengaluru_parking_opencity.json`).
   - 15-minute spot reservations (`POST /lots/{lot_id}/hold`, `DELETE /lots/{lot_id}/hold`) with `OP-*` pass codes, plus live crowd reporting (`POST /lots/{lot_id}/reports`).
   - Dedicated operator touch dashboard (`/dashboard/`) with live WebSocket broadcasts (`/ws/lots/{lot_id}`).

5. **OSRM Navigation & Traccar GPS Telemetry**
   - Turn-by-turn routes (`/api/traccar/route`) and alternative corridor comparison (`/api/traccar/routes/compare`).
   - OsmAnd / Traccar HTTP telemetry ingestion (`GET` & `POST /api/traccar`) and WebSocket live vehicle updates (`/ws/vehicle`). When running locally, raw OsmAnd TCP port `5055` is also available; on Railway, HTTP endpoints listen on `$PORT` and raw TCP `5055` requires enabling a Railway TCP Proxy.

6. **Optional Provider Proxies**
   - Server-side endpoints for **Ola Maps** (`/api/olamaps/*`), **Mappls** (`/api/mappls/*`), **Outscraper** (`/api/outscraper/*`), and **Geofabrik** (`/api/geofabrik/*`), enabled when the corresponding environment keys are configured.

---

## 🔌 Verified API Endpoints Reference

### Smart Parking & AI Scanner
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/lots` | List all loaded parking lots |
| `GET` | `/lots/nearby` | Parking lots strictly within `<= 1 km` (`radius_m` capped at `1000`) |
| `GET` | `/lots/{lot_id}` | Single lot details |
| `GET` | `/lots/{lot_id}/telemetry` | Multi-zone occupancy, EV, and heuristic telemetry |
| `POST` | `/lots/{lot_id}/hold` | Reserve a 15-minute hold and issue an `OP-*` entry pass |
| `DELETE` | `/lots/{lot_id}/hold` | Release an active hold |
| `POST` | `/lots/{lot_id}/reports` | Submit crowd report (`got_spot`, `has_space`, `lot_full`) |
| `POST` | `/lots/{lot_id}/availability` | Operator availability update (requires `X-API-Key`) |
| `GET` | `/api/ai/scan-parking` | Scan `<= 1 km` for 45–550 m² small grounds, malls, and bays |
| `POST` | `/api/ai/verify-pocket` | Vote `open` or `blocked` on an AI-detected pocket |
| `GET` | `/api/ai/verified-pockets` | List crowd-verified pocket votes |

### Places, Routing, Overpass & Telemetry
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/places/search` | India-scoped SQLite FTS5 + Photon search |
| `GET` | `/api/places/nearby` | Spatial Haversine nearby POI lookup |
| `GET` | `/api/places/stats` | Indexed places counts and top categories |
| `GET` | `/api/osm/overpass` | OSM parking outlines, fuel stations, and toll booths |
| `GET` | `/api/traccar/route` | OSRM driving route geometry and turn-by-turn steps |
| `GET` | `/api/traccar/routes/compare` | Compare fastest vs alternative driving routes |
| `GET` / `POST` | `/api/traccar` | Ingest OsmAnd / Traccar HTTP GPS fixes |
| `GET` | `/api/geolocate` | Approximate IP geolocation |
| `GET` | `/api/config/public` | Public frontend runtime config & map style defaults |
| `GET` | `/health` & `/health/details` | Service health and dataset diagnostics |
| `WS` | `/ws/lots/{lot_id}`, `/ws/vehicle`, `/api/socket` | Real-time lot availability and vehicle position streams |

---

## 🛠️ Scripts & Utilities

- **Import Overture Places into SQLite FTS5**:
  ```bash
  python3 scripts/overture_places_importer.py
  ```
- **Harvest OSM / Overpass Places Dataset**:
  ```bash
  python3 scripts/download_places_dataset.py
  ```
- **Headless Browser E2E Check**:
  ```bash
  ./backend/venv/bin/python scripts/e2e_browser_check.py
  ```

---

## 🚀 Quickstart (Local Development)

### 1. Create Environment & Install Dependencies
```bash
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r requirements.txt
```

### 2. Optional Environment Variables
Copy `.env.example` to `.env` and add optional keys (`OPENPARK_API_KEY`, `OLAMAPS_API_KEY`, `OUTSCRAPER_API_KEY`, `MAPPLS_CLIENT_ID`, `MAPPLS_CLIENT_SECRET`, `DATABASE_URL`, `REDIS_URL`) if needed. Zero paid keys are required to run core search, routing, and parking discovery.

### 3. Run the Server
```bash
./backend/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
- Driver Web App: [http://localhost:8000/app/](http://localhost:8000/app/)
- Operator Dashboard: [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/)
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Automated Testing

Run the full 22-test FastAPI backend suite:
```bash
./backend/venv/bin/pytest backend/test_api.py -v
```

---

## 🔒 Privacy & License

- **Ephemeral Vehicle Telemetry**: Real-time vehicle positions sent via WebSockets or `/api/traccar` remain in memory only during active sessions.
- **License**: [Apache-2.0 License](LICENSE).
- **Map & Place Data**: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), [Overture Maps Foundation](https://overturemaps.org/), and [MapLibre](https://maplibre.org/).
