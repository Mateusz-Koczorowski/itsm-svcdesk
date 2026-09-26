# ai-generated: 100% - Claude wrote this stdlib HTTP helper for the own-tests suite
"""Tiny HTTP client on the standard library, so the tests image needs nothing beyond pytest."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BASE_URL = os.environ.get("SVCDESK_URL", "http://svcdesk:8080").rstrip("/")


def call(method: str, path: str, body: object | None = None, clock: str | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE_URL + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if clock:
        request.add_header("X-Test-Clock", clock)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"null")
        except ValueError:
            return exc.code, raw.decode(errors="replace")


def wait_for_health(seconds: float = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if call("GET", "/health")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError(f"{BASE_URL}/health did not answer 200 within {seconds} s")


def ticket(impact: int = 1, urgency: int = 1, vip: bool = False, **extra: object) -> dict:
    body = {"title": "Printer on floor 2 is down", "reporter": {"name": "Test Reporter", "vip": vip},
            "impact": impact, "urgency": urgency}
    body.update(extra)
    return body
