# OpenPark 🅿️

**OpenPark** is an open-source, real-time smart parking platform for metro cities (such as Bengaluru and Mumbai). It shows drivers parking lots on an interactive map, tracks vehicle location live, computes turn-by-turn driving routes via OSRM, displays live spot availability, alerts drivers upon arrival, and empowers parking lot attendants and edge cameras with real-time controls.

Everything is built using 100% open-source tools: MapLibre GL, OpenStreetMap, FastAPI, PostgreSQL + PostGIS, Redis, and WebSockets.

---

## Architecture & Tech Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Map & Tiles** | [MapLibre GL](https://maplibre.org/) + [OpenStreetMap](https://www.openstreetmap.org/) | Vector & raster map visualization with color-blind accessible markers |
| **Routing** | [OSRM](http://project-osrm.org/) | Offline/online driving directions, route polyline, distance & ETA |
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11+) | Async REST API & high-concurrency WebSocket channels |
| **Spatial Database** | [PostgreSQL 16](https://www.postgresql.org/) + [PostGIS 3.4](https://postgis.net/) | `ST_DWithin`, `ST_Distance` spherical geography queries |
| **Live Cache & Pub/Sub** | [Redis 7](https://redis.io/) | Sub-millisecond broadcast of availability changes |
| **Driver App** | Web App / PWA (`app/index.html`) | Live map, GPS tracking, audio navigation alerts, crowdsourcing |
| **Operator Dashboard** | Mobile Web (`dashboard/index.html`) | Big touch controls (`+1`, `-1`, `FULL`) and lot capacity editor |
| **Sensors & Edge** | Python OpenCV / REST (`edge/`) | Automatic barrier / camera vehicle entry and exit counters |
| **Simulator** | Python (`simulator/fake_lots.py`) | Real-time sensor simulation with realistic Poisson fluctuations |

---

## Directory Structure

```text
openpark/
├── app/                  # Driver map web application (PWA)
│   └── index.html        # MapLibre map, GPS tracking, OSRM routing, voice alerts
├── backend/              # FastAPI server
│   ├── main.py           # Core REST API & WebSockets (/ws/lots, /ws/vehicle)
│   ├── schema.sql        # PostGIS schema (parking_lots, availability, reports)
│   ├── seed_osm.py       # OpenStreetMap Overpass & Bengaluru seed loader
│   ├── test_api.py       # Automated test suite (100% passing)
│   └── requirements.txt  # Python backend dependencies
├── dashboard/            # Operator & parking attendant interface
│   └── index.html        # Mobile-friendly +/- free spot counter & lot editor
├── edge/                 # Camera & barrier sensor scripts
│   └── camera_counter.py # Vehicle entry/exit counter
├── infra/                # Docker Compose & deployment configuration
│   ├── docker-compose.yml# PostGIS 16-3.4 and Redis 7 services
│   └── osrm/             # OSRM setup script and road network extracts
├── simulator/            # Sensor simulator for testing without hardware
│   └── fake_lots.py      # Updates nearest 10 lots every 3s via API
├── docs/                 # Documentation & API specifications
│   └── api_spec.md       # Complete REST & WebSocket specification
├── CONTRIBUTING.md       # Contribution guidelines & good first issues
├── LICENSE               # Apache-2.0 License
├── .env.example          # Environment configuration template
└── README.md             # Project documentation
```

---

## Quickstart (One-Command Setup)

### 1. Start the Database & Redis
Ensure Docker is running, then run:
```bash
cd infra && docker compose up -d
```
Both `postgis` (port 5432) and `redis` (port 6379) will start and report healthy.

### 2. Initialize Database Tables
Run the schema script to enable PostGIS and create the tables:
```bash
docker exec -i infra-db-1 psql -U openpark -d openpark < backend/schema.sql
```

### 3. Seed Real Parking Lots
Seed verified Bengaluru parking lots (UB City, Brigade Road, Garuda Mall, Commercial St, Majestic Interchange, etc.):
```bash
./backend/venv/bin/python backend/seed_osm.py Bengaluru
```

### 4. Start the FastAPI Backend
```bash
cd backend
../backend/venv/bin/uvicorn main:app --reload --port 8000
```
- API Docs & Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

### 5. Launch the Driver Map & Operator Dashboard
You can serve the frontend with any static server or Python's built-in HTTP server:
```bash
# In openpark root:
python3 -m http.server 3000
```
- **Driver Map**: [http://localhost:3000/app/](http://localhost:3000/app/)
- **Operator Dashboard**: [http://localhost:3000/dashboard/](http://localhost:3000/dashboard/)

---

## Live Features Demonstration

### Real-Time Sensor Simulator
To see live spot availability changing in real-time on the map and dashboard without physical sensors, run:
```bash
./backend/venv/bin/python simulator/fake_lots.py
```
Watch the markers change color and spot counts update smoothly over WebSockets!

### Automated Vehicle GPS Simulation
On the Driver Map, tap **🚗 Simulate GPS**. The blue vehicle dot will smoothly drive along the route towards the parking lot. When it reaches within **1.5 km**, an arrival banner pops up and speaks the alert aloud!

### Dynamic Reroute Alert
If a selected destination fills up (`free_spots = 0`) while you are en route, OpenPark detects the condition in real-time and alerts you with a 1-tap button to switch to the nearest available lot.

---

## Running Tests

Execute the automated test suite with pytest:
```bash
cd backend
../backend/venv/bin/pytest test_api.py -v
```

---

## Privacy Policy & Location Data
OpenPark is built privacy-first:
- **No Location History**: Driver GPS positions received over `/ws/vehicle` are strictly ephemeral and used solely in-memory to compute proximity to destination lots and trigger arrival alerts.
- **No Tracking**: Driver location coordinates are **never stored** in the database or written to disk.

---

## Attribution & Licenses
- **OpenStreetMap**: Map data is © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), licensed under the Open Data Commons Open Database License (ODbL).
- **MapLibre GL**: Licensed under the BSD 3-Clause License.
- **OpenPark Software**: Open-source under the [Apache-2.0 License](LICENSE).