#!/usr/bin/env bash
# OpenPark - Step 10: OSRM Setup Helper Script
# Prepares and runs local OSRM routing engine for Bengaluru / Southern India zone.

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

PBF_FILE="southern-zone-latest.osm.pbf"
OSRM_BASE="southern-zone-latest.osrm"

echo "=== OpenPark OSRM Routing Engine Setup ==="

if [ ! -f "$PBF_FILE" ]; then
    echo "Downloading southern-zone-latest.osm.pbf from Geofabrik (India Southern Zone)..."
    echo "Tip: You can also use a smaller city extract if RAM is constrained."
    curl -L -o "$PBF_FILE" "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf"
fi

echo "1. Extracting road network with car profile..."
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua "/data/${PBF_FILE}"

echo "2. Partitioning..."
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition "/data/${OSRM_BASE}"

echo "3. Customizing..."
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize "/data/${OSRM_BASE}"

echo "4. Launching OSRM routed server on port 5000..."
docker run -d --name openpark-osrm -p 5000:5000 -v "${PWD}:/data" osrm/osrm-backend \
    osrm-routed --algorithm mld "/data/${OSRM_BASE}"

echo "OSRM is ready and listening on http://localhost:5000"
echo "Test route query: http://localhost:5000/route/v1/driving/77.5946,12.9716;77.6101,12.9352?overview=full&geometries=geojson"
