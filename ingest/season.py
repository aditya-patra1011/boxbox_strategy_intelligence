"""
Brings one season up to date: calendar, race results and the standings after every round.
"""

from datetime import datetime, timezone

from . import jolpica as J
from .store import rounds_in, upsert


def ingest_season(client, conn, season, full=False, log=print):
    races = [J.parse_race(r) for r in client.paged(f"{season}/races", "RaceTable", "Races")]
    upsert(conn, "races", races)
    log(f"calendar: {len(races)} rounds")

    # Results pages are cut by result rows, so one race can span two pages. Flattening
    # every page's race blocks into rows makes that split harmless.
    results, drivers, constructors = [], {}, {}
    for race in client.paged(f"{season}/results", "RaceTable", "Races"):
        results += J.parse_results(race)
        for x in race["Results"]:
            drivers[x["Driver"]["driverId"]] = J.parse_driver(x["Driver"])
            constructors[x["Constructor"]["constructorId"]] = J.parse_constructor(x["Constructor"])
    upsert(conn, "results", results)
    done = sorted({r["round"] for r in results})
    log(f"results: {len(results)} rows over {len(done)} completed rounds")

    # Standings after every completed round feed the points-over-time charts. Past rounds are
    # fetched once; the latest round is always refreshed in case of late penalties.
    have = rounds_in(conn, "driver_standings", season) & rounds_in(conn, "constructor_standings", season)
    todo = [r for r in done if full or r not in have or r == done[-1]]
    for rnd in todo:
        for lst in client.get(f"{season}/{rnd}/driverstandings")["StandingsTable"]["StandingsLists"]:
            upsert(conn, "driver_standings", J.parse_driver_standings(lst))
            for s in lst["DriverStandings"]:
                drivers[s["Driver"]["driverId"]] = J.parse_driver(s["Driver"])
        for lst in client.get(f"{season}/{rnd}/constructorstandings")["StandingsTable"]["StandingsLists"]:
            upsert(conn, "constructor_standings", J.parse_constructor_standings(lst))
            for s in lst["ConstructorStandings"]:
                constructors[s["Constructor"]["constructorId"]] = J.parse_constructor(s["Constructor"])
    log(f"standings: refreshed {len(todo)} rounds")

    upsert(conn, "drivers", drivers.values())
    upsert(conn, "constructors", constructors.values())
    upsert(conn, "ingest_log", [{"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "season": season, "races": len(races), "results": len(results),
                                 "standings_rounds": ",".join(map(str, todo)), "requests": client.requests}])
    conn.commit()
    return {"races": len(races), "results": len(results), "standings_rounds": todo}
