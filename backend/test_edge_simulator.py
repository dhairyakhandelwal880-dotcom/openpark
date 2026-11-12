"""
Tests for Edge Camera Vehicle Counter and Simulator modules.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Ensure repo root and subdirs are in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from edge.camera_counter import EdgeVehicleCounter
from simulator.fake_lots import get_nearest_lots, run_simulation


def test_edge_counter_init():
    counter = EdgeVehicleCounter(lot_id=42, api_url="http://testserver:8000", api_key="secret-key")
    assert counter.lot_id == 42
    assert counter.api_url == "http://testserver:8000"
    assert counter.headers["x-api-key"] == "secret-key"
    assert counter.free_spots is None
    assert counter.capacity is None


def test_edge_counter_sync_success():
    counter = EdgeVehicleCounter(lot_id=5)
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"id": 5, "capacity": 80, "free_spots": 22}

    with patch("requests.get", return_value=mock_resp) as mock_get:
        counter.sync_lot_state()
        mock_get.assert_called_once_with("http://localhost:8000/lots/5", timeout=5)
        assert counter.capacity == 80
        assert counter.free_spots == 22


def test_edge_counter_sync_fallback():
    counter = EdgeVehicleCounter(lot_id=9)
    with patch("requests.get", side_effect=Exception("Connection refused")):
        counter.sync_lot_state()
        assert counter.capacity == 50
        assert counter.free_spots == 30


def test_edge_counter_entry_decrements_and_floors():
    counter = EdgeVehicleCounter(lot_id=1)
    counter.capacity = 50
    counter.free_spots = 1

    with patch.object(counter, "_push_update") as mock_push:
        counter.record_entry()
        assert counter.free_spots == 0
        mock_push.assert_called_once()

        counter.record_entry()
        assert counter.free_spots == 0  # does not go negative


def test_edge_counter_exit_increments_and_clamps():
    counter = EdgeVehicleCounter(lot_id=1)
    counter.capacity = 10
    counter.free_spots = 9

    with patch.object(counter, "_push_update") as mock_push:
        counter.record_exit()
        assert counter.free_spots == 10
        mock_push.assert_called_once()

        counter.record_exit()
        assert counter.free_spots == 10  # clamped to capacity


def test_edge_counter_push_update_network_error():
    counter = EdgeVehicleCounter(lot_id=2)
    counter.free_spots = 15
    with patch("requests.post", side_effect=Exception("Timeout")):
        # Should catch gracefully and not raise
        counter._push_update()


def test_simulator_get_nearest_lots_primary():
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = [{"id": i, "name": f"Lot {i}", "capacity": 50} for i in range(1, 10)]

    with patch("requests.get", return_value=mock_resp):
        lots = get_nearest_lots("http://localhost:8000", 12.97, 77.59, count=5)
        assert len(lots) == 5
        assert lots[0]["id"] == 1


def test_simulator_get_nearest_lots_fallback_synthetic():
    with patch("requests.get", side_effect=Exception("Backend down")):
        lots = get_nearest_lots("http://localhost:8000", 12.97, 77.59, count=8)
        assert len(lots) == 8
        assert lots[0]["id"] == 1
        assert lots[0]["capacity"] == 50
        assert "name" in lots[0]


def test_simulator_run_simulation_single_iteration():
    mock_lots = [
        {"id": 101, "name": "Mall A", "capacity": 40, "free_spots": 20},
        {"id": 102, "name": "Ground B", "capacity": 20, "free_spots": 5},
    ]

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200

    with patch("simulator.fake_lots.get_nearest_lots", return_value=mock_lots):
        with patch("requests.post", return_value=mock_post_resp) as mock_post:
            run_simulation(
                api_url="http://testserver:8000",
                lat=12.97,
                lon=77.59,
                single_run=True,
                iterations=1
            )
            assert mock_post.call_count == 2
