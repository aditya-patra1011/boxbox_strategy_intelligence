"""
Read-only access to the Race Centre store that `python -m ingest` fills.
Pages call these; nothing here talks to an external API.
"""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

BASE = Path(os.environ.get("BOXBOX_BASE", Path(__file__).resolve().parent.parent))
STORE = Path(os.environ.get("BOXBOX_STORE", BASE / "data" / "race_centre" / "boxbox.sqlite"))


def available():
    return STORE.exists()


def query(sql, params=()):
    """Run a SELECT against the store; an empty frame if the store hasn't been built yet."""
    if not available():
        return pd.DataFrame()
    with closing(sqlite3.connect(f"file:{STORE.as_posix()}?mode=ro", uri=True)) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def seasons():
    df = query("SELECT DISTINCT season FROM races ORDER BY season DESC")
    return df["season"].tolist() if not df.empty else []


def current_season():
    s = seasons()
    return s[0] if s else None


def races(season):
    return query("SELECT * FROM races WHERE season = ? ORDER BY round", (season,))


def results(season):
    return query("""
        SELECT r.*, d.code, d.given_name, d.family_name, c.name AS team
        FROM results r
        JOIN drivers d USING (driver_id)
        JOIN constructors c USING (constructor_id)
        WHERE r.season = ? ORDER BY r.round, r.position""", (season,))


def completed_rounds(season):
    df = query("SELECT DISTINCT round FROM results WHERE season = ? ORDER BY round", (season,))
    return df["round"].tolist() if not df.empty else []


def driver_standings(season):
    """Standings after every completed round (one row per driver per round)."""
    return query("""
        SELECT s.*, d.code, d.given_name, d.family_name, d.number, c.name AS team
        FROM driver_standings s
        JOIN drivers d USING (driver_id)
        LEFT JOIN constructors c USING (constructor_id)
        WHERE s.season = ? ORDER BY s.round, s.position""", (season,))


def constructor_standings(season):
    return query("""
        SELECT s.*, c.name AS team
        FROM constructor_standings s
        JOIN constructors c USING (constructor_id)
        WHERE s.season = ? ORDER BY s.round, s.position""", (season,))


def last_updated():
    df = query("SELECT run_utc FROM ingest_log ORDER BY run_utc DESC LIMIT 1")
    return df["run_utc"].iloc[0] if not df.empty else None


# ── standings shaping (pure functions on the frames above) ──

# 2026 points: race win 25, sprint win 8 (no fastest-lap point since 2025).
# A team can take the top two places, so its maximum per event is P1 + P2.
MAX_POINTS = {"drivers": {"race": 25, "sprint": 8}, "constructors": {"race": 25 + 18, "sprint": 8 + 7}}


def latest_table(standings, key):
    """Standings after the latest round, with gap to the leader and places gained since the round before."""
    if standings.empty:
        return standings
    last = standings["round"].max()
    now = standings[standings["round"] == last].copy()
    before = standings[standings["round"] == last - 1].set_index(key)["position"]
    now["change"] = (now[key].map(before) - now["position"]).fillna(0).astype(int)   # + = places gained
    now["gap"] = now["points"].max() - now["points"]
    return now.sort_values(["position", "points"], ascending=[True, False], na_position="last")


def points_left(races_df, completed, kind):
    """Most points one driver (or team) can still score in the races after the last completed round."""
    future = races_df[races_df["round"] > max(completed, default=0)]
    sprints = int(future["sprint_utc"].notna().sum())
    m = MAX_POINTS[kind]
    return len(future) * m["race"] + sprints * m["sprint"]


def contenders(table, left):
    """Everyone who can still mathematically reach the leader's total."""
    if table.empty:
        return table
    return table[table["points"] + left >= table["points"].max()]
