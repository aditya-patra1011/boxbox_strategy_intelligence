"""
Small client for the Jolpica F1 API (the community successor to Ergast).

Free, no key. Fair-use limits are 4 requests a second and 500 an hour, so every
request is spaced out and a 429 is retried after a pause.
"""

import time

import requests

BASE_URL = "https://api.jolpi.ca/ergast/f1"
PAGE_SIZE = 100
MIN_INTERVAL = 0.3          # seconds between requests, keeps us under 4 a second
RETRIES = 4


class Client:
    def __init__(self, session=None, min_interval=MIN_INTERVAL, sleep=time.sleep):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "BoxBox Race Centre (github.com/aditya-patra1011)")
        self.min_interval = min_interval
        self.sleep = sleep
        self.requests = 0
        self._last = 0.0

    def get(self, path, limit=PAGE_SIZE, offset=0):
        """GET one page and return its MRData block."""
        url = f"{BASE_URL}/{path.strip('/')}/"
        for attempt in range(RETRIES):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
            resp = self.session.get(url, params={"limit": limit, "offset": offset}, timeout=30)
            self._last = time.monotonic()
            self.requests += 1
            if resp.status_code == 429 or resp.status_code >= 500:
                self.sleep(float(resp.headers.get("Retry-After", 2 ** (attempt + 1))))
                continue
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.json()["MRData"]
        raise RuntimeError(f"Jolpica kept failing for {url}")

    def paged(self, path, table, items):
        """Yield every item of MRData[table][items] across all pages."""
        offset = 0
        while True:
            page = self.get(path, offset=offset)
            yield from page[table][items]
            offset += int(page["limit"])
            if offset >= int(page["total"]):
                return


# ── parsing: Jolpica JSON -> flat rows that match the store's tables ──

SESSIONS = {"FirstPractice": "fp1", "SecondPractice": "fp2", "ThirdPractice": "fp3",
            "SprintQualifying": "sprint_qualifying", "Sprint": "sprint", "Qualifying": "qualifying"}


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utc(block):
    """{"date": "2026-03-08", "time": "04:00:00Z"} -> "2026-03-08T04:00:00Z"."""
    if not block or "date" not in block:
        return None
    return f"{block['date']}T{block['time']}" if block.get("time") else block["date"]


def parse_race(r):
    loc = r["Circuit"]["Location"]
    row = {"season": _int(r["season"]), "round": _int(r["round"]), "race_name": r["raceName"],
           "circuit_id": r["Circuit"]["circuitId"], "circuit_name": r["Circuit"]["circuitName"],
           "locality": loc.get("locality"), "country": loc.get("country"),
           "lat": _float(loc.get("lat")), "lon": _float(loc.get("long")),
           "race_utc": _utc(r)}
    for key, col in SESSIONS.items():
        row[f"{col}_utc"] = _utc(r.get(key))
    return row


def parse_driver(d):
    return {"driver_id": d["driverId"], "code": d.get("code"), "number": _int(d.get("permanentNumber")),
            "given_name": d["givenName"], "family_name": d["familyName"],
            "date_of_birth": d.get("dateOfBirth"), "nationality": d.get("nationality")}


def parse_constructor(c):
    return {"constructor_id": c["constructorId"], "name": c["name"], "nationality": c.get("nationality")}


def parse_results(race):
    """One race block (with its Results list) -> result rows."""
    season, rnd = _int(race["season"]), _int(race["round"])
    rows = []
    for x in race["Results"]:
        fl, t = x.get("FastestLap", {}), x.get("Time", {})
        rows.append({"season": season, "round": rnd,
                     "driver_id": x["Driver"]["driverId"], "constructor_id": x["Constructor"]["constructorId"],
                     "number": _int(x.get("number")), "grid": _int(x.get("grid")),
                     "position": _int(x.get("position")), "position_text": x.get("positionText"),
                     "points": _float(x.get("points")), "laps": _int(x.get("laps")), "status": x.get("status"),
                     "time_text": t.get("time"), "time_millis": _int(t.get("millis")),
                     "fastest_lap_rank": _int(fl.get("rank")), "fastest_lap_lap": _int(fl.get("lap")),
                     "fastest_lap_time": fl.get("Time", {}).get("time")})
    return rows


def parse_driver_standings(lst):
    season, rnd = _int(lst["season"]), _int(lst["round"])
    return [{"season": season, "round": rnd, "driver_id": s["Driver"]["driverId"],
             "constructor_id": s["Constructors"][-1]["constructorId"] if s.get("Constructors") else None,
             "position": _int(s.get("position")), "position_text": s.get("positionText"),
             "points": _float(s.get("points")), "wins": _int(s.get("wins"))}
            for s in lst["DriverStandings"]]


def parse_constructor_standings(lst):
    season, rnd = _int(lst["season"]), _int(lst["round"])
    return [{"season": season, "round": rnd, "constructor_id": s["Constructor"]["constructorId"],
             "position": _int(s.get("position")), "position_text": s.get("positionText"),
             "points": _float(s.get("points")), "wins": _int(s.get("wins"))}
            for s in lst["ConstructorStandings"]]
