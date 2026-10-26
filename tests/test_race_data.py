import pytest

import race_data
from ingest.season import ingest_season
from ingest.store import connect


@pytest.fixture
def store(client, tmp_path, monkeypatch):
    path = tmp_path / "store.sqlite"
    conn = connect(path)
    ingest_season(client, conn, 2026, log=lambda *_: None)
    conn.close()
    monkeypatch.setattr(race_data, "STORE", path)
    return path


def test_missing_store_gives_empty_frames(tmp_path, monkeypatch):
    monkeypatch.setattr(race_data, "STORE", tmp_path / "nope.sqlite")
    assert not race_data.available()
    assert race_data.races(2026).empty and race_data.seasons() == []
    assert race_data.last_updated() is None


def test_reads_calendar_results_and_standings(store):
    assert race_data.current_season() == 2026
    assert len(race_data.races(2026)) == 23
    assert race_data.completed_rounds(2026) == [1, 2, 3]

    res = race_data.results(2026)
    winner = res[(res["round"] == 1) & (res["position"] == 1)].iloc[0]
    assert (winner["code"], winner["team"]) == ("RUS", "Mercedes")

    ds = race_data.driver_standings(2026)
    assert set(ds["round"]) == {1, 2, 3} and ds.groupby("round").size().eq(22).all()
    cs = race_data.constructor_standings(2026)
    assert cs.groupby("round").size().eq(11).all()
    assert race_data.last_updated() is not None


def test_store_is_opened_read_only(store):
    with pytest.raises(Exception):
        race_data.query("DELETE FROM races")


# ── standings shaping ──

import pandas as pd


def standings(rows):
    return pd.DataFrame(rows, columns=["round", "driver_id", "position", "points"])


def test_latest_table_gap_and_places_gained():
    df = standings([(1, "a", 1, 25), (1, "b", 2, 18), (1, "c", 3, 15),
                    (2, "a", 1, 43), (2, "c", 2, 40), (2, "b", 3, 30)])
    t = race_data.latest_table(df, "driver_id").set_index("driver_id")
    assert t.loc["c", "change"] == 1 and t.loc["b", "change"] == -1 and t.loc["a", "change"] == 0
    assert t.loc["a", "gap"] == 0 and t.loc["b", "gap"] == 13


def test_latest_table_new_driver_and_unranked_driver():
    df = standings([(1, "a", 1, 25), (1, "x", None, 0),
                    (2, "a", 1, 50), (2, "x", 3, 0), (2, "sub", 2, 6)])   # "sub" joins in round 2
    t = race_data.latest_table(df, "driver_id")
    assert list(t["driver_id"]) == ["a", "sub", "x"]
    assert t.set_index("driver_id")["change"].tolist() == [0, 0, 0]


def test_points_left_counts_races_and_sprints_after_last_round():
    races = pd.DataFrame({"round": [1, 2, 3, 4], "sprint_utc": [None, "2026-x", None, "2026-y"]})
    assert race_data.points_left(races, [1, 2], "drivers") == 2 * 25 + 1 * 8
    assert race_data.points_left(races, [1, 2], "constructors") == 2 * 43 + 1 * 15
    assert race_data.points_left(races, [1, 2, 3, 4], "drivers") == 0


def test_contenders_includes_exact_tie_with_leader():
    table = pd.DataFrame({"driver_id": ["a", "b", "c"], "points": [100, 75, 74]})
    assert race_data.contenders(table, 25)["driver_id"].tolist() == ["a", "b"]
    assert race_data.contenders(table, 0)["driver_id"].tolist() == ["a"]


# ── circuit content ──

import json


def test_circuit_content_reads_and_rotates(tmp_path, monkeypatch):
    (tmp_path / "circuits").mkdir()
    (tmp_path / "circuits.json").write_text(json.dumps({"season": 2026, "circuits": [
        {"round": 14, "circuit_id": "madring", "first_gp": 2026, "outline": "circuits/madring.json"}]}))
    (tmp_path / "circuits" / "madring.json").write_text(json.dumps(
        {"circuit_id": "madring", "rotation_deg": 90, "x": [0, 20, 20, 0], "y": [0, 0, 10, 10]}))
    monkeypatch.setattr(race_data, "CONTENT", tmp_path)
    race_data.circuits.cache_clear(), race_data.outline.cache_clear()

    assert race_data.circuits()["circuit_id"].tolist() == ["madring"]
    x, y = race_data.outline_xy("madring")
    assert len(x) == 5 and (x[0], y[0]) == pytest.approx((x[-1], y[-1]))   # closed loop
    assert max(y) - min(y) == pytest.approx(20) and max(x) - min(x) == pytest.approx(10)   # turned 90°
    assert race_data.outline_xy("nowhere") is None
    race_data.circuits.cache_clear(), race_data.outline.cache_clear()


# ── race weekends ──

MEXICO = {"round": 19, "fp1_utc": "2026-10-30T18:30:00Z", "fp2_utc": "2026-10-30T22:00:00Z",
          "fp3_utc": "2026-10-31T17:30:00Z", "sprint_qualifying_utc": None, "sprint_utc": None,
          "qualifying_utc": "2026-10-31T21:00:00Z", "race_utc": "2026-11-01T20:00:00Z"}


@pytest.mark.parametrize("at, status, session", [
    ("2026-10-30T18:00:00Z", "upcoming", ("Practice 1", False)),
    ("2026-10-30T19:00:00Z", "live", ("Practice 1", True)),      # FP1 running
    ("2026-10-31T12:00:00Z", "live", ("Practice 3", False)),     # between sessions: still a live weekend
    ("2026-11-01T21:30:00Z", "live", ("Race", True)),
    ("2026-11-01T23:30:00Z", "completed", None),                 # 3h after the start, result or not
])
def test_weekend_status_through_a_weekend(at, status, session):
    t = race_data.utc(at)
    assert race_data.weekend_status(MEXICO, t) == status
    s = race_data.session_now(MEXICO, t)
    assert (None if s is None else (s[0], s[2])) == session


def test_a_published_result_marks_the_race_completed_early():
    assert race_data.weekend_status(MEXICO, race_data.utc("2026-11-01T21:30:00Z"), has_result=True) == "completed"


def test_sprint_weekend_sessions_are_in_time_order():
    china = {"fp1_utc": "2026-03-13T03:30:00Z", "sprint_qualifying_utc": "2026-03-13T07:30:00Z",
             "sprint_utc": "2026-03-14T03:00:00Z", "qualifying_utc": "2026-03-14T07:00:00Z",
             "race_utc": "2026-03-15T07:00:00Z", "fp2_utc": None, "fp3_utc": None}
    assert [n for n, *_ in race_data.sessions(china)] == ["Practice 1", "Sprint Qualifying", "Sprint", "Qualifying", "Race"]


def test_now_can_be_pinned_for_demos(monkeypatch):
    monkeypatch.setenv("BOXBOX_NOW", "2026-10-31T21:30:00Z")
    assert race_data.now() == race_data.utc("2026-10-31T21:30:00Z")


def test_calendar_marks_winners_and_status(store):
    cal = race_data.calendar(2026, at=race_data.utc("2026-03-31T00:00:00Z")).set_index("round")
    assert cal.loc[1, "status"] == "completed" and cal.loc[1, "winner_code"] == "RUS"
    assert cal.loc[4, "status"] == "upcoming" and cal.loc[4, "winner"] is None


def test_strategy_links_point_at_circuits_in_the_content():
    import json
    ids = {c["circuit_id"] for c in json.loads((race_data.BASE / "content" / "circuits.json").read_text("utf-8"))["circuits"]}
    assert set(race_data.STRATEGY_CIRCUIT) <= ids
    assert {"madring", "sepang", "interlagos"} <= ids - set(race_data.STRATEGY_CIRCUIT)
