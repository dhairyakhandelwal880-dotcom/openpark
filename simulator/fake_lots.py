#!/usr/bin/env python3
"""
OpenPark - Step 7: Sensor Data Simulator
Periodically updates availability for the nearest parking lots to simulate
live sensors in a metro city.
"""

import argparse
import random
import time
import requests

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_LAT = 12.9716   # Bengaluru center
DEFAULT_LON = 77.5946
DEFAULT_API_KEY = "dev-key"


def get_nearest_lots(api_url: str, lat: float, lon: float, count: int = 50):
    try:
        url = f"{api_url}/lots"
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        lots = res.json()
        if lots:
            return lots[:count]
    except Exception as e:
        pass

    try:
        url = f"{api_url}/lots/nearby?lat={lat}&lon={lon}&radius=35000"
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        lots = res.json()
        return lots[:count]
    except Exception as e:
        print(f"Fallback to static lots: {e}")
        return [{"id": i, "name": f"Lot #{i}", "capacity": 50, "free_spots": 25} for i in range(1, count + 1)]


def run_simulation(
    api_url: str = DEFAULT_API_URL,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    api_key: str = DEFAULT_API_KEY,
    interval_seconds: float = 3.0,
    single_run: bool = False,
    iterations: int = 0
):
    print(f"Starting OpenPark Sensor Simulator...")
    print(f"API Target: {api_url}")
    print(f"Test Center: ({lat}, {lon})")

    lots = get_nearest_lots(api_url, lat, lon, count=50)
    print(f"Simulating sensor updates for {len(lots)} parking lots:")
    for lot in lots:
        print(f" - [{lot['id']}] {lot['name']} (Capacity: {lot.get('capacity', 50)})")

    free_spots = {}
    capacities = {}
    for lot in lots:
        lid = lot["id"]
        cap = lot.get("capacity") or 50
        capacities[lid] = cap
        curr = lot.get("free_spots")
        free_spots[lid] = curr if curr is not None else random.randint(int(cap * 0.1), int(cap * 0.8))

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    loop_count = 0
    try:
        while True:
            loop_count += 1
            timestamp = time.strftime("%H:%M:%S")
            updates_sent = 0

            for lot in lots:
                lid = lot["id"]
                cap = capacities[lid]
                delta = random.randint(-3, 3)
                free_spots[lid] = max(0, min(cap, free_spots[lid] + delta))

                payload = {
                    "free_spots": free_spots[lid],
                    "source": "sensor"
                }

                try:
                    res = requests.post(
                        f"{api_url}/lots/{lid}/availability",
                        json=payload,
                        headers=headers,
                        timeout=3
                    )
                    if res.status_code == 200:
                        updates_sent += 1
                except Exception as req_err:
                    print(f"[{timestamp}] Failed to send update for lot #{lid}: {req_err}")

            print(f"[{timestamp}] Cycle {loop_count}: Updated {updates_sent}/{len(lots)} lots.")

            if single_run or (iterations > 0 and loop_count >= iterations):
                break

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")


def main():
    parser = argparse.ArgumentParser(description="OpenPark Live Sensor Simulator")
    parser.add_argument("--url", default=DEFAULT_API_URL, help="Backend API URL")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Center latitude")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON, help="Center longitude")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="API key for x-api-key header")
    parser.add_argument("--interval", type=float, default=3.0, help="Interval between ticks in seconds")
    parser.add_argument("--single-run", action="store_true", help="Run one simulation cycle and exit")
    parser.add_argument("--iterations", type=int, default=0, help="Run specific number of iterations")

    args = parser.parse_args()
    run_simulation(
        api_url=args.url,
        lat=args.lat,
        lon=args.lon,
        api_key=args.key,
        interval_seconds=args.interval,
        single_run=args.single_run,
        iterations=args.iterations
    )


if __name__ == "__main__":
    main()
