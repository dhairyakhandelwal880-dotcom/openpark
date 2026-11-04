# OpenPark 🅿️

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-3776ab.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4-589632.svg)](https://postgis.net/)
[![Redis](https://img.shields.io/badge/Redis-7-dc382d.svg)](https://redis.io/)
[![Mapbox GL](https://img.shields.io/badge/Mapbox%20GL%20JS-v3-4264fb.svg)](https://www.mapbox.com/)
[![Traccar GPS](https://img.shields.io/badge/Traccar%20GPS-Standard%20Protocols-00a884.svg)](https://www.traccar.org/)

**OpenPark** is an open-source, production-grade real-time smart parking & live GPS telemetry platform designed for high-density metro areas (seeded with real municipal datasets from Bengaluru). It guides drivers to vacant parking spots using vector maps, provides real-time turn-by-turn routing with voice prompts, enables butter-smooth 60 FPS physics vehicle simulation, captures live device GPS tracking, integrates standard **Traccar GPS** telemetry protocols, displays multi-zone IIoT sensor diagnostics, and empowers parking lot operators with a responsive mobile touch dashboard.

---

## 🌟 Key Features

### 1. 🗺️ Vector Mapping & 3D Extruded Buildings (Mapbox GL JS v3)
- **High-Definition Vector Tiles**: Runs Mapbox GL JS v3 with custom map styles: *Streets v12*, *Navigation Day*, *Navigation Night*, and *Satellite Streets*.
- **3D Buildings Extrusion**: Dynamically renders real 3D building heights based on zoom level and light angle.
- **Zero-Token Fallback**: Automatically degrades gracefully to MapLibre GL + OpenStreetMap vector tiles if no Mapbox key is provided.
- **Precision Tip Anchoring**: Every parking pin tip is locked mathematically to its exact coordinate `(17, 44)` with zero displacement during zoom and pan operations.

### 2. 🏎️ 60 FPS Butter-Smooth Vehicle Animation
- **Continuous Spline Traversal**: Replaced discrete jumps with fluid 60 FPS `requestAnimationFrame` spline advancement along OSRM & Mapbox road polylines.
- **Realistic Driving Physics & Inertia**:
  - Automatically accelerates up to 46 km/h on straight roads.
  - Anticipates upcoming road curvature, decelerating to ~20 km/h before sharp turns and bends.
  - Smoothly brakes to 0 km/h within 5 meters of the destination.
- **Shortest-Arc Bearing Interpolation (`getShortestArcRotation`)**: Rotates using minimum circular angular differences to eliminate sudden 360° flip glitches.
- **Dynamic 3D Camera Follow**: Maps camera pitch to 45° and smoothly tracks behind the vehicle.

### 3. 🎯 Real-Time Device GPS Tracking (`🎯 Live GPS`)
- **Direct Device Sensors**: Connects to browser `navigator.geolocation.watchPosition` with `enableHighAccuracy: true`.
- **Live Telemetry Extraction**: Measures actual device speed (km/h), heading/bearing, altitude, and precision accuracy halo (±X m).
- **Device Battery Monitoring**: Uses `navigator.getBattery()` to capture actual device battery percentage and charging indicator (`⚡`).
- **Live Traccar Synchronization**: Automatically streams live device fixes into `/api/traccar` and broadcasts updates via WebSockets (`/ws/vehicle`).

### 4. 📡 Traccar GPS Live Telemetry & Pairing
- **Standard Protocol Ingestion**: Native implementation of the Traccar OsmAnd / HTTP protocol via `GET /api/traccar` and `POST /api/traccar`.
- **Floating HUD**:
  - Digital speedometer with motion state (`🟢 Moving`, `🟡 Idle`, `🔴 Stopped`).
  - 3D compass rose needle with cardinal direction tracking.
  - Altitude, accuracy radius, live odometer accumulator, and real-time battery status.
  - Real-time breadcrumb trail line toggle.
- **Traccar Client Pairing**: Easily pairs with the free **Traccar Client** app (iOS / Android) or standard OBD-II hardware GPS trackers.

### 5. 🔬 Multi-Zone IIoT Sensor Telemetry
- **Zone Occupancy Breakdown**: Sub-zone vacancy counters for Zone A, Zone B, Zone C, and Zone D.
- **Smart City Indicators**: Live EV charging spot counters, dynamic congestion pricing multipliers (e.g. `1.2x Peak Rate`), and live traffic indicators.
- **Real Municipal Datasets**: Pre-seeded with real OpenCity Bengaluru public parking lots and IIoT sensor management distributions.

### 6. 📱 Operator Touch Dashboard (`dashboard/index.html`)
- Dedicated attendant interface with large mobile touch controls (`+1`, `-1`, `FULL`, `CLEAR`).
- Instant capacity editor and WebSocket real-time broadcast to all connected drivers.

---

## 🏗️ Architecture & Tech Stack

```text
                           ┌──────────────────────────┐
                           │   Traccar Client / GPS   │
                           │  (Android, iOS, OBD-II)  │
                           └────────────┬─────────────┘
                                        │ HTTP / OsmAnd Protocol
                                        ▼
┌────────────────────────┐      ┌───────────────┐      ┌─────────────────────────┐
│  Driver Web App (PWA)  │◄────►│  FastAPI Core │◄────►│   Operator Dashboard    │
│  (Mapbox v3 / 60 FPS)  │ WS   │  (Python 3.9+)│  WS  │  (Real-Time Touch Ctrls)│
└────────────────────────┘      └───────┬───────┘      └─────────────────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
                 ┌───────────────┐             ┌───────────────┐
                 │ PostgreSQL 16 │             │    Redis 7    │
                 │  PostGIS 3.4  │             │ Pub/Sub Cache │
                 └───────────────┘             └───────────────┘
```

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Map Rendering** | [Mapbox GL JS v3](https://www.mapbox.com/) / [MapLibre GL](https://maplibre.org/) | Vector vector tiles, 3D extruded buildings, styling |
| **Routing Engine** | [OSRM](http://project-osrm.org/) | Offline/online driving directions, turn-by-turn road geometry |
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com/) (Python) | High-throughput asynchronous REST endpoints & WebSockets |
| **GPS Telemetry** | [Traccar Standards](https://www.traccar.org/) | Ingestion of OsmAnd / Traccar HTTP GPS packets |
| **Spatial Database** | [PostgreSQL 16](https://www.postgresql.org/) + [PostGIS 3.4](https://postgis.net/) | Fast spatial indexing, `ST_DWithin`, spherical distance queries |
| **Cache & Pub/Sub** | [Redis 7](https://redis.io/) | Sub-millisecond broadcast of availability and vehicle fixes |
| **Client Frontend** | HTML5, CSS3, Vanilla ES6+ | Zero-dependency, lightweight, high-performance web applications |

---

## 📁 Repository Structure

```text
openpark/
├── app/                  # Driver web app (PWA)
│   └── index.html        # Mapbox v3 map, 60 FPS animation, live GPS, Traccar HUD
├── backend/              # FastAPI server
│   ├── main.py           # Core REST API & WebSockets (/ws/lots, /ws/vehicle, /api/traccar)
│   ├── schema.sql        # PostGIS schema (parking_lots, availability, reports)
│   ├── traccar_service.py# Traccar GPS protocol ingestion, odometer & telemetry service
│   ├── iiot_service.py   # Multi-zone IIoT sensor telemetry & EV spot engine
│   ├── seed_osm.py       # OpenStreetMap Overpass & Bengaluru seed loader
│   ├── seed_opencity.py  # OpenCity Bengaluru municipal parking lots loader
│   ├── test_api.py       # Automated test suite (10/10 tests passing)
│   └── requirements.txt  # Python backend dependencies
├── dashboard/            # Parking operator & attendant touch interface
│   └── index.html        # Mobile-friendly +/- free spot counter & lot editor
├── data/                 # Seed datasets
│   ├── bengaluru_parking_opencity.json
│   └── archive/IIoT_Smart_Parking_Management.csv
├── edge/                 # Camera & barrier sensor scripts
│   └── camera_counter.py # Vehicle entry/exit counter
├── infra/                # Infrastructure & container definitions
│   ├── docker-compose.yml# PostGIS 16-3.4, Redis 7, and optional Traccar server
│   └── osrm/             # OSRM setup script and road network extracts
├── simulator/            # Hardware-free sensor simulator
│   └── fake_lots.py      # Real-time Poisson sensor fluctuation simulator
├── docs/                 # Documentation & API specifications
│   └── api_spec.md       # Complete REST & WebSocket specification
├── CONTRIBUTING.md       # Contribution guidelines
├── LICENSE               # Apache-2.0 License
├── .env.example          # Environment configuration template
└── README.md             # Project documentation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Docker & Docker Compose**
- **Python 3.9+**

### 2. Clone the Repository
```bash
git clone https://github.com/dhairyakhandelwal880-dotcom/openpark.git
cd openpark
```

### 3. Start Database & Redis Services
```bash
cd infra
docker compose up -d
cd ..
```
* PostgreSQL + PostGIS starts on port `5432`
* Redis starts on port `6379`

### 4. Set Up Python Virtual Environment
```bash
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

### 5. Initialize the Spatial Database Schema
```bash
docker exec -i infra-db-1 psql -U openpark -d openpark < backend/schema.sql
```

### 6. Seed Parking Lots Dataset
Seed verified municipal parking facilities across Bengaluru:
```bash
./backend/venv/bin/python backend/seed_opencity.py
```

### 7. Launch the Backend Server
```bash
cd backend
../backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- **API Documentation & Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### 8. Open the Driver Map & Operator Dashboard
- **Driver Navigation App**: [http://localhost:8000/app/](http://localhost:8000/app/)
- **Operator Touch Dashboard**: [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/)

---

## 📡 Pairing a Traccar Smartphone Client

You can stream real GPS telemetry directly from your phone:

1. Install the free **Traccar Client** app from Google Play or Apple App Store.
2. In the app settings:
   - **Device Identifier**: Enter your ID (e.g. `OP-TRACKER-01`).
   - **Server URL**: Enter `http://<YOUR_IP>:8000/api/traccar`.
   - **Location Accuracy**: High.
   - **Frequency**: 2–5 seconds.
3. Switch **Service Status** to **ON**.
4. Open [http://localhost:8000/app/](http://localhost:8000/app/) and click **📡 Traccar** in the top bar to watch your live speed, compass direction, altitude, and trail populate in real time!

---

## 🧪 Running Automated Tests

Run the complete backend test suite:
```bash
./backend/venv/bin/pytest backend/test_api.py -v
```
All 10 tests will execute against live ASGI instances:
- Status threshold logic (`available`, `filling_up`, `full`)
- Proximity geospatial calculations
- Crowdsource report ingestion
- IIoT multi-zone telemetry endpoint
- Mapbox configuration endpoints
- Traccar OsmAnd GPS ingestion protocol endpoints

---

## 🔒 Privacy & Data Policy
- **Ephemeral Vehicle Positions**: GPS coordinates sent by drivers over WebSockets or Traccar are used solely in-memory to compute distance to destination lots, animate navigation markers, and issue arrival warnings.
- **Zero Permanent Tracking**: Driver location coordinates are **never stored** permanently in the relational database.

---

## 📄 License
This project is open-source under the [Apache-2.0 License](LICENSE).
Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Vector tiles © [Mapbox](https://www.mapbox.com).