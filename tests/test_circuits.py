import math

import pytest

from ingest import circuits as C


def ellipse(n=200, a=1000, b=300, tilt=30):
    t = math.radians(tilt)
    pts = [(a * math.cos(2 * math.pi * i / n), b * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return ([px * math.cos(t) - py * math.sin(t) for px, py in pts],
            [px * math.sin(t) + py * math.cos(t) for px, py in pts])


def signed_area(x, y):
    return sum(x[i] * y[i + 1] - x[i + 1] * y[i] for i in range(-1, len(x) - 1)) / 2


def test_orientation_turns_long_axis_horizontal():
    x, y = ellipse(tilt=30)
    assert C.orientation(x, y) == pytest.approx(-30, abs=0.2)
    rx, ry = C.rotate(x, y, C.orientation(x, y))
    assert max(rx) - min(rx) > 3 * (max(ry) - min(ry))


def test_rotate_never_mirrors_the_track():
    x, y = ellipse(tilt=70)
    rx, ry = C.rotate(x, y, C.orientation(x, y))
    assert math.copysign(1, signed_area(x, y)) == math.copysign(1, signed_area(rx, ry))


def test_path_length_closes_the_loop_and_converts_units():
    # a 100 m square in OpenF1 units (tenths of a metre)
    assert C.path_length_m([0, 1000, 1000, 0], [0, 0, 1000, 1000]) == pytest.approx(400)


def test_clean_outline_drops_repeated_points():
    rows = [{"x": 1, "y": 1}, {"x": 1, "y": 1}, {"x": 2, "y": 1}, {"x": 2, "y": 1}, {"x": 1, "y": 1}]
    assert C.clean_outline(rows) == ([1, 2, 1], [1, 1, 1])


def test_meeting_for_skips_cancelled_weekends():
    meetings = [{"meeting_key": 1, "date_start": "2026-04-10T10:00", "date_end": "2026-04-12T18:00", "is_cancelled": True},
                {"meeting_key": 2, "date_start": "2026-04-10T10:00", "date_end": "2026-04-12T18:00", "is_cancelled": False},
                {"meeting_key": 3, "date_start": "2026-05-01T10:00", "date_end": "2026-05-03T18:00", "is_cancelled": False}]
    from datetime import date
    assert C.meeting_for(date(2026, 4, 12), meetings)["meeting_key"] == 2
    assert C.meeting_for(date(2026, 4, 20), meetings) is None


class FakeOpenF1:
    """Lap 1 is fastest but has a gap in its position data; lap 2 is complete."""

    def __init__(self):
        self.requests, self.calls = 0, []
        x, y = ellipse(n=320)
        self.full = [{"x": round(a), "y": round(b)} for a, b in zip(x, y)]

    def get(self, endpoint, **p):
        self.calls.append((endpoint, p.get("driver_number")))
        if endpoint == "laps":
            return [{"driver_number": 1, "lap_number": 5, "lap_duration": 80.1, "date_start": "2026-09-12T14:58:00+00:00"},
                    {"driver_number": 4, "lap_number": 9, "lap_duration": 80.3, "date_start": "2026-09-12T15:01:00+00:00"},
                    {"driver_number": 7, "lap_number": 2, "lap_duration": None, "date_start": "2026-09-12T14:20:00+00:00"}]
        if endpoint == "location":
            return self.full[:40] if p["driver_number"] == 1 else self.full
        raise AssertionError(endpoint)


def test_fastest_lap_outline_skips_a_lap_with_missing_positions():
    out = C.fastest_lap_outline(FakeOpenF1(), session_key=11365)
    assert out["source"]["driver_number"] == 4 and out["source"]["lap_number"] == 9
    assert len(out["x"]) == 320
    a, b = 1000, 300                                   # Ramanujan's ellipse perimeter, tenths of a metre -> m
    assert out["length_m"] == pytest.approx(math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b))) / 10, rel=0.01)
