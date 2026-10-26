from datetime import datetime, timezone

import pandas as pd

import race_data
from ingest import session as S
from ingest.store import connect, upsert

T0 = "2026-10-25T20:00:00+00:00"


def at(seconds):
    return datetime.fromtimestamp(datetime.fromisoformat(T0).timestamp() + seconds, timezone.utc).isoformat()


def test_thin_merges_location_and_car_data_onto_a_half_second_grid():
    location = [{"date": at(0.10), "x": 1, "y": 1}, {"date": at(0.30), "x": 2, "y": 2}, {"date": at(0.60), "x": 3, "y": 3}]
    car = [{"date": at(0.20), "speed": 280, "throttle": 100, "brake": 0, "n_gear": 7, "rpm": 11000},
           {"date": at(1.70), "speed": 150, "throttle": 0, "brake": 100, "n_gear": 3, "rpm": 9000}]
    rows = S.thin(location, car, datetime.fromisoformat(T0))
    assert [r["t"] for r in rows] == [0.0, 0.5, 1.5]
    assert (rows[0]["x"], rows[0]["speed"]) == (1, 280)          # first sample in a slot wins
    assert rows[1]["x"] == 3 and rows[1]["speed"] is None
    assert rows[2]["x"] is None and rows[2]["gear"] == 3


def test_latest_finished_waits_for_the_data_and_skips_cancelled():
    sessions = [{"session_key": 1, "date_start": "2026-10-04T08:00:00+00:00", "date_end": "2026-10-04T10:00:00+00:00"},
                {"session_key": 2, "date_start": "2026-10-25T20:00:00+00:00", "date_end": "2026-10-25T22:00:00+00:00"},
                {"session_key": 3, "date_start": "2026-04-12T15:00:00+00:00", "date_end": "2026-04-12T17:00:00+00:00",
                 "is_cancelled": True}]
    assert S.latest_finished(sessions, S._utc("2026-10-25T22:10:00Z"))["session_key"] == 1   # too fresh
    assert S.latest_finished(sessions, S._utc("2026-10-25T22:45:00Z"))["session_key"] == 2


def test_race_for_finds_the_round_of_the_weekend():
    races = [{"season": 2026, "round": 18, "circuit_id": "americas", "race_utc": "2026-10-25T20:00:00Z"},
             {"season": 2026, "round": 19, "circuit_id": "rodriguez", "race_utc": "2026-11-01T20:00:00Z"}]
    assert S.race_for({"date_start": "2026-10-25T20:00:00+00:00"}, races) == (2026, 18, "americas")
    assert S.race_for({"date_start": "2026-10-24T21:00:00+00:00"}, races) == (2026, 18, "americas")   # qualifying
    assert S.race_for({"date_start": "2026-12-25T20:00:00+00:00"}, races) == (None, None, None)


class FakeOpenF1:
    def __init__(self, key=11396, start=T0):
        self.requests, self.key, self.start = 0, key, start

    def get(self, endpoint, **p):
        self.requests += 1
        k = self.key
        two = [{"driver_number": 12}, {"driver_number": 63}]
        rows = {
            "sessions": [{"session_key": k, "meeting_key": 1297, "year": 2026, "circuit_short_name": "Austin",
                          "session_name": "Race", "session_type": "Race", "date_start": self.start,
                          "date_end": self.start.replace("T20", "T22")}],
            "drivers": [{**d, "name_acronym": c, "first_name": "F", "last_name": c.title(), "team_name": "Mercedes",
                         "team_colour": "27F4D2", "headshot_url": "https://example.invalid/photo.png"}
                        for d, c in zip(two, ["ANT", "RUS"])],
            "laps": [{"driver_number": n, "lap_number": l, "date_start": at(90 * (l - 1) + (n == 63)),
                      "lap_duration": 90.0, "is_pit_out_lap": False} for n in (12, 63) for l in (1, 2, 3)],
            "stints": [{"driver_number": n, "stint_number": 1, "compound": "MEDIUM", "lap_start": 1, "lap_end": 3,
                        "tyre_age_at_start": 0} for n in (12, 63)],
            "pit": [],
            "race_control": [{"date": at(100), "lap_number": 2, "category": "SafetyCar", "flag": None,
                              "message": "VSC DEPLOYED"}],
            "position": [{"driver_number": 12, "date": at(-60), "position": 2}, {"driver_number": 63, "date": at(-60), "position": 1},
                         {"driver_number": 12, "date": at(150), "position": 1}, {"driver_number": 63, "date": at(150), "position": 2}],
            "intervals": [{"driver_number": 63, "date": at(200), "gap_to_leader": 1.2, "interval": 1.2},
                          {"driver_number": 12, "date": at(200), "gap_to_leader": "+1 LAP", "interval": None}],
            "weather": [{"date": at(0), "air_temperature": 24.0, "track_temperature": 38.0}],
            "location": [{"date": at(t / 2), "x": t, "y": -t} for t in range(10)],
            "car_data": [{"date": at(t / 2), "speed": 200 + t} for t in range(10)],
        }
        return rows[endpoint]


def store_with_races(path):
    conn = connect(path)
    upsert(conn, "races", [{"season": 2026, "round": 18, "circuit_id": "americas", "race_utc": "2026-10-25T20:00:00Z"}])
    conn.commit()
    return conn


def test_ingest_session_stores_everything_and_reruns_cleanly(tmp_path, monkeypatch):
    conn = store_with_races(tmp_path / "s.sqlite")
    out = S.ingest_session(FakeOpenF1(), conn, session_key=11396, log=lambda *_: None)
    assert out["laps"] == 6 and out["car_samples"] == 20 and out["race_control"] == 1
    S.ingest_session(FakeOpenF1(), conn, session_key=11396, log=lambda *_: None)     # rerun replaces, never duplicates
    count = lambda t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    assert (count("laps"), count("car_samples"), count("sessions")) == (6, 20, 1)
    assert conn.execute("SELECT season, round, circuit_id, total_laps FROM sessions").fetchone() == (2026, 18, "americas", 3)
    assert "headshot" not in {c[1] for c in conn.execute("PRAGMA table_info(session_drivers)")}   # no photo links stored
    gap = conn.execute("SELECT gap_to_leader, gap_text FROM intervals WHERE driver_number = 12").fetchone()
    assert gap == (None, "+1 LAP")

    conn.close()
    monkeypatch.setattr(race_data, "STORE", tmp_path / "s.sqlite")
    assert race_data.latest_session()["session_key"] == 11396
    assert len(race_data.car_samples(11396, t_from=1, t_to=3, drivers=[12])) == 5
    by_lap = race_data.positions_by_lap(race_data.session_table("laps", 11396),
                                        race_data.session_table("positions", 11396))
    assert by_lap[by_lap["lap_number"] == 1].set_index("driver_number")["position"].to_dict() == {63: 1, 12: 2}
    assert by_lap[by_lap["lap_number"] == 2].set_index("driver_number")["position"].to_dict() == {12: 1, 63: 2}


def test_only_the_newest_sessions_keep_car_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "KEEP_SAMPLES_FOR", 1)
    conn = store_with_races(tmp_path / "s.sqlite")
    S.ingest_session(FakeOpenF1(key=1, start="2026-10-04T08:00:00+00:00"), conn, session_key=1, log=lambda *_: None)
    S.ingest_session(FakeOpenF1(key=2), conn, session_key=2, log=lambda *_: None)
    assert {k for (k,) in conn.execute("SELECT DISTINCT session_key FROM car_samples")} == {2}
    assert conn.execute("SELECT COUNT(*) FROM laps WHERE session_key = 1").fetchone()[0] == 6   # laps stay
    conn.close()


def test_session_table_rejects_unknown_tables():
    import pytest
    with pytest.raises(ValueError):
        race_data.session_table("drivers; DROP TABLE races", 1)
