"""
Shared test helpers. Tests never touch the network: FakeSession serves saved Jolpica
responses from tests/fixtures/jolpica (real 2026 data, results trimmed to rounds 1-3).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "dash_app")]

FIXTURES = ROOT / "tests" / "fixtures" / "jolpica"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers, self.encoding = status, body, headers or {}, None

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Maps "<path after /f1/2026/>@<offset>" to a fixture file, and records every call."""

    ROUTES = {"races/@0": "races.json", "results/@0": "results_0.json", "results/@30": "results_30.json",
              **{f"{r}/driverstandings/@0": f"driverstandings_{r}.json" for r in (1, 2, 3)},
              **{f"{r}/constructorstandings/@0": f"constructorstandings_{r}.json" for r in (1, 2, 3)}}

    def __init__(self, queued=None):
        self.headers, self.calls, self.queued = {}, [], list(queued or [])

    def get(self, url, params=None, timeout=None):
        key = f"{url.split('/f1/2026/')[1]}@{params['offset']}"
        self.calls.append(key)
        if self.queued:
            return self.queued.pop(0)
        return FakeResponse(200, fixture(self.ROUTES[key]))


@pytest.fixture
def client():
    from ingest.jolpica import Client
    return Client(session=FakeSession(), min_interval=0, sleep=lambda s: None)
