"""
Small client for OpenF1's free historical API (https://openf1.org). No key needed.

Free-tier rules this project is built around:
- A session is "live" from 30 minutes before it starts until 30 minutes after it ends, and
  live data is a paid tier we don't use. Everything outside that window is free.
- Up to 3 requests a second and 30 a minute, so requests are spaced 2 s apart and a 429 is
  retried after a pause.
"""

import time

import requests

BASE_URL = "https://api.openf1.org/v1"
MIN_INTERVAL = 2.0          # seconds between requests: the free tier allows 30 a minute
RETRIES = 5


class Client:
    def __init__(self, session=None, min_interval=MIN_INTERVAL, sleep=time.sleep):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "BoxBox Race Centre (github.com/aditya-patra1011)")
        self.min_interval = min_interval
        self.sleep = sleep
        self.requests = 0
        self._last = 0.0

    def get(self, endpoint, **params):
        """GET /v1/<endpoint>. Filters like date>= go in as {"date>": ...} via **{"date>": value}."""
        url = f"{BASE_URL}/{endpoint}"
        for attempt in range(RETRIES):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
            resp = self.session.get(url, params=params, timeout=60)
            self._last = time.monotonic()
            self.requests += 1
            if resp.status_code == 429 or resp.status_code >= 500:
                self.sleep(float(resp.headers.get("Retry-After", 2 ** (attempt + 1))))
                continue
            if resp.status_code == 404:          # OpenF1 answers 404 for "no rows match"
                return []
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"OpenF1 kept failing for {url} {params}")
