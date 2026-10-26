import json
from datetime import datetime, timedelta

import pandas as pd
import pytest

import race_data as R
from conftest import ROOT

FIX = ROOT / "tests" / "fixtures" / "openf1"


def race_control(name):
    return pd.DataFrame(json.loads((FIX / f"race_control_{name}.json").read_text(encoding="utf-8")))


def periods(name):
    return [(p["kind"], p["start_lap"], p["end_lap"], p["laps"]) for p in R.neutralisations(race_control(name)).to_dict("records")]


def test_vsc_periods_melbourne():
    assert periods("melbourne") == [("VSC", 12, 14, 3), ("VSC", 18, 20, 3), ("VSC", 34, 34, 1)]


def test_safety_car_period_shanghai():
    assert periods("shanghai") == [("SC", 10, 13, 4)]


def test_red_flag_ends_the_safety_car_and_lasts_until_the_restart_monaco():
    assert periods("monaco") == [("SC", 60, 65, 6), ("SC", 66, 68, 3), ("RED", 68, 68, 1)]
    red = R.neutralisations(race_control("monaco")).iloc[-1]
    assert red["minutes"] == pytest.approx(36.9, abs=0.1)        # 14:35:07 -> SESSION STARTED 15:12:00


def test_red_flag_infringement_notes_do_not_open_a_red_flag():
    rc = race_control("monaco")
    notes = rc[rc["message"].str.contains("RED FLAG INFRINGEMENT", na=False)]
    assert not notes.empty and R.neutralisations(notes).empty


def test_no_messages_no_periods():
    assert R.neutralisations(pd.DataFrame()).empty


def test_lap_starts_take_the_first_car_and_lap_at_counts_them():
    laps = pd.DataFrame({"lap_number": [1, 1, 2, 2], "date_start": [
        "2026-10-25T20:03:49+00:00", "2026-10-25T20:03:50+00:00", "2026-10-25T20:05:30+00:00", "2026-10-25T20:05:31+00:00"]})
    starts = R.lap_starts(laps, "2026-10-25T20:00:00+00:00")
    assert starts == {1: 229.0, 2: 330.0}
    assert (R.lap_at(starts, 100), R.lap_at(starts, 229), R.lap_at(starts, 400)) == (0, 1, 2)


def test_board_at_uses_the_latest_position_and_gap_before_t():
    start = "2026-10-25T20:00:00+00:00"
    at = lambda s: (datetime.fromisoformat(start) + timedelta(seconds=s)).isoformat()
    positions = pd.DataFrame({"driver_number": [12, 63, 12, 63], "position": [1, 2, 2, 1],
                              "date": [at(0), at(0), at(500), at(500)]})
    intervals = pd.DataFrame({"driver_number": [12, 63, 12], "gap_to_leader": [0.0, 1.5, None],
                              "gap_text": [None, None, "+1 LAP"], "date": [at(450), at(450), at(600)]})
    drivers = pd.DataFrame({"driver_number": [12, 63], "code": ["ANT", "RUS"]})
    assert R.board_at(100, start, positions, intervals, drivers)[["code", "gap"]].values.tolist() ==         [["ANT", "Leader"], ["RUS", ""]]                          # no gap published yet
    early = R.board_at(460, start, positions, intervals, drivers)
    assert early[["code", "gap"]].values.tolist() == [["ANT", "Leader"], ["RUS", "+1.5"]]
    late = R.board_at(700, start, positions, intervals, drivers)
    assert late[["code", "gap"]].values.tolist() == [["RUS", "Leader"], ["ANT", "+1 LAP"]]


def test_tyre_on_lap_counts_age_from_the_start_of_the_stint():
    stints = pd.DataFrame({"driver_number": [12, 12, 44], "stint_number": [1, 2, 1], "compound": ["MEDIUM", "HARD", "SOFT"],
                           "lap_start": [1, 25, 1], "tyre_age_at_start": [0, 0, 2]})
    idx = R.stint_index(stints)
    assert R.tyre_on_lap(idx, 12, 24) == ("MEDIUM", 23)
    assert R.tyre_on_lap(idx, 12, 30) == ("HARD", 5)
    assert R.tyre_on_lap(idx, 44, 1) == ("SOFT", 2)               # a used set from qualifying
    assert R.tyre_on_lap(idx, 99, 5) == (None, None)


def test_replay_chunk_turns_samples_into_the_display_frame(tmp_path, monkeypatch):
    from ingest.store import connect, upsert
    path = tmp_path / "r.sqlite"
    conn = connect(path)
    o = R.outline("americas")
    centre = (sum(o["x"]) / len(o["x"]), sum(o["y"]) / len(o["y"]))
    upsert(conn, "car_samples", [{"session_key": 1, "driver_number": 12, "t": t, "x": centre[0], "y": centre[1] + 100,
                                  "speed": 300, "throttle": None, "brake": None, "gear": None, "rpm": None} for t in (0, 0.5, 1)])
    conn.commit(), conn.close()
    monkeypatch.setattr(R, "STORE", path)
    chunk = R.replay_chunk(1, "americas", 0, 0.5)
    assert list(chunk) == [12] and chunk[12]["t"] == [0.0, 0.5] and chunk[12]["s"] == [300, 300]
    # a point 100 units "north" of the centre ends up 100 units from the origin after rotation
    assert (chunk[12]["x"][0] ** 2 + chunk[12]["y"][0] ** 2) ** 0.5 == pytest.approx(100, abs=1)
