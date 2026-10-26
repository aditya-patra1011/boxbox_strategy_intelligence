"""
Local SQLite store for Race Centre data. The ingest worker is the only writer;
the Dash app opens it read-only (dash_app/race_data.py).
"""

import os
import sqlite3
from pathlib import Path

BASE = Path(os.environ.get("BOXBOX_BASE", Path(__file__).resolve().parent.parent))
DEFAULT_PATH = BASE / "data" / "race_centre" / "boxbox.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS races (
    season INTEGER, round INTEGER, race_name TEXT,
    circuit_id TEXT, circuit_name TEXT, locality TEXT, country TEXT, lat REAL, lon REAL,
    race_utc TEXT, fp1_utc TEXT, fp2_utc TEXT, fp3_utc TEXT,
    sprint_qualifying_utc TEXT, sprint_utc TEXT, qualifying_utc TEXT,
    PRIMARY KEY (season, round)
);
CREATE TABLE IF NOT EXISTS drivers (
    driver_id TEXT PRIMARY KEY, code TEXT, number INTEGER, given_name TEXT, family_name TEXT,
    date_of_birth TEXT, nationality TEXT
);
CREATE TABLE IF NOT EXISTS constructors (
    constructor_id TEXT PRIMARY KEY, name TEXT, nationality TEXT
);
CREATE TABLE IF NOT EXISTS results (
    season INTEGER, round INTEGER, driver_id TEXT, constructor_id TEXT, number INTEGER,
    grid INTEGER, position INTEGER, position_text TEXT, points REAL, laps INTEGER, status TEXT,
    time_text TEXT, time_millis INTEGER,
    fastest_lap_rank INTEGER, fastest_lap_lap INTEGER, fastest_lap_time TEXT,
    PRIMARY KEY (season, round, driver_id)
);
CREATE TABLE IF NOT EXISTS driver_standings (
    season INTEGER, round INTEGER, driver_id TEXT, constructor_id TEXT,
    position INTEGER, position_text TEXT, points REAL, wins INTEGER,
    PRIMARY KEY (season, round, driver_id)
);
CREATE TABLE IF NOT EXISTS constructor_standings (
    season INTEGER, round INTEGER, constructor_id TEXT,
    position INTEGER, position_text TEXT, points REAL, wins INTEGER,
    PRIMARY KEY (season, round, constructor_id)
);
CREATE TABLE IF NOT EXISTS ingest_log (
    run_utc TEXT, season INTEGER, races INTEGER, results INTEGER, standings_rounds TEXT, requests INTEGER
);

-- One OpenF1 session (python -m ingest.session), replayed by Race Live and Race Analysis.
CREATE TABLE IF NOT EXISTS sessions (
    session_key INTEGER PRIMARY KEY, meeting_key INTEGER, season INTEGER, round INTEGER, circuit_id TEXT,
    session_type TEXT, session_name TEXT, date_start TEXT, date_end TEXT, total_laps INTEGER, ingested_utc TEXT
);
CREATE TABLE IF NOT EXISTS session_drivers (
    session_key INTEGER, driver_number INTEGER, code TEXT, first_name TEXT, last_name TEXT,
    team_name TEXT, team_colour TEXT,
    PRIMARY KEY (session_key, driver_number)
);
CREATE TABLE IF NOT EXISTS laps (
    session_key INTEGER, driver_number INTEGER, lap_number INTEGER, date_start TEXT, lap_duration REAL,
    s1 REAL, s2 REAL, s3 REAL, i1_speed REAL, i2_speed REAL, st_speed REAL, is_pit_out_lap INTEGER,
    PRIMARY KEY (session_key, driver_number, lap_number)
);
CREATE TABLE IF NOT EXISTS stints (
    session_key INTEGER, driver_number INTEGER, stint_number INTEGER, compound TEXT,
    lap_start INTEGER, lap_end INTEGER, tyre_age_at_start INTEGER,
    PRIMARY KEY (session_key, driver_number, stint_number)
);
CREATE TABLE IF NOT EXISTS pits (
    session_key INTEGER, driver_number INTEGER, lap_number INTEGER, date TEXT, pit_duration REAL, stop_duration REAL,
    PRIMARY KEY (session_key, driver_number, lap_number)
);
CREATE TABLE IF NOT EXISTS race_control (
    session_key INTEGER, date TEXT, lap_number INTEGER, category TEXT, flag TEXT, scope TEXT,
    sector INTEGER, driver_number INTEGER, message TEXT
);
CREATE TABLE IF NOT EXISTS positions (
    session_key INTEGER, driver_number INTEGER, date TEXT, position INTEGER
);
CREATE TABLE IF NOT EXISTS intervals (
    session_key INTEGER, driver_number INTEGER, date TEXT,
    gap_to_leader REAL, interval REAL, gap_text TEXT      -- gap_text keeps values like "+1 LAP"
);
CREATE TABLE IF NOT EXISTS weather (
    session_key INTEGER, date TEXT, air_temperature REAL, track_temperature REAL, humidity REAL,
    rainfall INTEGER, wind_speed REAL
);
-- Car position and telemetry thinned to a fixed rate; t = seconds since the session start.
CREATE TABLE IF NOT EXISTS car_samples (
    session_key INTEGER, driver_number INTEGER, t REAL, x REAL, y REAL,
    speed REAL, throttle REAL, brake REAL, gear INTEGER, rpm REAL,
    PRIMARY KEY (session_key, driver_number, t)
);
CREATE INDEX IF NOT EXISTS idx_positions ON positions (session_key, date);
CREATE INDEX IF NOT EXISTS idx_intervals ON intervals (session_key, date);
"""

SESSION_TABLES = ["session_drivers", "laps", "stints", "pits", "race_control", "positions", "intervals",
                  "weather", "car_samples"]


def connect(path=DEFAULT_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def upsert(conn, table, rows):
    """Insert rows (dicts with identical keys), replacing any with the same primary key."""
    rows = list(rows)
    if not rows:
        return 0
    cols = list(rows[0])
    sql = f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    conn.executemany(sql, [[r[c] for c in cols] for r in rows])
    return len(rows)


def rounds_in(conn, table, season):
    return {r for (r,) in conn.execute(f"SELECT DISTINCT round FROM {table} WHERE season = ?", (season,))}
