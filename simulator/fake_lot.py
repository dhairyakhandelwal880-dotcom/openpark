"""
OpenPark - Parking Lot Simulator
--------------------------------
Simulates a parking lot where cars arrive and depart randomly.
Every few seconds, a random parking bay flips its status between
'free' and 'occupied', then sends an HTTP POST update to the backend.

Designed for beginners:
- Clear configuration settings at the top
- Uses only Python standard library (no external packages to install!)
- Handles connection errors gracefully if backend is not yet started
"""

from datetime import datetime
import json
import random
import time
import urllib.error
import urllib.request

# ==============================================================================
# CONFIGURATION SETTINGS
# You can change these numbers to experiment with different parking lots!
# ==============================================================================
LOT_ID: str = "A"               # Identifier for this parking lot (e.g. "A", "North", "B")
TOTAL_BAYS: int = 30            # Total number of parking bays in the lot (1 to 30)
DELAY_SECONDS: float = 2.0      # How many seconds to wait between state changes
BACKEND_URL: str = "http://localhost:8000/bays/update"  # Backend API endpoint


def send_update(payload: dict) -> None:
    """
    Sends a single bay update to the backend server via an HTTP POST request.
    
    If the backend is offline (e.g., during Phase 1 testing before Phase 2 is built),
    it catches the error and informs you without crashing the simulation.
    """
    # Convert Python dictionary to a JSON-formatted string and then to bytes
    json_bytes = json.dumps(payload).encode("utf-8")

    # Prepare standard HTTP POST request with Content-Type header
    req = urllib.request.Request(
        url=BACKEND_URL,
        data=json_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        # Send the request with a 2-second timeout
        with urllib.request.urlopen(req, timeout=2.0) as response:
            status_code = response.getcode()
            print(f" -> [HTTP {status_code}] Successfully sent to backend!\n")
    except urllib.error.URLError:
        # Backend is not running yet; this is expected in Phase 1
        print(" -> [Notice] Backend not reachable yet at http://localhost:8000 (normal for Phase 1)\n")
    except Exception as e:
        # Any other unexpected network error
        print(f" -> [Warning] Could not send update: {e}\n")


def run_simulator() -> None:
    """
    Main simulator loop.
    1. Keeps track of the current state of every bay in memory.
    2. Randomly flips one bay between 'free' and 'occupied' every DELAY_SECONDS.
    3. Prints and sends the contract message.
    """
    # Start with all bays marked as 'free' (bay numbers 1 to 30)
    bay_states = {bay_number: "free" for bay_number in range(1, TOTAL_BAYS + 1)}

    print("=" * 60)
    print("  OpenPark Simulator Started")
    print(f"  Lot: {LOT_ID} | Total Bays: {TOTAL_BAYS} | Interval: {DELAY_SECONDS}s")
    print(f"  Target: {BACKEND_URL}")
    print("  Press Ctrl+C to stop the simulator anytime.")
    print("=" * 60)
    print()

    step_count = 0

    try:
        while True:
            step_count += 1

            # 1. Pick a random bay from 1 to TOTAL_BAYS
            target_bay = random.randint(1, TOTAL_BAYS)

            # 2. Flip the state: free -> occupied, or occupied -> free
            previous_state = bay_states[target_bay]
            new_state = "occupied" if previous_state == "free" else "free"
            bay_states[target_bay] = new_state

            # 3. Create ISO 8601 timestamp string (e.g. 2026-10-31T11:50:00)
            timestamp = datetime.now().isoformat(timespec="seconds")

            # 4. Form the exact JSON message according to docs/messages.md
            message = {
                "lot": LOT_ID,
                "bay": target_bay,
                "state": new_state,
                "time": timestamp,
            }

            # 5. Print the message nicely to the console
            print(f"[Event #{step_count}] Bay {target_bay} changed: {previous_state} -> {new_state}")
            print(f"Payload: {json.dumps(message)}")

            # 6. Send the message via HTTP POST to the backend
            send_update(message)

            # 7. Wait before the next flip
            time.sleep(DELAY_SECONDS)

    except KeyboardInterrupt:
        # Cleanly handle Ctrl+C stopping
        print("\nSimulator stopped by user. Goodbye!")


if __name__ == "__main__":
    run_simulator()
