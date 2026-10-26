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
"""


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
