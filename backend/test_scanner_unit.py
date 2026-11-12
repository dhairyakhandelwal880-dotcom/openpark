"""
Unit tests for AI Parking Scanner classifier heuristics and rules.
"""
import asyncio
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.ai_parking_scanner import (
    _matches_any_word,
    _has_non_parking_name,
    classify_and_score_candidate,
    scan_map_for_parking
)


def test_matches_any_word():
    assert _matches_any_word("Orion Mall East", ("mall", "plaza")) is True
    assert _matches_any_word("Local bakery shop", ("mall", "plaza")) is False
    assert _matches_any_word("", ("mall",)) is False
    assert _matches_any_word("Mall,", ("mall",)) is True  # punctuation stripped


def test_has_non_parking_name():
    # Names of places that are NOT parking spots
    assert _has_non_parking_name("Stanza Living Debrecan House Boys PG") is True
    assert _has_non_parking_name("Zolo Colive PG") is True
    assert _has_non_parking_name("Green Valley Apartments") is True
    assert _has_non_parking_name("Shri Krishna Temple") is True

    # Real parking names
    assert _has_non_parking_name("Metro Parking Bay") is False
    assert _has_non_parking_name("Forum Mall Parking") is False
    assert _has_non_parking_name(None) is False


def test_classify_candidate_illegal_access_rejected():
    tags = {"amenity": "parking", "access": "private"}
    result = classify_and_score_candidate(tags, name="Private Lot", area_m2=200, dist_m=100)
    assert result is None

    tags_no = {"amenity": "parking", "access": "no"}
    assert classify_and_score_candidate(tags_no, name="No Entry", area_m2=200, dist_m=100) is None


def test_classify_candidate_mall():
    tags = {"shop": "mall"}
    result = classify_and_score_candidate(tags, name="Phoenix Marketcity", area_m2=1500, dist_m=200)
    assert result is not None
    assert result["category"] == "mall_parking"
    assert result["badge"] == "🛍️"
    assert result["estimated_spots"] > 20


def test_classify_candidate_empty_ground_limits():
    # Small empty ground (holds 3-6 cars)
    tags = {"landuse": "brownfield", "surface": "dirt"}
    result = classify_and_score_candidate(tags, name="Empty Plot", area_m2=180, dist_m=50)
    assert result is not None
    assert result["category"] == "empty_ground"
    assert result["badge"] == "🟩"
    assert 3 <= result["estimated_spots"] <= 6

    # Oversized ground (> 1200 m2) should be rejected to avoid recommending football stadiums / huge private properties
    oversized = classify_and_score_candidate(tags, name="Huge Ground", area_m2=2500, dist_m=50)
    assert oversized is None

    # Undersized ground (< 60 m2) should be rejected (too small for safe parking)
    undersized = classify_and_score_candidate(tags, name="Tiny Patch", area_m2=30, dist_m=50)
    assert undersized is None


def test_classify_candidate_legal_bay():
    tags = {"amenity": "parking", "parking": "surface"}
    result = classify_and_score_candidate(tags, name="Public Car Park", area_m2=350, dist_m=120)
    assert result is not None
    assert result["category"] == "legal_bay"
    assert result["badge"] == "🅿️"


def test_ai_scan_max_five_results():
    # Run scan on local test coordinates with use_live_overpass=False (using cached/fallback features)
    scan = asyncio.run(scan_map_for_parking(
        lat=12.90310,
        lon=77.49750,
        radius_m=1000,
        use_live_overpass=False
    ))
    assert scan["status"] == "ok"
    assert len(scan["results"]) <= 5
    assert len(scan["geojson"]["features"]) <= 5
    assert scan["summary"]["total_found"] <= 5

