# OpenPark 🅿️

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-3776ab.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)
[![MapLibre GL](https://img.shields.io/badge/MapLibre%20GL%20JS-v4-396afc.svg)](https://maplibre.org/maplibre-gl-js/docs/API/)
[![Ola Maps API](https://img.shields.io/badge/Ola%20Maps%20API-api.olamaps.io-00D09C.svg)](https://maps.olacabs.com)
[![Outscraper API](https://img.shields.io/badge/Outscraper%20API-Google%20Maps%20Reviews-4285F4.svg)](https://outscraper.com/)
[![Mappls REST API](https://img.shields.io/badge/Mappls%20REST%20API-MapmyIndia-orange.svg)](https://github.com/mappls-api/mapmyindia-rest-api)
[![Traccar GPS](https://img.shields.io/badge/Traccar%20GPS-Standard%20Protocols-00a884.svg)](https://www.traccar.org/)
[![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5%20Search-003B57.svg)](https://www.sqlite.org/fts5.html)
[![Tests](https://img.shields.io/badge/Tests-18%2F18%20Passing-success.svg)](backend/test_api.py)

**OpenPark** is an open-source, production-grade real-time smart parking, navigation, and live GPS telemetry platform designed for high-density metro areas. It guides drivers to vacant parking spots using vector maps, provides real-time turn-by-turn routing with multi-route comparisons, enables butter-smooth 60 FPS physics vehicle simulation, captures live device GPS tracking, integrates standard **Traccar GPS** telemetry protocols, connects to **Ola Maps** and **Mappls** services, indexes hundreds of thousands of offline places via **SQLite FTS5**, and enriches places with verified Google Maps reviews through **Outscraper**.

---

## 🌟 Key Features & Integrations

### 1. 🗺️ High-Performance Vector Mapping ([MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/API/))
- **100% Free & Open-Source**: Runs on MapLibre GL JS v4 with zero proprietary map tokens or vendor lock-in.
- **Curated Vector & Retina Basemaps**: Pre-configured with OpenFreeMap Liberty, OpenFreeMap Bright, OpenFreeMap Positron, Carto Dark Matter, Carto Voyager, and high-DPI Google Hybrid raster tiles (`tileSize: 512`).
- **Dynamic Viewport Auto-Resizing**: Built-in `ResizeObserver` automatically guarantees 100% full-screen canvas coverage across mobile, tablet, and ultra-wide displays.
- **Top-Level Route Layer Stacking**: High-contrast navigation routes (`#1d4ed8` / `#3b82f6`) with casing borders automatically elevated above all basemaps and 3D building extrusions.

### 2. 📍 Ola Maps API Integration ([api.olamaps.io](https://maps.olacabs.com))
- **Hyperlocal India Autocomplete**: Proxied query endpoint (`GET /api/olamaps/autocomplete`) with optional bounding location coordinates and radius.
- **Sub-Building Reverse Geocoding**: Direct coordinate lookup (`GET /api/olamaps/reverse-geocode`) mapping any coordinate pair to landmark, building number, and street name.
- **Turn-by-Turn Navigation & Routing**: Driving, cycling, and walking routes via `GET /api/olamaps/directions`.
- **Dynamic Key Support**: Seamlessly uses the environment variable `OLAMAPS_API_KEY` or per-request `?api_key=` overrides.

### 3. ⭐ Outscraper Google Maps Places & Reviews API
- **Live Google Reviews Extraction**: Fetch authentic Google Maps user reviews, star ratings, review timestamps, and user profile pictures via `GET /api/outscraper/reviews`.
- **Live Places Search**: Search places on Google Maps via `GET /api/outscraper/search`.
- **In-Memory Caching Layer**: Automated 1-hour TTL cache layer to prevent redundant API queries and conserve API quotas.
- **Bulk Extraction CLI Utility**: `scripts/outscraper_collector.py` for exporting harvested place reviews to JSON and CSV.

### 4. 🗄️ Offline Places Database (SQLite FTS5)
- **Sub-Millisecond Full-Text Search**: In-memory SQLite FTS5 engine (`data/places_search.db`) supporting instant prefix matching on name, category, and address via `GET /api/places/search`.
- **Spatial Radius Search (`ST_DWithin` equivalent)**: Fast Haversine circular proximity query via `GET /api/places/nearby` with optional category filtering.
- **Place Archetype Enrichment**: Automatically enriches queried buildings and shops with realistic operating hours, amenities, phone numbers, and rating distributions via `GET /api/places/lookup`.
- **Multi-Category Ingestion & Export CLI**: `scripts/download_places_dataset.py` crawls and ingests hostels, PGs, hotels, hospitals, tech parks, cafes, and fuel stations, with `--export csv` and `--export geojson` export modes.

### 5. 🧭 Turn-by-Turn Navigation & Route Comparison
- **Fastest vs. Shortest Routes**: Compare multiple driving corridors via `GET /api/traccar/routes/compare`. Returns alternative paths, duration savings, and distance deltas.
- **Quick-Share Deep Linking**: One-click "Share Route" button copies `?start=lat,lon&end=lat,lon` deep links to the clipboard for instant sharing.
- **Keyboard Shortcuts**: Press `?` in the driver app to view the keyboard shortcuts guide (`H` = HUD toggle, `N` = Navigation, `D` = Dark/Light theme, `Esc` = Close modal).

### 6. 🏎️ 60 FPS Butter-Smooth Vehicle Animation
- **Continuous Spline Traversal**: Fluid 60 FPS `requestAnimationFrame` spline advancement along road polylines.
- **Inertia Physics**: Accelerates on straight corridors, decelerates to ~20 km/h ahead of sharp turns, and softly brakes to 0 km/h at destinations.
- **Shortest-Arc Bearing Interpolation**: Smooth circular rotation eliminating sudden 360° flipping.

### 7. 📡 Traccar GPS Telemetry & Pairing
- **Standard Protocol Ingestion**: Native implementation of the Traccar OsmAnd / HTTP protocol via `GET /api/traccar` and `POST /api/traccar`.
- **Floating HUD**: Digital speedometer (`🟢 Moving`, `🟡 Idle`, `🔴 Stopped`), 3D compass rose needle, altitude, odometer accumulator, and real-time battery status (`⚡`).
- **Traccar Client Pairing**: Connects directly with the free Traccar Client app (iOS / Android) or OBD-II hardware trackers.

### 8. 📍 Mappls (MapmyIndia) REST APIs
- **AutoSuggest**: `GET /api/mappls/autosuggest` for Indian addresses and eLoc pin codes.
- **Driving Route Engine**: `GET /api/mappls/route` for road geometries with fallback to OSRM.

### 9. 🔬 Multi-Zone IIoT Sensor Telemetry
- Sub-zone vacancy counters (Zone A, B, C, D), EV charging spot metrics, and dynamic congestion multipliers.
- Pre-seeded with real municipal datasets from OpenCity Bengaluru.

### 10. 📱 Operator Touch Dashboard (`dashboard/index.html`)
- Dedicated attendant interface with large mobile touch controls (`+1`, `-1`, `FULL`, `CLEAR`).
- Instant capacity editor and WebSocket real-time broadcast to all connected drivers.

---

## 🏗️ Architecture & Data Flow

```text
                            ┌──────────────────────────────┐
                            │    Traccar Client / GPS      │
                            │   (Android, iOS, OBD-II)     │
                            └──────────────┬───────────────┘
                                           │ HTTP OsmAnd
                                           ▼
┌─────────────────────────┐       ┌─────────────────┐       ┌─────────────────────────┐
│   Driver Web App (PWA)  │◄─────►│   FastAPI Core  │◄─────►│    Operator Dashboard   │
│  (MapLibre / 60 FPS)    │  WS   │  (Python 3.9+)  │  WS   │ (Touch Capacity Ctrls)  │
└─────────────────────────┘       └────────┬────────┘       └─────────────────────────┘
                                           │
         ┌──────────────────┬──────────────┴─────┬──────────────────┐
         ▼                  ▼                    ▼                  ▼
  ┌──────────────┐   ┌──────────────┐     ┌──────────────┐   ┌──────────────┐
  │  Ola Maps    │   │  Outscraper  │     │ SQLite FTS5  │   │  PostgreSQL  │
  │  api.olamaps │   │ Google Maps  │     │   Places DB  │   │  + PostGIS   │
  └──────────────┘   └──────────────┘     └──────────────┘   └──────────────┘
```

---

## 🔌 API Endpoints Reference

### 📍 Ola Maps API (`api.olamaps.io`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/olamaps/autocomplete` | Places autocomplete search with optional location and radius |
| `GET` | `/api/olamaps/reverse-geocode` | Reverse geocode coordinates to exact address and building name |
| `GET` | `/api/olamaps/directions` | Driving, walking, and cycling navigation directions and geometry |

### ⭐ Outscraper Google Maps API
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/outscraper/search` | Search places on Google Maps via Outscraper |
| `GET` | `/api/outscraper/reviews` | Extract verified Google Maps reviews, ratings, and photos (cached) |

### 🗄️ Places Intelligence (SQLite FTS5)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/places/search` | Sub-millisecond full-text search across offline places index |
| `GET` | `/api/places/nearby` | Spatial Haversine search within given radius (km) and category |
| `GET` | `/api/places/lookup` | Click-to-lookup reverse geocoding with Google Maps archetype details |
| `GET` | `/api/places/stats` | Summary statistics of indexed categories and total places |

### 🧭 Navigation & Traccar GPS Telemetry
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET/POST`| `/api/traccar` | Ingests live Traccar / OsmAnd GPS telemetry packets |
| `GET` | `/api/traccar/search` | Geocoding and places search for navigation destinations |
| `GET` | `/api/traccar/route` | OSRM turn-by-turn driving route geometry |
| `GET` | `/api/traccar/routes/compare`| Compare fastest vs shortest alternative routes with distance deltas |

### 🅿️ Smart Parking & IIoT Telemetry
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/lots` | List all parking facilities with live availability |
| `GET` | `/api/lots/nearby` | Proximity search for parking lots within a radius |
| `POST`| `/api/lots/{id}/availability`| Update vacant spot count (requires `X-API-Key`) |
| `POST`| `/api/reports/crowd` | Crowdsourced parking availability reports |
| `GET` | `/api/telemetry/stats` | Aggregated multi-zone occupancy and EV metrics |

### 🗺️ Map Configurations & Basemaps
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET/POST`| `/config/map` | Get or update active vector map style configuration |
| `GET` | `/api/map/style/ultra-detail` | Ultra-detail vector style stylesheet with 3D buildings |
| `GET` | `/api/map/style/ultra-detail-dark` | Dark mode ultra-detail vector style stylesheet |

### 🩺 System Diagnostics
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Basic service uptime and status check |
| `GET` | `/health/details` | Detailed diagnostic breakdown: PostGIS, Redis, Places DB, memory |

### ⚡ Real-Time WebSockets
| Protocol | Endpoint | Description |
| :--- | :--- | :--- |
| `WS` | `/ws/lots` | Live broadcast of parking availability and occupancy updates |
| `WS` | `/ws/vehicle` | Live vehicle GPS position, speed, and heading stream |

---

## 🛠️ CLI Utilities & Scripts

### 1. Offline Places Dataset Harvester & Exporter
```bash
# Ingest places into local SQLite FTS5 database
python3 scripts/download_places_dataset.py --categories hostels,hotels,hospitals,cafes

# Export harvested places to CSV
python3 scripts/download_places_dataset.py --export csv --output data/places_export.csv

# Export harvested places to GeoJSON
python3 scripts/download_places_dataset.py --export geojson --output data/places_export.geojson
```

### 2. Outscraper Google Maps Review Collector
```bash
python3 scripts/outscraper_collector.py --query "Debrecan House Bangalore" --limit 5 --reviews-limit 20
```

### 3. OpenCity Bengaluru Municipal Data Seeder
```bash
./backend/venv/bin/python backend/seed_opencity.py
```

---

## ⚙️ Configuration & Environment Variables

Create a `.env` file in the project root:

```ini
# OpenPark Core API
OPENPARK_API_KEY=dev-key

# Ola Maps API (https://api.olamaps.io)
OLAMAPS_API_KEY=your_olamaps_api_key_here

# Outscraper Google Maps API (https://outscraper.com)
OUTSCRAPER_API_KEY=your_outscraper_api_key_here

# Mappls / MapmyIndia OAuth (Optional)
MAPPLS_CLIENT_ID=your_mappls_client_id
MAPPLS_CLIENT_SECRET=your_mappls_client_secret

# Database & Cache (Optional for full Docker mode)
DATABASE_URL=postgresql://openpark:openpark123@localhost:5432/openpark
REDIS_URL=redis://localhost:6379/0
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.9+**
- **Docker & Docker Compose** (optional for PostGIS & Redis)

### 2. Set Up Virtual Environment & Dependencies
```bash
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

### 3. Start Backend Server
```bash
cd backend
../backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Diagnostics**: [http://localhost:8000/health/details](http://localhost:8000/health/details)
- **Driver Navigation App**: [http://localhost:8000/app/](http://localhost:8000/app/)
- **Operator Touch Dashboard**: [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/)

---

## 🧪 Automated Testing

The repository includes a comprehensive 18-suite unit and integration test suite:

```bash
./backend/venv/bin/pytest backend/test_api.py -v
```

All 18 tests execute in sub-second time:
- `test_lot_status_logic`: Occupancy threshold calculation (`available`, `filling_up`, `full`).
- `test_confidence_metrics`: Sensor confidence scoring.
- `test_health_endpoint`: Service health check.
- `test_list_lots`: In-memory and database lot listing.
- `test_nearby_lots_bengaluru`: Proximity search with Haversine metrics.
- `test_update_availability_auth`: API key authorization enforcement on updates.
- `test_crowd_report`: Crowdsourced incident and spot reporting.
- `test_lot_telemetry_endpoint`: Zone breakdown, EV spots, and occupancy rates.
- `test_maplibre_config_endpoints`: Style stylesheet delivery and runtime config.
- `test_mappls_rest_api_endpoints`: AutoSuggest and Mappls route proxies.
- `test_traccar_endpoints`: OsmAnd GPS protocol ingestion, speed, and heading.
- `test_osm_overpass_features`: OpenStreetMap feature parsers.
- `test_websocket_ping_pong`: Real-time WebSocket connection handling.
- `test_geofabrik_endpoints`: Offline regional boundary and dataset checks.
- `test_google_maps_place_details_enrichment`: Place archetype enrichment (amenities, hours, reviews).
- `test_outscraper_endpoints`: Google Maps reviews extraction and cache verification.
- `test_offline_places_database`: SQLite FTS5 search and spatial nearby queries.
- `test_olamaps_endpoints`: Ola Maps client, reverse geocode, autocomplete, and routing.

---

## 🔒 Privacy & Data Policy
- **Ephemeral Vehicle Positions**: GPS coordinates streamed by drivers via WebSockets or Traccar are kept strictly in-memory to compute distance to destination lots, animate vehicle motion, and calculate navigation vectors.
- **Zero Permanent Tracking**: Driver real-time coordinates are **never stored** permanently.

---

## 📄 License
This project is open-source under the [Apache-2.0 License](LICENSE).
Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Vector basemaps powered by [MapLibre](https://maplibre.org/), OpenFreeMap, and Carto.
