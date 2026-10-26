import json

import pytest

from ingest import teams as T
from ingest.store import BASE

TEAMS = T.load_teams()


def test_owner_follows_lineage_years():
    assert T.owner(TEAMS, "tyrrell", 1971) == ("mercedes", "Tyrrell")
    assert T.owner(TEAMS, "brawn", 2009) == ("mercedes", "Brawn GP")
    assert T.owner(TEAMS, "mercedes", 1954) == (None, None)        # Stuttgart works team, not Brackley
    assert T.owner(TEAMS, "renault", 1983) == (None, None)         # Viry works team, not Enstone
    assert T.owner(TEAMS, "renault", 2005) == ("alpine", "Renault")
    assert T.owner(TEAMS, "sauber", 2024) == ("audi", "Sauber")
    assert T.owner(TEAMS, "williams", 1976) == (None, None)        # Frank Williams Racing Cars
    assert T.owner(TEAMS, "mclaren-ford", 1969) == ("mclaren", "McLaren")


def test_summarise_credits_predecessors_and_mid_season_moves():
    drivers = [{"season": 1971, "driver": "Jackie Stewart", "constructor_ids": ["tyrrell"]},
               {"season": 1954, "driver": "Juan Manuel Fangio", "constructor_ids": ["maserati", "mercedes"]},
               {"season": 2009, "driver": "Jenson Button", "constructor_ids": ["brawn"]}]
    constructors = [{"season": 1971, "constructor_id": "tyrrell"}, {"season": 2009, "constructor_id": "brawn"},
                    {"season": 2014, "constructor_id": "mercedes"}]
    wins = [{"season": 2009, "round": 1, "race": "Australian Grand Prix", "driver": "Jenson Button", "constructor_id": "brawn"},
            {"season": 1970, "round": 12, "race": "x", "driver": "y", "constructor_id": "tyrrell"},
            {"season": 2013, "round": 3, "race": "Chinese Grand Prix", "driver": "z", "constructor_id": "mercedes"},
            {"season": 2020, "round": 1, "race": "Austrian Grand Prix", "driver": "Valtteri Bottas", "constructor_id": "mercedes"}]
    s = T.summarise(TEAMS, drivers, constructors, wins, 2025)["mercedes"]
    assert [t["season"] for t in s["constructors_titles"]] == [1971, 2009, 2014]
    assert [t["driver"] for t in s["drivers_titles"]] == ["Jackie Stewart", "Jenson Button"]   # Fangio 1954 is not Brackley
    assert s["wins"] == 4 and s["wins_by_name"] == {"Tyrrell": 1, "Brawn GP": 1, "Mercedes": 2}
    assert s["first_win"]["as"] == "Tyrrell" and s["latest_win"]["season"] == 2020


def test_lineage_steps_never_overlap_within_a_team():
    for t in TEAMS:
        spans = sorted((s["from"], s["to"] or 9999, s["name"]) for s in t["lineage"])
        for (a0, a1, an), (b0, b1, bn) in zip(spans, spans[1:]):
            # Midland became Spyker MF1 during 2006: the one allowed same-year hand-over
            assert a1 < b0 or (a1 == b0 == 2006), f"{t['id']}: {an} and {bn} overlap"


def test_every_2026_constructor_has_content_and_a_timeline():
    ids = {t["id"] for t in TEAMS}
    current = {"mercedes", "ferrari", "mclaren", "red_bull", "rb", "alpine", "haas", "audi", "williams",
               "aston_martin", "cadillac"}
    assert ids == current
    for t in TEAMS:
        assert t["colour"].startswith("#") and len(t["colour"]) == 7
        years = [e["year"] for e in t["timeline"]]
        assert years == sorted(years) and len(years) >= 2
        assert t["id"] in t["lineage"][-1]["constructor_ids"] and t["lineage"][-1]["to"] is None


@pytest.mark.skipif(not (BASE / "content" / "team_stats.json").exists(), reason="run python -m ingest.teams")
def test_computed_stats_cover_every_team():
    stats = json.loads((BASE / "content" / "team_stats.json").read_text(encoding="utf-8"))["teams"]
    assert set(stats) == {t["id"] for t in TEAMS}
