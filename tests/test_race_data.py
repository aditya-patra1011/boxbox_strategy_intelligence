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
