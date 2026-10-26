"""
Read-only access to the Race Centre store that `python -m ingest` fills.
Pages call these; nothing here talks to an external API.
"""

import json
import math
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd

BASE = Path(os.environ.get("BOXBOX_BASE", Path(__file__).resolve().parent.parent))
STORE = Path(os.environ.get("BOXBOX_STORE", BASE / "data" / "race_centre" / "boxbox.sqlite"))
CONTENT = BASE / "content"          # committed content built by: python -m ingest.circuits


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


# ── circuits (content/, committed to the repo) ──

@lru_cache(maxsize=1)
def circuits():
    """Facts per circuit for the season: first GP, races held, racing-line length, laps."""
    path = CONTENT / "circuits.json"
    if not path.exists():
        return pd.DataFrame()
    return pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))["circuits"])


@lru_cache(maxsize=32)
def outline(circuit_id):
    """Track outline in OpenF1 coordinates plus the rotation to display it with, or None."""
    path = CONTENT / "circuits" / f"{circuit_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def rotate(x, y, deg, centre):
    """Turn points about `centre` for display. Same maths as the builder, so car positions
    from OpenF1 can be turned with the outline they belong to."""
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    mx, my = centre
    return ([(a - mx) * c - (b - my) * s for a, b in zip(x, y)],
            [(a - mx) * s + (b - my) * c for a, b in zip(x, y)])


def outline_xy(circuit_id):
    """Display-ready outline: rotated, closed, and centred on (0, 0)."""
    o = outline(circuit_id)
    if not o:
        return None
    centre = (sum(o["x"]) / len(o["x"]), sum(o["y"]) / len(o["y"]))
    x, y = rotate(o["x"] + o["x"][:1], o["y"] + o["y"][:1], o["rotation_deg"], centre)
    return x, y


# ── race weekends ──

# Strategy Lab has models for these circuits (2024 data, Phases 1-8). New venues (Madring,
# Sepang) and Interlagos (2024 was fully wet) have none.
STRATEGY_CIRCUIT = {
    "albert_park": "Australia", "shanghai": "China", "suzuka": "Japan", "miami": "Miami",
    "villeneuve": "Canada", "monaco": "Monaco", "catalunya": "Spain", "red_bull_ring": "Austria",
    "silverstone": "Great Britain", "spa": "Belgium", "hungaroring": "Hungary", "zandvoort": "Netherlands",
    "monza": "Italy", "baku": "Azerbaijan", "marina_bay": "Singapore", "americas": "United States",
    "rodriguez": "Mexico", "vegas": "Las Vegas", "losail": "Qatar", "yas_marina": "Abu Dhabi",
}

SESSIONS = [("fp1_utc", "Practice 1"), ("fp2_utc", "Practice 2"), ("fp3_utc", "Practice 3"),
            ("sprint_qualifying_utc", "Sprint Qualifying"), ("sprint_utc", "Sprint"),
            ("qualifying_utc", "Qualifying"), ("race_utc", "Race")]
SESSION_LENGTH = {"Race": timedelta(hours=2, minutes=30)}      # everything else: 1h30
RACE_DONE_AFTER = timedelta(hours=3)


def now():
    """Current UTC time. Setting BOXBOX_NOW (ISO time) pins it, to demo or screenshot a race weekend."""
    fixed = os.environ.get("BOXBOX_NOW")
    return utc(fixed) if fixed else datetime.now(timezone.utc)


def utc(text):
    if not isinstance(text, str) or not text:
        return None
    t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def sessions(race):
    """[(name, start, end)] for one weekend, in order."""
    out = [(name, utc(race.get(col))) for col, name in SESSIONS if utc(race.get(col))]
    return sorted(((n, t, t + SESSION_LENGTH.get(n, timedelta(hours=1, minutes=30))) for n, t in out),
                  key=lambda s: s[1])


def weekend_status(race, at, has_result=False):
    """"completed", "live" (from first practice until the race is over) or "upcoming"."""
    ss = sessions(race)
    if has_result or at >= utc(race["race_utc"]) + RACE_DONE_AFTER:
        return "completed"
    return "live" if ss and at >= ss[0][1] else "upcoming"


def session_now(race, at):
    """(name, start, running) for the session on track now, else the next one; None once all are done."""
    for name, start, end in sessions(race):
        if start <= at <= end:
            return name, start, True
        if at < start:
            return name, start, False
    return None


def calendar(season, at=None):
    """Every round with its weekend status and, for finished races, the winner."""
    at = at or now()
    df = races(season)
    if df.empty:
        return df
    res = results(season)
    winners = res[res["position"] == 1].set_index("round") if not res.empty else pd.DataFrame()
    rows = []
    for _, r in df.iterrows():
        race = r.to_dict()
        w = winners.loc[race["round"]] if race["round"] in winners.index else None
        race["status"] = weekend_status(race, at, has_result=w is not None)
        race["winner"] = None if w is None else f"{w['given_name']} {w['family_name']}"
        race["winner_code"] = None if w is None else w["code"]
        race["winner_team"] = None if w is None else w["team"]
        race["winner_team_id"] = None if w is None else w["constructor_id"]
        rows.append(race)
    return pd.DataFrame(rows)


def podium(season, rnd):
    res = results(season)
    return res[(res["round"] == rnd) & (res["position"] <= 3)].sort_values("position")


# ── teams (content/teams.json is curated; content/team_stats.json is computed by python -m ingest.teams) ──

@lru_cache(maxsize=1)
def teams():
    path = CONTENT / "teams.json"
    return json.loads(path.read_text(encoding="utf-8"))["teams"] if path.exists() else []


@lru_cache(maxsize=1)
def team_stats():
    path = CONTENT / "team_stats.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"teams": {}}


def team_lineup(season):
    """Each team's drivers at the latest completed round: racing number, nationality, date of birth,
    and where they stand in the championship after that round."""
    return query("""
        SELECT r.constructor_id, c.name AS team, r.driver_id, r.number, d.code, d.given_name, d.family_name,
               d.nationality, d.date_of_birth, s.position AS champ_position, s.points AS champ_points,
               s.wins AS season_wins
        FROM results r
        JOIN drivers d USING (driver_id)
        JOIN constructors c USING (constructor_id)
        LEFT JOIN driver_standings s ON s.season = r.season AND s.round = r.round AND s.driver_id = r.driver_id
        WHERE r.season = ? AND r.round = (SELECT MAX(round) FROM results WHERE season = ?)
        ORDER BY r.constructor_id, s.position""", (season, season))


def initials(given, family):
    """"Andrea Kimi", "Antonelli" -> "AA": first given name and family name."""
    return (given.split()[0][:1] + family.replace("-", " ").split()[-1][:1]).upper()


def age(date_of_birth, at=None):
    born, at = datetime.fromisoformat(date_of_birth).date(), (at or now()).date()
    return at.year - born.year - ((at.month, at.day) < (born.month, born.day))


# ── replay sessions (python -m ingest.session) ──

SESSION_TABLES = {"session_drivers", "laps", "stints", "pits", "race_control", "positions", "intervals", "weather"}


def latest_session(session_type="Race"):
    """The newest stored session of a type, as a dict, or None."""
    df = query("SELECT * FROM sessions WHERE session_type = ? ORDER BY date_start DESC LIMIT 1", (session_type,))
    return df.iloc[0].to_dict() if not df.empty else None


def session_table(table, session_key):
    """Every row one session has in a table: laps, stints, pits, race_control, positions, ..."""
    if table not in SESSION_TABLES:
        raise ValueError(f"not a session table: {table}")
    return query(f"SELECT * FROM {table} WHERE session_key = ?", (session_key,))


def car_samples(session_key, t_from=None, t_to=None, drivers=None):
    """Thinned car position and telemetry; t is seconds since the session start."""
    sql, params = "SELECT * FROM car_samples WHERE session_key = ?", [session_key]
    if t_from is not None:
        sql, params = sql + " AND t >= ?", params + [t_from]
    if t_to is not None:
        sql, params = sql + " AND t <= ?", params + [t_to]
    if drivers:
        sql, params = sql + f" AND driver_number IN ({','.join('?' * len(drivers))})", params + list(drivers)
    return query(sql + " ORDER BY driver_number, t", params)


def positions_by_lap(laps, positions):
    """Each driver's race position at the end of every lap they completed (for the lap chart).
    A lap ends when the next one starts; the position is the latest change at or before then."""
    if laps.empty or positions.empty:
        return pd.DataFrame(columns=["driver_number", "lap_number", "position"])
    laps = laps.sort_values(["driver_number", "lap_number"]).copy()
    start = pd.to_datetime(laps["date_start"], utc=True, format="ISO8601")
    laps["end"] = start.groupby(laps["driver_number"]).shift(-1)
    laps["end"] = laps["end"].fillna(start + pd.to_timedelta(laps["lap_duration"], unit="s"))
    laps = laps.dropna(subset=["end"]).sort_values("end")
    pos = positions.assign(date=pd.to_datetime(positions["date"], utc=True, format="ISO8601")).sort_values("date")
    out = pd.merge_asof(laps, pos[["driver_number", "date", "position"]], left_on="end", right_on="date",
                        by="driver_number", direction="backward")
    return out.dropna(subset=["position"]).astype({"position": int})[["driver_number", "lap_number", "position"]] \
        .sort_values(["lap_number", "position"]).reset_index(drop=True)
