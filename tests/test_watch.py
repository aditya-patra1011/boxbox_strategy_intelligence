from datetime import datetime, timezone

import pytest

import race_data
from ingest import watch as W
from ingest.store import connect
from test_session import FakeOpenF1


def t(text):
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


RACES = [{"round": 17, "race_utc": "2026-10-11T12:00:00Z"}, {"round": 18, "race_utc": "2026-10-25T20:00:00Z"},
         {"round": 19, "race_utc": "2026-11-01T20:00:00Z"}]
FRESH = {"season": t("2026-10-25T19:00:00")}


def jobs(now, stored=(17,), results=(17,), last_run=None):
    return W.due_jobs(RACES, set(stored), set(results), last_run if last_run is not None else FRESH, t(now))


def test_nothing_before_the_race_starts():
    assert jobs("2026-10-25T19:30:00") == []


def test_results_checks_start_with_the_race_but_the_session_waits_for_free_data():
    assert jobs("2026-10-25T21:00:00") == [("results", 18)]
    # earliest finish (1h45) + OpenF1's 30 minutes = 22:15
    assert jobs("2026-10-25T22:10:00") == [("results", 18)]
    assert jobs("2026-10-25T22:15:00") == [("session", 18), ("results", 18)]


def test_results_are_checked_every_15_minutes_until_they_arrive():
    last = {**FRESH, "results:18": t("2026-10-25T22:15:00")}
    assert jobs("2026-10-25T22:20:00", stored=(17, 18), last_run=last) == []
    assert jobs("2026-10-25T22:30:00", stored=(17, 18), last_run=last) == [("results", 18)]
    assert jobs("2026-10-25T22:30:00", stored=(17, 18), results=(17, 18), last_run=last) == []


def test_old_races_are_left_alone_after_36_hours():
    # round 18 is still missing, but it's too old to chase: only the routine season refresh is due
    assert jobs("2026-10-27T09:00:00") == [("season", None)]


def test_the_season_is_refreshed_every_12_hours_when_nothing_else_does_it():
    assert jobs("2026-10-28T06:00:00", stored=(17, 18), results=(17, 18)) == [("season", None)]
    assert jobs("2026-10-25T23:00:00", stored=(17, 18), results=(17, 18)) == []


def test_a_pass_stores_the_race_once_its_data_is_free(client, tmp_path):
    conn = connect(tmp_path / "w.sqlite")
    f1 = FakeOpenF1(key=11396, start="2026-10-25T20:00:00+00:00")
    log = []
    done = W.tick(conn, client, f1, now=t("2026-10-25T23:00:00"), log=log.append)
    assert done == ["stored race 18", "results 18: not yet"]    # the fixture has no round 18 results
    assert conn.execute("SELECT round, total_laps FROM sessions WHERE session_key = 11396").fetchone() == (18, 3)

    # Five minutes later: the race is stored and both checks ran a moment ago.
    assert W.tick(conn, client, f1, now=t("2026-10-25T23:05:00"), log=log.append) == []
    assert W.tick(conn, client, f1, now=t("2026-10-25T23:20:00"), log=log.append) == ["results 18: not yet"]
    conn.close()


def test_a_pass_waits_when_openf1_has_not_published_yet(client, tmp_path):
    conn = connect(tmp_path / "w.sqlite")
    f1 = FakeOpenF1(key=11396, start="2026-10-25T20:00:00+00:00")   # the race ends 22:00, free from 22:30
    log = []
    done = W.tick(conn, client, f1, now=t("2026-10-25T22:20:00"), log=log.append)
    assert done == ["results 18: not yet"] and any("not free yet" in line for line in log)
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    conn.close()


def test_live_status_during_a_weekend(store):
    s = race_data.live_status(2026, at=race_data.utc("2026-10-31T21:30:00Z"))
    assert (s["race"], s["round"], s["session"], s["running"]) == ("Mexico City Grand Prix", 19, "Qualifying", True)
    assert s["race_data_at"] == race_data.utc("2026-11-01T22:30:00Z")
    assert race_data.live_status(2026, at=race_data.utc("2026-10-27T12:00:00Z")) is None


def test_banner_explains_when_the_data_arrives(store, monkeypatch):
    import live_status
    monkeypatch.setenv("BOXBOX_NOW", "2026-10-31T21:30:00Z")
    text = str(live_status.banner(2026, showing="the US GP replay"))
    assert "Qualifying is on track now" in text and "22:30 UTC" in text and "the US GP replay" in text
    monkeypatch.setenv("BOXBOX_NOW", "2026-10-27T12:00:00Z")
    assert live_status.banner(2026) is None


def test_openf1_client_respects_the_free_rate_limit():
    from ingest import openf1
    assert 60 / openf1.MIN_INTERVAL <= 30
