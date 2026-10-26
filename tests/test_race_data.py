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
