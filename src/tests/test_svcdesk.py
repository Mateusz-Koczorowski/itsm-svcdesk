# ai-generated: 90% - Claude wrote the cases from API.md and CHECKS.md; I picked what to cover
"""Own conformance suite (Stretch S3): runs against SVCDESK_URL."""

from __future__ import annotations

import pytest

from tests.client import call, ticket

T1 = "2026-10-14T10:00:00Z"


def create(clock: str = T1, **kwargs) -> dict:
    status, body = call("POST", "/tickets", ticket(**kwargs), clock)
    assert status == 201, body
    return body


def drive(t: dict, *actions: tuple[str, str]) -> dict:
    body = t
    for action, clock in actions:
        status, body = call("POST", f"/tickets/{t['id']}/{action}", None, clock)
        assert status == 200, (action, body)
    return body


def test_health():
    status, body = call("GET", "/health")
    assert status == 200 and body["status"] == "ok" and body["service"] == "svcdesk"


def test_unknown_route_is_json_404():
    status, body = call("GET", "/no-such-route")
    assert status == 404 and isinstance(body, dict)


@pytest.mark.parametrize("impact,urgency,expected", [
    (1, 1, "P1"), (1, 2, "P2"), (1, 3, "P3"), (2, 1, "P2"), (2, 2, "P3"),
    (2, 3, "P4"), (3, 1, "P3"), (3, 2, "P4"), (3, 3, "P4"),
])
def test_priority_matrix(impact, urgency, expected):
    assert create(impact=impact, urgency=urgency)["priority"] == expected


def test_vip_does_not_change_priority_c3_matrix():
    assert create(impact=3, urgency=3, vip=True, priority="P1")["priority"] == "P4"


@pytest.mark.parametrize("body", [
    {"reporter": {"name": "x"}, "impact": 1, "urgency": 1},
    {"title": "x" * 201, "reporter": {"name": "x"}, "impact": 1, "urgency": 1},
    {"title": "t", "reporter": {"name": "x"}, "impact": 5, "urgency": 1},
    {"title": "t", "reporter": {"name": "x"}, "impact": 1, "urgency": "high"},
    {"title": "t", "impact": 1, "urgency": 1},
])
def test_validation_rejected(body):
    status, payload = call("POST", "/tickets", body, T1)
    assert status in (400, 422) and "error" in payload


def test_malformed_clock_rejected():
    assert call("POST", "/tickets", ticket(), "yesterday")[0] in (400, 422)


def test_server_owned_fields_ignored():
    t = create(id="mine", state="closed", created_at="2000-01-01T00:00:00Z")
    assert t["id"] != "mine" and t["state"] == "new" and t["created_at"] == T1


@pytest.mark.parametrize("clock,impact,urgency,ack,resolve", [
    ("2026-10-14T10:00:00Z", 1, 1, "2026-10-14T10:15:00Z", "2026-10-14T14:00:00Z"),  # T1
    ("2026-10-16T13:30:00Z", 1, 3, "2026-10-19T09:30:00Z", "2026-10-21T13:30:00Z"),  # T2
    ("2026-10-16T15:00:00Z", 1, 1, "2026-10-16T15:15:00Z", "2026-10-16T19:00:00Z"),  # T3 wallclock
    ("2026-10-17T10:00:00Z", 1, 2, "2026-10-19T07:00:00Z", "2026-10-19T14:00:00Z"),  # T4 tie rule
    ("2027-01-14T14:30:00Z", 3, 3, "2027-01-15T14:30:00Z", "2027-01-27T14:30:00Z"),  # T5
    ("2027-01-15T15:50:00Z", 1, 1, "2027-01-15T16:05:00Z", "2027-01-15T19:50:00Z"),  # T6 wallclock
    ("2026-10-14T10:00:00Z", 1, 2, "2026-10-14T11:00:00Z", "2026-10-15T10:00:00Z"),  # T7
    ("2026-10-23T13:00:00Z", 1, 3, "2026-10-26T10:00:00Z", "2026-10-28T14:00:00Z"),  # T8 DST
])
def test_sla_vectors(clock, impact, urgency, ack, resolve):
    t = create(clock, impact=impact, urgency=urgency)
    assert (t["sla"]["ack_due_at"], t["sla"]["resolve_due_at"]) == (ack, resolve)


def test_state_machine_happy_path_and_shortcuts():
    t = create()
    assert call("POST", f"/tickets/{t['id']}/start", None, T1)[0] == 409
    assert call("POST", f"/tickets/{t['id']}/resolve", None, T1)[0] == 409
    t = drive(t, ("ack", "2026-10-14T10:05:00Z"))
    assert t["acknowledged_at"] == "2026-10-14T10:05:00Z"
    assert call("POST", f"/tickets/{t['id']}/ack", None, T1)[0] == 409
    assert call("POST", f"/tickets/{t['id']}/resolve", None, T1)[0] == 409
    t = drive(t, ("start", T1), ("resolve", "2026-10-14T11:00:00Z"), ("close", "2026-10-14T12:00:00Z"))
    assert t["state"] == "closed" and t["closed_at"] == "2026-10-14T12:00:00Z"


def test_reopen_window_and_immutable_closed():
    t = drive(create(), ("ack", T1), ("start", T1), ("resolve", T1))
    assert call("POST", f"/tickets/{t['id']}/reopen", None, "2026-10-21T10:00:01Z")[0] == 409
    t2 = drive(create(), ("ack", T1), ("start", T1), ("resolve", T1))
    assert drive(t2, ("reopen", "2026-10-20T10:00:00Z"))["state"] == "in_progress"
    t3 = drive(create(), ("ack", T1), ("start", T1), ("resolve", T1), ("close", T1))
    assert call("POST", f"/tickets/{t3['id']}/reopen", None, "2026-10-15T10:00:00Z")[0] == 409


def test_breach_and_pause():
    t = create("2026-10-16T13:30:00Z", impact=1, urgency=3)
    sla = call("GET", f"/tickets/{t['id']}/sla", None, "2026-10-19T09:31:00Z")[1]
    assert sla["ack_breached"] is True and sla["resolve_breached"] is False
    assert call("GET", f"/tickets/{t['id']}/sla", None, "2026-10-19T09:30:00Z")[1]["ack_breached"] is False
    assert call("GET", f"/tickets/{t['id']}/sla", None, "2026-10-17T10:00:00Z")[1]["paused"] is True
    assert call("GET", f"/tickets/{t['id']}/sla", None, "2026-10-19T09:00:00Z")[1]["paused"] is False


def test_list_filters():
    p1, p4 = create(impact=1, urgency=1), create(impact=3, urgency=3)
    ids = [t["id"] for t in call("GET", "/tickets?priority=P1")[1]]
    assert p1["id"] in ids and p4["id"] not in ids
