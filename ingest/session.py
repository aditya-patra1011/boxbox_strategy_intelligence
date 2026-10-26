"""
Stores one OpenF1 session for Race Live and Race Analysis to replay: laps, tyre stints,
pit stops, race control (flags, Safety Car, VSC), positions, intervals, weather, and every
car's position and telemetry thinned to SAMPLE_HZ samples a second.

By default it takes the latest race that finished at least DELAY ago (OpenF1's free
historical data appears after the session). Re-running replaces that session's rows.

Run from the repo root:  python -m ingest.session
                         python -m ingest.session --session-key 11396
"""

import argparse
import math
from datetime import date, datetime, timedelta, timezone

from . import openf1
from .store import DEFAULT_PATH, SESSION_TABLES, connect, upsert

SAMPLE_HZ = 2               # car samples kept per second (OpenF1 sends ~3.7)
DELAY = timedelta(minutes=30)
WINDOW = (timedelta(minutes=-10), timedelta(minutes=30))   # car samples kept around the session
KEEP_SAMPLES_FOR = 3        # car samples are big: keep them only for the newest sessions


def _utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _num(value):
    """OpenF1 gaps are numbers, or text like "+1 LAP" for lapped cars."""
    return value if isinstance(value, (int, float)) else None


# ── pure helpers ──

def latest_finished(sessions, now):
    done = [s for s in sessions if not s.get("is_cancelled") and _utc(s["date_end"]) + DELAY <= now]
    return max(done, key=lambda s: s["date_start"]) if done else None


def race_for(session, races):
    """The Jolpica (season, round, circuit_id) whose race falls in the session's race weekend."""
    start = _utc(session["date_start"]).date()
    for r in races:
        race_day = date.fromisoformat(r["race_utc"][:10])
        if timedelta(0) <= race_day - start <= timedelta(days=3):
            return r["season"], r["round"], r["circuit_id"]
    return None, None, None


def thin(location, car_data, t0, hz=SAMPLE_HZ, window=None):
    """Merge one driver's location and car data onto a fixed grid of 1/hz seconds.
    The first sample in each slot wins; slots with neither, or outside `window`
    (seconds from t0), are left out. OpenF1 can return a day of data before the session."""
    slots = {}
    for rows, fields in ((location, ("x", "y")), (car_data, ("speed", "throttle", "brake", "n_gear", "rpm"))):
        for r in rows:
            t = math.floor((_utc(r["date"]) - t0).total_seconds() * hz) / hz
            if window and not window[0] <= t <= window[1]:
                continue
            slot = slots.setdefault(t, {})
            for f in fields:
                if f not in slot and r.get(f) is not None:
                    slot[f] = r[f]
    return [{"t": t, "x": s.get("x"), "y": s.get("y"), "speed": s.get("speed"), "throttle": s.get("throttle"),
             "brake": s.get("brake"), "gear": s.get("n_gear"), "rpm": s.get("rpm")}
            for t, s in sorted(slots.items())]


# ── ingest ──

def ingest_session(f1, conn, session_key=None, now=None, log=print):
    now = now or datetime.now(timezone.utc)
    if session_key:
        session = f1.get("sessions", session_key=session_key)[0]
    else:
        session = latest_finished(f1.get("sessions", year=now.year, session_name="Race"), now)
        if session is None:
            log("no finished race this season yet")
            return None
    key, t0 = session["session_key"], _utc(session["date_start"])
    races = [dict(zip(("season", "round", "circuit_id", "race_utc"), r)) for r in
             conn.execute("SELECT season, round, circuit_id, race_utc FROM races WHERE season = ?", (session["year"],))]
    season, rnd, circuit_id = race_for(session, races)
    log(f"session {key}: {session['year']} {session['circuit_short_name']} {session['session_name']}"
        f" (round {rnd}, {circuit_id})")

    def tagged(rows, **extra):
        return [{"session_key": key, **extra, **r} for r in rows]

    drivers = f1.get("drivers", session_key=key)
    laps = f1.get("laps", session_key=key)
    data = {
        "session_drivers": tagged({"driver_number": d["driver_number"], "code": d["name_acronym"],
                                   "first_name": d["first_name"], "last_name": d["last_name"],
                                   "team_name": d["team_name"], "team_colour": d.get("team_colour")} for d in drivers),
        "laps": tagged({"driver_number": l["driver_number"], "lap_number": l["lap_number"], "date_start": l.get("date_start"),
                        "lap_duration": l.get("lap_duration"), "s1": l.get("duration_sector_1"),
                        "s2": l.get("duration_sector_2"), "s3": l.get("duration_sector_3"), "i1_speed": l.get("i1_speed"),
                        "i2_speed": l.get("i2_speed"), "st_speed": l.get("st_speed"),
                        "is_pit_out_lap": int(bool(l.get("is_pit_out_lap")))} for l in laps),
        "stints": tagged({k: s.get(k) for k in ("driver_number", "stint_number", "compound", "lap_start", "lap_end",
                                                 "tyre_age_at_start")} for s in f1.get("stints", session_key=key)),
        "pits": tagged({k: p.get(k) for k in ("driver_number", "lap_number", "date", "pit_duration", "stop_duration")}
                       for p in f1.get("pit", session_key=key)),
        "race_control": tagged({k: r.get(k) for k in ("date", "lap_number", "category", "flag", "scope", "sector",
                                                       "driver_number", "message")}
                               for r in f1.get("race_control", session_key=key)),
        "positions": tagged({k: p[k] for k in ("driver_number", "date", "position")}
                            for p in f1.get("position", session_key=key)),
        "intervals": tagged({"driver_number": i["driver_number"], "date": i["date"], "gap_to_leader": _num(i.get("gap_to_leader")),
                             "interval": _num(i.get("interval")),
                             "gap_text": None if _num(i.get("gap_to_leader")) is not None else i.get("gap_to_leader")}
                            for i in f1.get("intervals", session_key=key)),
        "weather": tagged({k: w.get(k) for k in ("date", "air_temperature", "track_temperature", "humidity", "rainfall",
                                                  "wind_speed")} for w in f1.get("weather", session_key=key)),
        "car_samples": [],
    }
    length = (_utc(session["date_end"]) - t0).total_seconds()
    window = (WINDOW[0].total_seconds(), length + WINDOW[1].total_seconds())
    for d in drivers:
        n = d["driver_number"]
        rows = thin(f1.get("location", session_key=key, driver_number=n),
                    f1.get("car_data", session_key=key, driver_number=n), t0, window=window)
        data["car_samples"] += tagged(rows, driver_number=n)
        log(f"  car {n:>2} {d['name_acronym']}: {len(rows)} samples")

    with conn:                                   # one transaction: a session is all there or not at all
        for table in SESSION_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE session_key = ?", (key,))
            upsert(conn, table, data[table])
        upsert(conn, "sessions", [{
            "session_key": key, "meeting_key": session["meeting_key"], "season": season, "round": rnd,
            "circuit_id": circuit_id, "session_type": session["session_type"], "session_name": session["session_name"],
            "date_start": session["date_start"], "date_end": session["date_end"],
            "total_laps": max((l["lap_number"] for l in laps), default=None),
            "ingested_utc": now.isoformat(timespec="seconds")}])
        keep = [k for (k,) in conn.execute(
            "SELECT session_key FROM sessions ORDER BY date_start DESC LIMIT ?", (KEEP_SAMPLES_FOR,))]
        conn.execute(f"DELETE FROM car_samples WHERE session_key NOT IN ({','.join('?' * len(keep))})", keep)

    counts = {t: len(data[t]) for t in SESSION_TABLES}
    log(f"stored: {counts} ({f1.requests} OpenF1 requests)")
    return {"session_key": key, **counts}


def ingest_season_stints(f1, conn, year, now=None, log=print):
    """Light pass over every finished race of a season: the session, its drivers and their tyre
    stints only (3 requests a race), so result tables can show each driver's final tyre.
    Races already stored in full are left alone."""
    now = now or datetime.now(timezone.utc)
    races = [dict(zip(("season", "round", "circuit_id", "race_utc"), r)) for r in
             conn.execute("SELECT season, round, circuit_id, race_utc FROM races WHERE season = ?", (year,))]
    have = {k for (k,) in conn.execute("SELECT session_key FROM sessions")}
    done = [s for s in f1.get("sessions", year=year, session_name="Race")
            if not s.get("is_cancelled") and _utc(s["date_end"]) + DELAY <= now and s["session_key"] not in have]
    for s in done:
        key = s["session_key"]
        season, rnd, circuit_id = race_for(s, races)
        stints = f1.get("stints", session_key=key)
        drivers = f1.get("drivers", session_key=key)
        with conn:
            upsert(conn, "session_drivers", [{"session_key": key, "driver_number": d["driver_number"],
                                              "code": d["name_acronym"], "first_name": d["first_name"],
                                              "last_name": d["last_name"], "team_name": d["team_name"],
                                              "team_colour": d.get("team_colour")} for d in drivers])
            conn.execute("DELETE FROM stints WHERE session_key = ?", (key,))
            upsert(conn, "stints", [{"session_key": key, **{k: x.get(k) for k in (
                "driver_number", "stint_number", "compound", "lap_start", "lap_end", "tyre_age_at_start")}} for x in stints])
            upsert(conn, "sessions", [{
                "session_key": key, "meeting_key": s["meeting_key"], "season": season, "round": rnd,
                "circuit_id": circuit_id, "session_type": s["session_type"], "session_name": s["session_name"],
                "date_start": s["date_start"], "date_end": s["date_end"],
                "total_laps": max((x.get("lap_end") or 0 for x in stints), default=None),
                "ingested_utc": now.isoformat(timespec="seconds")}])
        log(f"  round {rnd} {s['circuit_short_name']}: {len(stints)} stints")
    log(f"stints: {len(done)} races added ({f1.requests} OpenF1 requests)")
    return len(done)


def main():
    ap = argparse.ArgumentParser(prog="python -m ingest.session", description="Store one session for replay.")
    ap.add_argument("--session-key", type=int, help="OpenF1 session key (default: latest finished race)")
    ap.add_argument("--season-stints", type=int, metavar="YEAR",
                    help="instead: store just the tyre stints of every finished race that season")
    ap.add_argument("--db", default=DEFAULT_PATH)
    args = ap.parse_args()
    conn = connect(args.db)
    try:
        if args.season_stints:
            ingest_season_stints(openf1.Client(), conn, args.season_stints)
        else:
            ingest_session(openf1.Client(), conn, args.session_key)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
