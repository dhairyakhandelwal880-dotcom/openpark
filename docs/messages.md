# OpenPark Message Format (The Contract)

This document defines the standard message format used for all spot updates in **openpark**. Every component in the system (the fake simulator, future camera edge devices, backend API, and dashboard) follows this exact contract.

---

## The Message Schema

Every spot state change is sent as a single JSON object:

```json
{
  "lot": "A",
  "bay": 14,
  "state": "occupied",
  "time": "2026-10-31T11:50:00"
}
```

---

## Field Descriptions

| Field | Type | Allowed Values | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `lot` | `string` | Any non-empty string | The identifier of the parking lot | `"A"` |
| `bay` | `integer` | Positive integer (e.g. `1` to `30`) | The specific parking spot number inside the lot | `14` |
| `state` | `string` | `"free"` or `"occupied"` | Whether a vehicle is currently parked in the bay | `"occupied"` |
| `time` | `string` | ISO 8601 timestamp string (`YYYY-MM-DDTHH:MM:SS`) | The local or UTC timestamp when the state change occurred | `"2026-10-31T11:50:00"` |

---

## Transport Details

- **HTTP Method:** `POST`
- **Endpoint:** `/bays/update` (e.g., `http://localhost:8000/bays/update`)
- **Headers:** `Content-Type: application/json`
- **Expected Backend Response:** HTTP `200 OK` with JSON confirmation (e.g. `{"status": "updated", "lot": "A", "bay": 14, "state": "occupied"}`)

---

## Rules & Constraints

1. **No changes to this contract**: All tools and scripts must adhere to these exact keys and casing.
2. **Strict state values**: `state` can **only** be `"free"` or `"occupied"`. Other values (such as `"empty"`, `"taken"`, or `true`/`false`) are invalid.
3. **No privacy or image data**: Only numeric bay IDs and occupancy status are sent. No camera pictures, license plates, or driver information are ever transmitted or stored.
