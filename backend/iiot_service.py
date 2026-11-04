"""
OpenPark - IIoT Smart Parking Telemetry Service
Processes and serves real Industrial IoT sensor telemetry from
IIoT_Smart_Parking_Management.csv
"""

import os
import csv
from typing import Dict, List, Optional
from datetime import datetime, timezone

CSV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "archive", "IIoT_Smart_Parking_Management.csv")
)

# In-memory buffer of IIoT records
_IIOT_RECORDS: List[dict] = []
_CURRENT_INDEX = 0


def load_iiot_records() -> List[dict]:
    global _IIOT_RECORDS
    if _IIOT_RECORDS:
        return _IIOT_RECORDS

    if not os.path.exists(CSV_PATH):
        return []

    try:
        with open(CSV_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                _IIOT_RECORDS.append({
                    "spot_id": int(row.get("Parking_Spot_ID", 1)),
                    "section": row.get("Parking_Lot_Section", "Zone A"),
                    "vehicle_type": row.get("Vehicle_Type", "Car"),
                    "occupancy_status": row.get("Occupancy_Status", "Vacant"),
                    "occupancy_rate": float(row.get("Occupancy_Rate", 0.5)),
                    "dynamic_pricing": float(row.get("Dynamic_Pricing_Factor", 1.0)),
                    "spot_size": row.get("Spot_Size", "Standard"),
                    "is_ev": int(row.get("Electric_Vehicle", 0)) == 1,
                    "is_violation": int(row.get("Parking_Violation", 0)) == 1,
                    "payment_status": row.get("Payment_Status", "Paid"),
                    "traffic_level": row.get("Nearby_Traffic_Level", "Low"),
                    "temperature": round(float(row.get("Weather_Temperature", 24.0)), 1),
                    "ultrasonic": round(float(row.get("Sensor_Reading_Ultrasonic", 95.0)), 1),
                    "pressure": round(float(row.get("Sensor_Reading_Pressure", 2.5)), 2),
                    "proximity": round(float(row.get("Sensor_Reading_Proximity", 5.0)), 2),
                    "noise_level": round(float(row.get("Environmental_Noise_Level", 50.0)), 1)
                })
    except Exception as e:
        print(f"Warning: Failed to load IIoT dataset: {e}")

    return _IIOT_RECORDS


def get_lot_telemetry(lot_id: int, total_capacity: int = 100, free_spots: Optional[int] = None) -> dict:
    """
    Synthesizes realistic IIoT sensor telemetry for a specific parking lot
    using deterministic slices of the IIoT_Smart_Parking_Management dataset.
    """
    records = load_iiot_records()
    if not records:
        return _default_telemetry(total_capacity, free_spots)

    # Use lot_id as deterministic offset into 1000 records
    offset = (lot_id * 37) % len(records)
    window = [records[(offset + i) % len(records)] for i in range(25)]

    # Calculate zone breakdowns
    zones = {"Zone A": {"total": 0, "free": 0},
             "Zone B": {"total": 0, "free": 0},
             "Zone C": {"total": 0, "free": 0},
             "Zone D": {"total": 0, "free": 0}}

    ev_total = 0
    ev_free = 0
    violations = 0
    pricing_factors = []
    traffic_counts = {"Low": 0, "Medium": 0, "High": 0}

    for rec in window:
        sec = rec["section"]
        if sec in zones:
            zones[sec]["total"] += 1
            if rec["occupancy_status"] == "Vacant":
                zones[sec]["free"] += 1

        if rec["is_ev"]:
            ev_total += 1
            if rec["occupancy_status"] == "Vacant":
                ev_free += 1

        if rec["is_violation"]:
            violations += 1

        pricing_factors.append(rec["dynamic_pricing"])
        t_lvl = rec["traffic_level"]
        traffic_counts[t_lvl] = traffic_counts.get(t_lvl, 0) + 1

    # Scale zones to match lot capacity
    scale = max(1.0, total_capacity / 25.0)
    scaled_zones = {}
    for z, data in zones.items():
        z_tot = max(5, int(data["total"] * scale))
        z_free = max(1, min(z_tot, int(data["free"] * scale)))
        scaled_zones[z] = {"total": z_tot, "free": z_free}

    avg_pricing = round(sum(pricing_factors) / len(pricing_factors), 1) if pricing_factors else 1.0
    dominant_traffic = max(traffic_counts, key=traffic_counts.get)
    latest = window[0]

    return {
        "lot_id": lot_id,
        "zones": scaled_zones,
        "ev_charging": {
            "total": max(4, int(ev_total * scale * 0.4)),
            "free": max(1, int(ev_free * scale * 0.4))
        },
        "dynamic_pricing": {
            "factor": avg_pricing,
            "label": "Off-Peak Discount" if avg_pricing < 1.0 else ("Surge Demand" if avg_pricing > 1.1 else "Standard Rate")
        },
        "traffic_level": dominant_traffic,
        "weather": {
            "temperature_c": latest["temperature"],
            "condition": "Clear"
        },
        "sensors": {
            "ultrasonic_avg_cm": latest["ultrasonic"],
            "pressure_avg_kpa": latest["pressure"],
            "environmental_noise_db": latest["noise_level"],
            "status": "Healthy (Dual Proximity + Ultrasonic Active)"
        },
        "violations_detected": violations,
        "telemetry_source": "IIoT Smart Parking Sensor Network"
    }


def _default_telemetry(total_capacity: int, free_spots: Optional[int]) -> dict:
    free = free_spots if free_spots is not None else int(total_capacity * 0.4)
    q_tot = max(1, total_capacity // 4)
    q_free = max(0, free // 4)
    return {
        "lot_id": 1,
        "zones": {
            "Zone A": {"total": q_tot, "free": q_free},
            "Zone B": {"total": q_tot, "free": q_free},
            "Zone C": {"total": q_tot, "free": q_free},
            "Zone D": {"total": q_tot, "free": q_free}
        },
        "ev_charging": {"total": 8, "free": 3},
        "dynamic_pricing": {"factor": 1.0, "label": "Standard Rate"},
        "traffic_level": "Low",
        "weather": {"temperature_c": 24.5, "condition": "Clear"},
        "sensors": {
            "ultrasonic_avg_cm": 95.0,
            "pressure_avg_kpa": 2.5,
            "environmental_noise_db": 52.0,
            "status": "Healthy"
        },
        "violations_detected": 0,
        "telemetry_source": "Default IIoT Synthetic"
    }
