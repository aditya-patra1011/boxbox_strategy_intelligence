"""
Computes each team's championships and race wins from Jolpica results, following the
lineage in content/teams.json: a predecessor's titles and wins count for the years it
raced under that name (Tyrrell -> BAR -> Honda -> Brawn -> Mercedes, and so on).

  content/team_stats.json    computed; never edited by hand

Run from the repo root:  python -m ingest.teams
"""

import argparse
import json
from datetime import date, datetime, timezone

from . import jolpica
from .store import BASE

CONTENT = BASE / "content"
FIRST_SEASON = 1950
FIRST_CONSTRUCTORS_TITLE = 1958          # the Constructors' Championship started in 1958


def load_teams(path=CONTENT / "teams.json"):
    return json.loads(path.read_text(encoding="utf-8"))["teams"]


def owner(teams, constructor_id, season):
    """(team id, name raced under) for the current team whose lineage covers this entry, else (None, None)."""
    for t in teams:
        for step in t["lineage"]:
            if constructor_id in step["constructor_ids"] and step["from"] <= season <= (step["to"] or 9999):
                return t["id"], step["name"]
    return None, None


def champions(jc, through, log=print):
    """Drivers' and Constructors' champions for every completed season up to `through`."""
    drivers, constructors = [], []
    for year in range(FIRST_SEASON, through + 1):
        for lst in jc.get(f"{year}/driverstandings/1")["StandingsTable"]["StandingsLists"]:
            s = lst["DriverStandings"][0]
            drivers.append({"season": year, "driver_id": s["Driver"]["driverId"],
                            "driver": f"{s['Driver']['givenName']} {s['Driver']['familyName']}",
                            "constructor_ids": [c["constructorId"] for c in s.get("Constructors", [])]})
        if year >= FIRST_CONSTRUCTORS_TITLE:
            for lst in jc.get(f"{year}/constructorstandings/1")["StandingsTable"]["StandingsLists"]:
                s = lst["ConstructorStandings"][0]
                constructors.append({"season": year, "constructor_id": s["Constructor"]["constructorId"],
                                     "constructor": s["Constructor"]["name"]})
        if year % 10 == 0:
            log(f"champions: up to {year}")
    return drivers, constructors


def race_wins(jc, constructor_id):
    return [{"season": int(r["season"]), "round": int(r["round"]), "race": r["raceName"],
             "driver": f"{r['Results'][0]['Driver']['givenName']} {r['Results'][0]['Driver']['familyName']}",
             "constructor_id": constructor_id}
            for r in jc.paged(f"constructors/{constructor_id}/results/1", "RaceTable", "Races")]


def summarise(teams, drivers, constructors, wins, through):
    """Pure step: attribute titles and wins to today's teams through their lineage."""
    out = {t["id"]: {"constructors_titles": [], "drivers_titles": [], "wins": 0, "wins_by_name": {},
                     "first_win": None, "latest_win": None} for t in teams}
    for c in constructors:
        team, name = owner(teams, c["constructor_id"], c["season"])
        if team:
            out[team]["constructors_titles"].append({"season": c["season"], "as": name})
    for d in drivers:
        # A champion who changed teams mid-season is credited to the last team they drove for.
        for cid in reversed(d["constructor_ids"]):
            team, name = owner(teams, cid, d["season"])
            if team:
                out[team]["drivers_titles"].append({"season": d["season"], "driver": d["driver"], "as": name})
                break
    for w in sorted(wins, key=lambda w: (w["season"], w["round"])):
        team, name = owner(teams, w["constructor_id"], w["season"])
        if not team:
            continue
        s = out[team]
        s["wins"] += 1
        s["wins_by_name"][name] = s["wins_by_name"].get(name, 0) + 1
        entry = {"season": w["season"], "race": w["race"], "driver": w["driver"], "as": name}
        s["first_win"] = s["first_win"] or entry
        s["latest_win"] = entry
    return out


def build(through=None, jc=None, out=CONTENT, log=print):
    jc = jc or jolpica.Client()
    through = through or date.today().year - 1
    teams = load_teams(out / "teams.json")
    drivers, constructors = champions(jc, through, log)
    ids = sorted({cid for t in teams for step in t["lineage"] for cid in step["constructor_ids"]})
    wins = [w for cid in ids for w in race_wins(jc, cid)]
    stats = summarise(teams, drivers, constructors, wins, through)
    (out / "team_stats.json").write_text(json.dumps({
        "titles_through_season": through,
        "wins_include_current_season": True,
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Jolpica F1 API: season champions and race winners, attributed through content/teams.json lineage.",
        "teams": stats}, indent=1, ensure_ascii=False), encoding="utf-8")
    for t in teams:
        s = stats[t["id"]]
        log(f"{t['name']:<13} constructors {len(s['constructors_titles']):>2}  drivers {len(s['drivers_titles']):>2}  "
            f"wins {s['wins']:>3}  {s['wins_by_name']}")
    log(f"done: {jc.requests} Jolpica requests")
    return stats


def main():
    ap = argparse.ArgumentParser(prog="python -m ingest.teams", description="Compute team titles and wins.")
    ap.add_argument("--through", type=int, help="last completed season to count titles for (default: last year)")
    build(ap.parse_args().through)


if __name__ == "__main__":
    main()
