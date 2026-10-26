import sqlite3

from conftest import FakeResponse, FakeSession, fixture
from ingest import jolpica as J
from ingest.season import ingest_season
from ingest.store import connect


def test_parse_race_keeps_session_times_in_utc():
    races = fixture("races.json")["MRData"]["RaceTable"]["Races"]
    melbourne, shanghai = J.parse_race(races[0]), J.parse_race(races[1])
    assert (melbourne["round"], melbourne["circuit_id"]) == (1, "albert_park")
    assert melbourne["race_utc"] == "2026-03-08T04:00:00Z"
    assert melbourne["sprint_utc"] is None and melbourne["fp3_utc"] is not None
    assert shanghai["sprint_utc"] is not None          # sprint weekend: no FP2/FP3
    assert shanghai["fp2_utc"] is None


def test_parse_results_handles_non_starters_and_accents():
    race = fixture("results_0.json")["MRData"]["RaceTable"]["Races"][0]
    rows = J.parse_results(race)
    winner, dns = rows[0], next(r for r in rows if r["driver_id"] == "hulkenberg")
    assert (winner["position"], winner["points"], winner["time_millis"]) == (1, 25.0, 4986801)
    assert dns["position_text"] == "W" and dns["time_text"] is None and dns["fastest_lap_rank"] is None
    assert J.parse_driver(race["Results"][-1]["Driver"])["family_name"] == "Hülkenberg"


def test_paged_follows_offsets_across_a_race_split_between_pages(client):
    races = list(client.paged("2026/results", "RaceTable", "Races"))
    rows = [row for race in races for row in J.parse_results(race)]
    assert client.session.calls == ["results/@0", "results/@30"]
    assert len(rows) == 60
    assert sum(r["round"] == 2 for r in rows) == 22    # 8 rows on page one, 14 on page two


def test_client_retries_after_rate_limit():
    waits = []
    session = FakeSession(queued=[FakeResponse(429, headers={"Retry-After": "1.5"})])
    c = J.Client(session=session, min_interval=0, sleep=waits.append)
    data = c.get("2026/races")
    assert data["total"] == "23"
    assert waits == [1.5] and c.requests == 2


def test_ingest_season_fills_store_then_only_refreshes_latest_round(client, tmp_path):
    conn = connect(tmp_path / "store.sqlite")
    out = ingest_season(client, conn, 2026, log=lambda *_: None)
    assert out == {"races": 23, "results": 60, "standings_rounds": [1, 2, 3]}
    count = lambda t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    assert count("races") == 23 and count("results") == 60
    assert count("drivers") == 22 and count("constructors") == 11
    assert {r for (r,) in conn.execute("SELECT DISTINCT round FROM driver_standings")} == {1, 2, 3}

    client.session.calls.clear()
    out = ingest_season(client, conn, 2026, log=lambda *_: None)
    assert out["standings_rounds"] == [3]
    assert [c for c in client.session.calls if "standings" in c] == ["3/driverstandings/@0",
                                                                    "3/constructorstandings/@0"]
    assert count("results") == 60                       # upserts, no duplicates
    conn.close()


def test_schema_can_be_applied_twice(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    conn.close()
    conn = connect(tmp_path / "s.sqlite")               # schema is idempotent
    assert conn.execute("SELECT COUNT(*) FROM races").fetchone()[0] == 0
    conn.close()
