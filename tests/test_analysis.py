import pandas as pd
import pytest

import figures as F
import race_data as R


def stints(*rows):
    return pd.DataFrame(rows, columns=["driver_number", "stint_number", "compound", "lap_start", "lap_end", "tyre_age_at_start"])


def laps_for(driver, laps, base, slope, pit_out=()):
    return [{"driver_number": driver, "lap_number": l, "lap_duration": base + slope * (l - 1) - R.FUEL_PER_LAP * l,
             "is_pit_out_lap": int(l in pit_out)} for l in laps]


NO_PERIODS = pd.DataFrame(columns=["kind", "start_lap", "end_lap"])
NO_PITS = pd.DataFrame(columns=["driver_number", "lap_number"])


def test_clean_laps_drop_lap_one_pit_laps_neutralised_laps_and_wet_tyres():
    laps = pd.DataFrame(laps_for(1, range(1, 21), 100, 0.05, pit_out=[11]) + laps_for(2, range(1, 6), 100, 0.05))
    st = stints((1, 1, "MEDIUM", 1, 10, 0), (1, 2, "HARD", 11, 20, 0), (2, 1, "INTERMEDIATE", 1, 5, 0))
    pits = pd.DataFrame({"driver_number": [1], "lap_number": [10]})
    periods = pd.DataFrame([{"kind": "VSC", "start_lap": 15, "end_lap": 16}])
    clean = R.clean_race_laps(laps, st, pits, periods)
    assert sorted(clean["lap_number"]) == [2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 17, 18, 19, 20]
    assert set(clean["driver_number"]) == {1}                                  # intermediates are not dry
    lap12 = clean[clean["lap_number"] == 12].iloc[0]
    assert (lap12["compound"], lap12["tyre_age"]) == ("HARD", 1)
    assert lap12["fuel_corrected"] == pytest.approx(100 + 0.05 * 11)           # fuel effect taken back out


def test_outliers_above_two_standard_deviations_are_dropped():
    laps = pd.DataFrame(laps_for(1, range(2, 31), 100, 0.0) + [{"driver_number": 1, "lap_number": 31,
                                                                  "lap_duration": 140.0, "is_pit_out_lap": 0}])
    clean = R.clean_race_laps(laps, stints((1, 1, "SOFT", 1, 31, 0)), NO_PITS, NO_PERIODS)
    assert 31 not in set(clean["lap_number"]) and len(clean) == 29


def test_degradation_slope_is_measured_within_each_stint():
    # Driver 1 is 2 s a lap slower than driver 2, but both lose exactly 0.08 s per lap of tyre age.
    laps = pd.DataFrame(laps_for(1, range(2, 22), 102, 0.08) + laps_for(2, range(2, 22), 100, 0.08))
    st = stints((1, 1, "HARD", 1, 21, 0), (2, 1, "HARD", 1, 21, 0))
    rates = R.degradation(R.clean_race_laps(laps, st, NO_PITS, NO_PERIODS))
    assert rates.to_dict("records") == [{"compound": "HARD", "rate": 0.08, "stints": 2, "laps": 40}]


def test_pooling_across_drivers_would_have_faked_a_trend():
    # A slow driver on old tyres and a fast one on new tyres, no wear at all: within-stint rate is ~0.
    slow = laps_for(1, range(2, 12), 103, 0.0)
    fast = laps_for(2, range(2, 12), 100, 0.0)
    st = stints((1, 1, "SOFT", 1, 11, 20), (2, 1, "SOFT", 1, 11, 0))
    clean = R.clean_race_laps(pd.DataFrame(slow + fast), st, NO_PITS, NO_PERIODS)
    assert R.degradation(clean)["rate"].iloc[0] == pytest.approx(0.0, abs=1e-9)
    naive = clean[["tyre_age", "fuel_corrected"]].cov().iloc[0, 1] / clean["tyre_age"].var()
    assert naive > 0.05                                                      # what a pooled slope would claim


def test_short_stints_are_left_out():
    laps = pd.DataFrame(laps_for(1, range(2, 6), 100, 0.1))
    clean = R.clean_race_laps(laps, stints((1, 1, "SOFT", 1, 5, 0)), NO_PITS, NO_PERIODS)
    assert R.degradation(clean).empty


def test_race_pace_is_the_median_fastest_first():
    clean = pd.DataFrame({"driver_number": [1, 1, 1, 2, 2, 2], "fuel_corrected": [101, 102, 150, 100.5, 100.6, 100.7]})
    pace = R.race_pace(clean)
    assert pace["driver_number"].tolist() == [2, 1] and pace["pace"].tolist() == [100.6, 102.0]


def test_gap_bars_always_point_right_and_keep_the_sign_in_the_label():
    fig = F.gap_bars([349, 345, 337], ["RUS", "LIN", "LAW"], "km/h", fmt="{:+.0f} km/h")
    assert list(fig.data[0].x) == [0, 4, 12]
    assert list(fig.data[0].text) == ["Best", "-4 km/h", "-12 km/h"]
