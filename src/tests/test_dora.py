# ai-generated: 90% - Claude wrote the cases from METRIC-SPEC.md; I picked the edge cases to cover
"""Own tests for Lab 2: POST /dora/metrics and GET /dora/ticket-events."""

from __future__ import annotations

from tests.client import call, ticket

WINDOW = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}


def commit(n, at, change="CHG-1", reverts=None, branch="main"):
    return {"event_id": f"c-{n}", "type": "commit", "at": at, "sha": f"sha-{n}", "branch": branch,
            "change_id": None if reverts else change, "reverts": reverts}


def deploy(n, at, commits, outcome="success", unplanned=False, caused_by=None):
    return {"event_id": f"d-{n}", "type": "deployment", "at": at, "deployment_id": f"DEP-{n}",
            "environment": "production", "outcome": outcome, "commits": commits,
            "unplanned": unplanned, "caused_by": caused_by}


def metrics(events, window=WINDOW):
    return call("POST", "/dora/metrics", {"window": window, "events": events})


def test_empty_log():
    status, body = metrics([])
    assert status == 200 and body["deployment_frequency_per_day"] == 0.0
    assert body["change_lead_time_seconds_p50"] is None and body["change_fail_rate"] is None


def test_rejections():
    assert metrics([], {"from": WINDOW["to"], "to": WINDOW["from"]})[0] in (400, 422)
    assert call("POST", "/dora/metrics", {"events": []})[0] in (400, 422)
    assert call("POST", "/dora/metrics", {"window": WINDOW})[0] in (400, 422)
    assert metrics([commit(1, "2026-09-02T00:00:00Z", reverts="sha-missing")])[0] in (400, 422)


def test_e1_negative_lead_time_is_clamped_and_counted():
    body = metrics([commit(1, "2026-09-02T10:05:00Z"), deploy(1, "2026-09-02T10:00:00Z", ["sha-1"])])[1]
    assert body["change_lead_time_seconds_p50"] == 0
    assert body["anomalies"]["negative_lead_time_pairs"] == 1


def test_e2_revert_of_revert_is_one_change():
    events = [commit(1, "2026-09-02T00:00:00Z"), commit(2, "2026-09-03T00:00:00Z", reverts="sha-1"),
              commit(3, "2026-09-04T00:00:00Z", reverts="sha-2")]
    body = metrics(events)[1]
    assert body["counts"]["changes"] == 1 and body["anomalies"]["revert_chains_collapsed"] == 2


def test_e3_e4_hotfix_and_empty_deployment_count():
    events = [commit(1, "2026-09-02T00:00:00Z", branch="hotfix/x"), deploy(1, "2026-09-02T01:00:00Z", ["sha-1"]),
              deploy(2, "2026-09-03T00:00:00Z", [], outcome="failure")]
    body = metrics(events)[1]
    assert body["anomalies"]["commits_never_on_main"] == 1
    assert body["anomalies"]["deployments_without_commits"] == 1
    assert body["counts"]["lead_time_pairs"] == 1 and body["change_fail_rate"] == 0.5
    assert body["counts"]["open_failures"] == 1  # E5: failed, no incident covers it


def test_order_and_duplicates_do_not_matter():
    events = [commit(1, "2026-09-02T00:00:00Z"), deploy(1, "2026-09-02T02:00:00Z", ["sha-1"])]
    first = metrics(events)[1]
    assert metrics(events[::-1])[1] == first
    assert metrics(events + events)[1] == first


def test_ticket_events_stream():
    status, created = call("POST", "/tickets", ticket(), "2026-10-14T10:00:00Z")
    assert status == 201
    for action in ("ack", "start", "resolve"):
        assert call("POST", f"/tickets/{created['id']}/{action}", None, "2026-10-14T11:00:00Z")[0] == 200
    stream = call("GET", "/dora/ticket-events")[1]
    phases = [e["phase"] for e in stream if e["ticket_id"] == created["id"]]
    assert phases == ["created", "acknowledged", "resolved"]
    keys = [(e["at"], e["ticket_id"]) for e in stream]
    assert keys == sorted(keys)
