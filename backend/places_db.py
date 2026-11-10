"""
OpenPark Offline Places Database Engine (SQLite FTS5)
Provides high-performance full-text search across millions of places, buildings,
shops, PGs, hospitals, and addresses with sub-millisecond query latency.
"""

import gzip
import os
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("openpark.places_db")

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "places_search.db")
)
OVERTURE_ARCHIVE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "overture_places_openpark.json.gz")
)
_HYDRATED_DB_PATHS = set()


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_places_db(db_path: str = DB_PATH):
    """Initializes tables and FTS5 full-text search index."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS places (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            badge TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            lat REAL,
            lon REAL,
            phone TEXT,
            website TEXT,
            rating REAL,
            reviews_count INTEGER,
            source TEXT
        )
    """)
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS places_fts USING fts5(
            name,
            category,
            address,
            city,
            content='places',
            content_rowid='rowid'
        )
    """)
    # Triggers to keep FTS in sync with main table
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS places_ai AFTER INSERT ON places BEGIN
            INSERT INTO places_fts(rowid, name, category, address, city)
            VALUES (new.rowid, new.name, new.category, new.address, new.city);
        END;
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS places_ad AFTER DELETE ON places BEGIN
            INSERT INTO places_fts(places_fts, rowid, name, category, address, city)
            VALUES('delete', old.rowid, old.name, old.category, old.address, old.city);
        END;
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_places_lat_lon ON places(lat, lon)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS verified_pockets (
            pocket_id TEXT PRIMARY KEY,
            name TEXT,
            lat REAL,
            lon REAL,
            open_votes INTEGER DEFAULT 0,
            blocked_votes INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def insert_places_batch(places: List[Dict[str, Any]], db_path: str = DB_PATH) -> int:
    """Inserts or replaces a batch of places cleanly in a single fast transaction."""
    if not places:
        return 0
    init_places_db(db_path)
    conn = get_db_connection(db_path)
    conn.execute("PRAGMA synchronous = NORMAL")
    cur = conn.cursor()
    rows = [
        (
            str(p.get("id") or f"{p.get('lat')}_{p.get('lon')}_{p.get('name')}"),
            str(p.get("name") or "Unnamed Place"),
            str(p.get("category") or "Building"),
            str(p.get("badge") or "🏢"),
            str(p.get("address") or ""),
            str(p.get("city") or "Bengaluru"),
            str(p.get("state") or "Karnataka"),
            float(p.get("lat") or 0.0),
            float(p.get("lon") or 0.0),
            p.get("phone") or "",
            p.get("website") or "",
            float(p.get("rating") or 4.5),
            int(p.get("reviews_count") or 150),
            str(p.get("source") or "dataset"),
        )
        for p in places
    ]
    cur.executemany("""
        INSERT OR REPLACE INTO places (
            id, name, category, badge, address, city, state,
            lat, lon, phone, website, rating, reviews_count, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()
    return len(rows)


def ensure_overture_hydrated(db_path: str = DB_PATH) -> None:
    """Auto-loads compact Overture Maps archive on cold server boot (only for default DB_PATH)."""
    abs_path = os.path.abspath(db_path)
    if abs_path in _HYDRATED_DB_PATHS or abs_path != DB_PATH:
        return
    _HYDRATED_DB_PATHS.add(abs_path)
    if not os.path.exists(OVERTURE_ARCHIVE_PATH):
        return
    try:
        conn = get_db_connection(abs_path)
        cur = conn.cursor()
        has_ovt = cur.execute("SELECT 1 FROM places WHERE source LIKE 'overture%' LIMIT 1").fetchone()
        conn.close()
        if not has_ovt:
            with gzip.open(OVERTURE_ARCHIVE_PATH, "rt", encoding="utf-8") as gz:
                places = json.load(gz)
            if places:
                n = insert_places_batch(places, db_path=abs_path)
                logger.info("Auto-hydrated %d Overture Maps POIs into %s", n, abs_path)
    except Exception as exc:
        logger.warning("Overture auto-hydration skipped: %s", exc)


def search_places_fts(query: str, limit: int = 15, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Fast FTS5 search query across place name, category, and address."""
    init_places_db(db_path)
    ensure_overture_hydrated(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
    if not clean_q:
        conn.close()
        return []

    # Prepare FTS wildcard prefix query
    words = clean_q.split()
    fts_expr = " ".join(f'"{w}"*' for w in words)

    try:
        cur.execute("""
            SELECT p.*, rank
            FROM places_fts f
            JOIN places p ON f.rowid = p.rowid
            WHERE places_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_expr, limit))
        rows = cur.fetchall()
        results = [dict(r) for r in rows]
    except Exception as e:
        logger.warning("FTS query failed, fallback to LIKE: %s", e)
        like_expr = f"%{clean_q}%"
        cur.execute("""
            SELECT * FROM places
            WHERE name LIKE ? OR address LIKE ? OR category LIKE ?
            LIMIT ?
        """, (like_expr, like_expr, like_expr, limit))
        results = [dict(r) for r in cur.fetchall()]

    conn.close()
    return results


def search_places_nearby(
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    category: Optional[str] = None,
    limit: int = 20,
    db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """
    Finds places within a given radius (km) of coordinates using Haversine calculation.
    Supports optional category filtering (e.g. 'Hospital', 'Hotel', 'Restaurant', 'Parking').
    """
    import math
    init_places_db(db_path)
    ensure_overture_hydrated(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # Bounding box rough pre-filter (~111 km per latitude degree, ~108 km per longitude at 13 deg N)
    d_lat = radius_km / 111.0
    d_lon = radius_km / (111.0 * math.cos(math.radians(lat)))

    query = """
        SELECT * FROM places
        WHERE lat BETWEEN ? AND ?
          AND lon BETWEEN ? AND ?
    """
    params = [lat - d_lat, lat + d_lat, lon - d_lon, lon + d_lon]

    if category:
        query += " AND (category LIKE ? OR name LIKE ?)"
        params.extend([f"%{category}%", f"%{category}%"])

    cur.execute(query, params)
    candidates = [dict(r) for r in cur.fetchall()]
    conn.close()

    # Exact Haversine distance filtering and ranking
    results = []
    r_earth = 6371.0
    for p in candidates:
        p_lat = p["lat"]
        p_lon = p["lon"]
        dlat = math.radians(p_lat - lat)
        dlon = math.radians(p_lon - lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat)) * math.cos(math.radians(p_lat)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        dist_km = r_earth * c
        if dist_km <= radius_km:
            p["distance_km"] = round(dist_km, 2)
            results.append(p)

    results.sort(key=lambda x: x["distance_km"])
    return results[:limit]


def get_places_stats(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Returns total count and summary of indexed places."""
    init_places_db(db_path)
    ensure_overture_hydrated(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM places")
    total = cur.fetchone()["total"]

    cur.execute("""
        SELECT category, COUNT(*) AS count
        FROM places
        GROUP BY category
        ORDER BY count DESC
        LIMIT 8
    """)
    top_categories = {r["category"]: r["count"] for r in cur.fetchall()}
    conn.close()

    return {
        "total_places": total,
        "database_path": db_path,
        "top_categories": top_categories
    }


def update_place_coordinates(name_query: str, lat: float, lon: float, db_path: str = DB_PATH) -> bool:
    """Updates the latitude and longitude of a place by name in the SQLite database."""
    init_places_db(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE places SET lat = ?, lon = ? WHERE name LIKE ?", (lat, lon, f"%{name_query}%"))
    changed = cur.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def record_pocket_verification(
    pocket_id: str,
    name: str,
    lat: float,
    lon: float,
    verdict: str,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """Persists driver crowd verification ('open' or 'blocked') for an AI-discovered ground."""
    from datetime import datetime, timezone
    init_places_db(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    open_inc = 1 if verdict == "open" else 0
    blocked_inc = 1 if verdict == "blocked" else 0
    cur.execute(
        """
        INSERT INTO verified_pockets (pocket_id, name, lat, lon, open_votes, blocked_votes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pocket_id) DO UPDATE SET
            name = excluded.name,
            open_votes = verified_pockets.open_votes + excluded.open_votes,
            blocked_votes = verified_pockets.blocked_votes + excluded.blocked_votes,
            updated_at = excluded.updated_at
        """,
        (pocket_id, name, float(lat), float(lon), open_inc, blocked_inc, now_iso),
    )
    row = cur.execute("SELECT * FROM verified_pockets WHERE pocket_id = ?", (pocket_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row) if row else {"pocket_id": pocket_id, "open_votes": open_inc, "blocked_votes": blocked_inc}


def get_verified_pockets_map(db_path: str = DB_PATH) -> Dict[str, Dict[str, Any]]:
    """Returns pocket_id -> verification vote counts from SQLite."""
    init_places_db(db_path)
    conn = get_db_connection(db_path)
    rows = conn.execute("SELECT * FROM verified_pockets").fetchall()
    conn.close()
    return {r["pocket_id"]: dict(r) for r in rows}
