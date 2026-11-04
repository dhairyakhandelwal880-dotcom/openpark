-- OpenPark Database Schema
-- Step 3: Enable PostGIS and define tables for parking lots, availability, and crowd reports

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS parking_lots (
    id BIGSERIAL PRIMARY KEY,
    osm_ref TEXT UNIQUE, -- e.g. 'way/12345' or 'node/67890'
    name TEXT,
    city TEXT,
    geom GEOGRAPHY(Point, 4326) NOT NULL,
    capacity INT,
    price_note TEXT,
    source TEXT DEFAULT 'osm'
);

CREATE INDEX IF NOT EXISTS parking_lots_geom_idx ON parking_lots USING GIST (geom);

CREATE TABLE IF NOT EXISTS availability (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT REFERENCES parking_lots(id) ON DELETE CASCADE,
    free_spots INT NOT NULL,
    source TEXT NOT NULL, -- sensor | operator | crowd | predicted
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS availability_lot_time_idx ON availability (lot_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT REFERENCES parking_lots(id) ON DELETE CASCADE,
    kind TEXT NOT NULL, -- got_spot | lot_full | has_space
    reporter_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS reports_lot_time_idx ON reports (lot_id, created_at DESC);
