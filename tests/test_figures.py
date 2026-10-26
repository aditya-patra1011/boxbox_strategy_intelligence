import re

import figures as F


def test_track_svg_fits_its_box_and_flips_y():
    x, y = [0, 100, 100, 0], [0, 0, 50, 50]
    uri = F.track_svg((x, y), width=200, height=110, pad=8)
    assert uri.startswith("data:image/svg+xml;utf8,") and "#" not in uri          # colours escaped
    pts = [tuple(map(float, p.split())) for p in re.findall(r"[ML]([\d.]+ [\d.]+)", uri)]
    assert all(8 - 0.1 <= a <= 192 + 0.1 and 8 - 0.1 <= b <= 102 + 0.1 for a, b in pts)
    assert pts[0][1] > pts[2][1]                       # y=0 (bottom) is drawn lower than y=50


def test_track_svg_without_outline():
    assert F.track_svg(None) is None
