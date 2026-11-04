#!/usr/bin/env python3
"""
OpenPark - Seed OpenCity Bengaluru Parking Lots into PostgreSQL / PostGIS.
Dataset: https://data.opencity.in/dataset/bengaluru-parking-lots
"""

import os
import json
import psycopg2
from psycopg2.extras import execute_values

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://openpark:openpark@localhost:5432/openpark"
)

DATA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "bengaluru_parking_opencity.json")
)


def seed_opencity():
    if not os.path.exists(DATA_PATH):
        print(f"Dataset not found at {DATA_PATH}. Running extractor...")
        import subprocess
        subprocess.run(["python3", os.path.join(os.path.dirname(__file__), "..", "data", "process_opencity.py")], check=True)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        lots = json.load(f)

    print(f"Loaded {len(lots)} parking lots from OpenCity dataset.")

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    except Exception as e:
        print(f"Could not connect to PostgreSQL ({e}). Please ensure database container is running.")
        return

    try:
        with conn:
            with conn.cursor() as cur:
                # Ensure schema exists
                cur.execute("""
                    CREATE EXTENSION IF NOT EXISTS postgis;
                    CREATE TABLE IF NOT EXISTS parking_lots (
                        id BIGSERIAL PRIMARY KEY,
                        osm_ref TEXT UNIQUE,
                        name TEXT,
                        city TEXT,
                        geom GEOGRAPHY(Point, 4326) NOT NULL,
                        capacity INT,
                        price_note TEXT,
                        source TEXT DEFAULT 'opencity'
                    );
                    CREATE INDEX IF NOT EXISTS parking_lots_geom_idx ON parking_lots USING GIST (geom);
                    CREATE TABLE IF NOT EXISTS availability (
                        id BIGSERIAL PRIMARY KEY,
                        lot_id BIGINT REFERENCES parking_lots(id) ON DELETE CASCADE,
                        free_spots INT NOT NULL,
                        source TEXT NOT NULL,
                        updated_at TIMESTAMPTZ DEFAULT now()
                    );
                    CREATE INDEX IF NOT EXISTS availability_lot_time_idx ON availability (lot_id, updated_at DESC);
                """)

                inserted = 0
                for lot in lots:
                    cur.execute("""
                        INSERT INTO parking_lots (osm_ref, name, city, geom, capacity, price_note, source)
                        VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s, %s)
                        ON CONFLICT (osm_ref) DO UPDATE SET
                            name = EXCLUDED.name,
                            geom = EXCLUDED.geom,
                            capacity = EXCLUDED.capacity,
                            price_note = EXCLUDED.price_note,
                            source = EXCLUDED.source
                        RETURNING id;
                    """, (
                        lot["osm_ref"],
                        lot["name"],
                        "Bengaluru",
                        lot["lon"],
                        lot["lat"],
                        lot["capacity"],
                        lot.get("price_note", "₹20/hr"),
                        "opencity"
                    ))
                    lot_id = cur.fetchone()[0]

                    # Initial availability record
                    cur.execute("""
                        INSERT INTO availability (lot_id, free_spots, source, updated_at)
                        VALUES (%s, %s, 'sensor', NOW())
                    """, (lot_id, lot.get("free_spots", int(lot["capacity"] * 0.5))))

                    inserted += 1

                print(f"Successfully seeded {inserted} OpenCity parking lots into PostgreSQL PostGIS database!")

    finally:
        conn.close()


if __name__ == "__main__":
    seed_opencity()
