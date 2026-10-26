"""
Keeps the Race Centre store up to date on its own, following the race calendar.

Free data only, so "live" means "as soon as the data is free":
- OpenF1 publishes a whole session for free 30 minutes after it ends (live timing is a paid
  tier). Once a race should be over, the watcher tries every tick until that race is stored.
- Jolpica's official results and standings usually land a few hours after a race; they are
  checked every RESULTS_EVERY until that round is in.
- The rest of the time, the season (calendar, results, standings) is refreshed every SEASON_EVERY.

Run it next to the app, from the repo root:  python -m ingest.watch
One pass only (for cron or a scheduled task):  python -m ingest.watch --once
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

from . import jolpica, openf1
from .season import ingest_season
from .session import _utc, ingest_season_stints, ingest_session
from .store import DEFAULT_PATH, connect, upsert

EARLIEST_RACE_END = timedelta(hours=1, minutes=45)   # shortest plausible race, start to flag
FREE_AFTER = timedelta(minutes=30)                   # OpenF1: historical (free) 30 min after the end
RESULTS_EVERY = timedelta(minutes=15)
RESULTS_GIVE_UP = timedelta(hours=36)
SEASON_EVERY = timedelta(hours=12)


# ── what's due (pure: everything it needs is passed in) ──

def due_jobs(races, stored_rounds, result_rounds, last_run, now):
    """The jobs to run now, as (job, round) pairs.

    races: [{"round", "race_utc"}] of the season; stored_rounds: rounds whose race session is
    stored in full; result_rounds: rounds with official results; last_run: {job: datetime}."""
    jobs = []
    for r in races:
        start = _utc(r["race_utc"])
        rnd = r["round"]
        if now < start:
            continue
        if rnd not in stored_rounds and now >= start + EARLIEST_RACE_END + FREE_AFTER \
                and now - start < RESULTS_GIVE_UP:
            jobs.append(("session", rnd))
        last = last_run.get(f"results:{rnd}")
        if rnd not in result_rounds and now - start < RESULTS_GIVE_UP \
                and (last is None or now - last >= RESULTS_EVERY):
            jobs.append(("results", rnd))
    last = last_run.get("season")
    if last is None or now - last >= SEASON_EVERY:
        if not any(job == "results" for job, _ in jobs):     # a results check refreshes the season anyway
            jobs.append(("season", None))
    return jobs


# ── reading the store ──

def store_state(conn, season):
    races = [{"round": r, "race_utc": t} for r, t in
             conn.execute("SELECT round, race_utc FROM races WHERE season = ? ORDER BY round", (season,))]
    stored = {r for (r,) in conn.execute("""
        SELECT DISTINCT s.round FROM sessions s JOIN laps l USING (session_key)
        WHERE s.season = ? AND s.session_type = 'Race'""", (season,))}
    results = {r for (r,) in conn.execute("SELECT DISTINCT round FROM results WHERE season = ?", (season,))}
    last_run = {job: _utc(t) for job, t in conn.execute("SELECT job, last_run_utc FROM watch_state")}
    return races, stored, results, last_run


def mark(conn, job, now, note=""):
    upsert(conn, "watch_state", [{"job": job, "last_run_utc": now.isoformat(timespec="seconds"), "note": note}])
    conn.commit()


# ── one pass ──

def tick(conn, jc, f1, now=None, log=print):
    now = now or datetime.now(timezone.utc)
    season = now.year
    races, stored, results, last_run = store_state(conn, season)
    if not races:                                    # first run: nothing to plan from yet
        ingest_season(jc, conn, season, log=log)
        mark(conn, "season", now, "first run")
        races, stored, results, last_run = store_state(conn, season)

    done = []
    for job, rnd in due_jobs(races, stored, results, last_run, now):
        if job == "session":
            out = ingest_session(f1, conn, now=now, log=log)
            got = conn.execute("SELECT round FROM sessions WHERE session_key = ?",
                               (out["session_key"],)).fetchone() if out else None
            if got and got[0] == rnd:
                ingest_season_stints(f1, conn, season, now=now, log=log)
                done.append(f"stored race {rnd}")
            else:
                log(f"round {rnd}: race data not free yet, will try again")
        elif job == "results":
            ingest_season(jc, conn, season, log=log)
            mark(conn, f"results:{rnd}", now)
            mark(conn, "season", now)
            have = conn.execute("SELECT 1 FROM results WHERE season = ? AND round = ? LIMIT 1", (season, rnd)).fetchone()
            done.append(f"results {rnd}: {'in' if have else 'not yet'}")
        elif job == "season":
            ingest_season(jc, conn, season, log=log)
            mark(conn, "season", now)
            done.append("season refreshed")
    return done


def main():
    ap = argparse.ArgumentParser(prog="python -m ingest.watch", description="Keep the Race Centre store up to date.")
    ap.add_argument("--interval", type=int, default=60, help="seconds between passes (default 60)")
    ap.add_argument("--once", action="store_true", help="run one pass and exit")
    ap.add_argument("--db", default=DEFAULT_PATH)
    args = ap.parse_args()

    conn = connect(args.db)
    jc, f1 = jolpica.Client(), openf1.Client()
    try:
        while True:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            try:
                done = tick(conn, jc, f1)
                print(f"[{stamp}] {'; '.join(done) if done else 'nothing due'}", flush=True)
            except Exception as e:                      # a network blip must not stop the watcher
                print(f"[{stamp}] pass failed, will retry: {e}", flush=True)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("stopped")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
