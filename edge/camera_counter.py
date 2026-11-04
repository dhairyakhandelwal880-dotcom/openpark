#!/usr/bin/env python3
"""
OpenPark - Edge Device Camera & Sensor Counter
-----------------------------------------------
Step 16: Automated vehicle entry/exit counter for edge devices (Raspberry Pi, Jetson Nano, IP Camera).
Detects vehicle pass-through events and sends real-time spot updates to the OpenPark backend.
"""

import argparse
import time
import requests

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_API_KEY = "dev-key"


class EdgeVehicleCounter:
    def __init__(self, lot_id: int, api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY):
        self.lot_id = lot_id
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        self.free_spots = None
        self.capacity = None

    def sync_lot_state(self):
        try:
            res = requests.get(f"{self.api_url}/lots/{self.lot_id}", timeout=5)
            res.raise_for_status()
            data = res.json()
            self.capacity = data.get("capacity", 50)
            self.free_spots = data.get("free_spots") if data.get("free_spots") is not None else self.capacity
            print(f"[Edge] Synced Lot #{self.lot_id}: {self.free_spots}/{self.capacity} free spots.")
        except Exception as e:
            print(f"[Edge Error] Could not fetch lot status: {e}")
            if self.free_spots is None:
                self.free_spots = 30
                self.capacity = 50

    def record_entry(self):
        """Called when an entry sensor or vision gate detects a vehicle entering."""
        if self.free_spots is None:
            self.sync_lot_state()
        self.free_spots = max(0, self.free_spots - 1)
        print(f"[Edge Event] Vehicle ENTERED -> Free spots now: {self.free_spots}")
        self._push_update()

    def record_exit(self):
        """Called when an exit sensor or vision gate detects a vehicle leaving."""
        if self.free_spots is None:
            self.sync_lot_state()
        self.free_spots = min(self.capacity or 50, self.free_spots + 1)
        print(f"[Edge Event] Vehicle EXITED -> Free spots now: {self.free_spots}")
        self._push_update()

    def _push_update(self):
        try:
            res = requests.post(
                f"{self.api_url}/lots/{self.lot_id}/availability",
                headers=self.headers,
                json={"free_spots": self.free_spots, "source": "sensor"},
                timeout=4
            )
            if res.ok:
                print(f"[Edge Success] Dispatched availability to cloud.")
            else:
                print(f"[Edge Warning] Server returned {res.status_code}")
        except Exception as e:
            print(f"[Edge Error] Failed to send update: {e}")


def main():
    parser = argparse.ArgumentParser(description="OpenPark Edge Vehicle Counter")
    parser.add_argument("--lot-id", type=int, default=1, help="Parking lot ID")
    parser.add_argument("--url", default=DEFAULT_API_URL, help="OpenPark API server URL")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="Operator/Sensor API key")
    parser.add_argument("--demo", action="store_true", help="Run simulated entry/exit events for testing")
    args = parser.parse_args()

    counter = EdgeVehicleCounter(lot_id=args.lot_id, api_url=args.url, api_key=args.key)
    counter.sync_lot_state()

    if args.demo:
        print("Running edge camera demonstration loop...")
        import random
        for _ in range(5):
            time.sleep(2)
            if random.random() > 0.5:
                counter.record_entry()
            else:
                counter.record_exit()
        print("Demo completed.")


if __name__ == "__main__":
    main()
