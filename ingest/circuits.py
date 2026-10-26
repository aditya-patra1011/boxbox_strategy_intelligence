"""
Builds the Race Centre circuit content for one season from free data only:

  content/circuits/<circuit_id>.json   track outline from the fastest qualifying lap's car positions
  content/circuits.json                 facts per circuit (first Grand Prix, races held, lap length, laps)

Outlines stay in OpenF1's own x/y coordinates, so live car positions from the same source
can be drawn straight on top later; `rotation_deg` says how to turn them for display.
Nothing here uses official F1 track graphics.

Run from the repo root:  python -m ingest.circuits --season 2026
"""

import argparse
import json
import math
from datetime import date, datetime, timedelta, timezone

from . import jolpica
from . import openf1
from .store import BASE

CONTENT = BASE / "content"
MIN_POINTS = 150            # a full lap at ~3.7 Hz has 300+; fewer means gaps in the data


# ── pure helpers ──

def orientation(x, y):
    """Degrees to rotate the outline so its long axis runs left to right (principal component)."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    angle = 0.5 * math.degrees(math.atan2(2 * sxy, sxx - syy))
    return round(-angle, 1)


def rotate(x, y, deg):
    """Rotate points about their centre. Rotation only, never a mirror, so corners keep their direction."""
    t = math.radians(deg)
    mx, my = sum(x) / len(x), sum(y) / len(y)
    c, s = math.cos(t), math.sin(t)
    return ([(a - mx) * c - (b - my) * s for a, b in zip(x, y)],
            [(a - mx) * s + (b - my) * c for a, b in zip(x, y)])


def path_length_m(x, y):
    """Length of the closed outline in metres (OpenF1 x/y are in tenths of a metre).

    This is the pole lap's racing line, which cuts corners, so it reads about 1-2% under the
    official centreline length. Checked against 22 published lengths: median -1.4%."""
    pts = list(zip(x, y)) + [(x[0], y[0])]
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) / 10


def clean_outline(location):
    """OpenF1 location rows -> x, y lists without repeated points."""
    x, y = [], []
    for r in location:
        if x and r["x"] == x[-1] and r["y"] == y[-1]:
            continue
        x.append(r["x"])
        y.append(r["y"])
    return x, y


def meeting_for(race_day, meetings):
    """The OpenF1 meeting (race weekend) that contains a Jolpica race date."""
    for m in meetings:
        start, end = date.fromisoformat(m["date_start"][:10]), date.fromisoformat(m["date_end"][:10])
        if start <= race_day <= end and not m.get("is_cancelled"):
            return m
    return None


# ── network steps ──

def fastest_lap_outline(f1, session_key, tries=3):
    """Outline and length from the fastest complete qualifying lap that has full position data."""
    laps = sorted((l for l in f1.get("laps", session_key=session_key) if l.get("lap_duration")),
                  key=lambda l: l["lap_duration"])
    for lap in laps[:tries]:
        start = datetime.fromisoformat(lap["date_start"])
        window = {"session_key": session_key, "driver_number": lap["driver_number"],
                  "date>": start.isoformat(), "date<": (start + timedelta(seconds=lap["lap_duration"])).isoformat()}
        x, y = clean_outline(f1.get("location", **window))
        if len(x) < MIN_POINTS:
            continue
        return {"x": x, "y": y, "rotation_deg": orientation(x, y),
                "source": {"session_key": session_key, "driver_number": lap["driver_number"],
                           "lap_number": lap["lap_number"], "lap_time_s": lap["lap_duration"]},
                "length_m": round(path_length_m(x, y))}
    return None


def qualifying_outline(f1, meeting):
    sessions = f1.get("sessions", meeting_key=meeting["meeting_key"], session_name="Qualifying")
    if not sessions:
        return None
    out = fastest_lap_outline(f1, sessions[0]["session_key"])
    if out:
        out["source"]["year"] = sessions[0]["year"]
    return out


def history(jc, circuit_id):
    """First Grand Prix, number held, and the latest race's lap count at this circuit (from winners)."""
    first = jc.get(f"circuits/{circuit_id}/results/1", limit=1)
    total = int(first["total"])
    latest = jc.get(f"circuits/{circuit_id}/results/1", limit=1, offset=total - 1) if total > 1 else first
    f, l = first["RaceTable"]["Races"][0], latest["RaceTable"]["Races"][0]
    return {"first_gp": int(f["season"]), "gp_count": total,
            "race_laps": int(l["Results"][0]["laps"]), "race_laps_season": int(l["season"])}


def build(season, jc=None, f1=None, out=CONTENT, log=print):
    jc, f1 = jc or jolpica.Client(), f1 or openf1.Client()
    races = [jolpica.parse_race(r) for r in jc.paged(f"{season}/races", "RaceTable", "Races")]
    meetings = {y: f1.get("meetings", year=y) for y in (season, season - 1)}
    (out / "circuits").mkdir(parents=True, exist_ok=True)

    facts = []
    for race in races:
        cid, day = race["circuit_id"], date.fromisoformat(race["race_utc"][:10])
        meeting = meeting_for(day, meetings[season])
        outline = qualifying_outline(f1, meeting) if meeting else None
        if outline is None and meeting:                 # not raced yet this season: use last year's lap
            prev = [m for m in meetings[season - 1]
                    if m["circuit_key"] == meeting["circuit_key"] and not m.get("is_cancelled")]
            outline = qualifying_outline(f1, prev[-1]) if prev else None
        if outline is None:
            log(f"R{race['round']:>2} {cid}: no outline found")
            continue

        (out / "circuits" / f"{cid}.json").write_text(json.dumps({
            "circuit_id": cid, "rotation_deg": outline["rotation_deg"],
            "x": outline["x"], "y": outline["y"], "source": outline["source"]}), encoding="utf-8")
        facts.append({"round": race["round"], "circuit_id": cid, "circuit_name": race["circuit_name"],
                      "locality": race["locality"], "country": race["country"],
                      "openf1_circuit_key": meeting["circuit_key"], "openf1_name": meeting["circuit_short_name"],
                      "racing_line_km": round(outline["length_m"] / 1000, 3), **history(jc, cid),
                      "outline": f"circuits/{cid}.json", "outline_year": outline["source"]["year"]})
        f = facts[-1]
        log(f"R{race['round']:>2} {cid:<14} {len(outline['x'])} pts  {f['racing_line_km']:.3f} km  "
            f"first GP {f['first_gp']}  ({outline['source']['year']} quali lap)")

    (out / "circuits.json").write_text(json.dumps({
        "season": season, "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": "Outlines and racing-line length: OpenF1 historical car positions (pole lap; reads "
                   "~1-2% under the official centreline length). History: Jolpica F1 API.",
        "circuits": facts}, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"done: {len(facts)}/{len(races)} circuits, {jc.requests} Jolpica + {f1.requests} OpenF1 requests")
    return facts


def main():
    ap = argparse.ArgumentParser(prog="python -m ingest.circuits", description="Build Race Centre circuit content.")
    ap.add_argument("--season", type=int, default=date.today().year)
    build(ap.parse_args().season)


if __name__ == "__main__":
    main()
