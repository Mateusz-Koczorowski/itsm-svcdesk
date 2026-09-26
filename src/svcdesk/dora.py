# ai-generated: 90% - Claude wrote the metric engine from METRIC-SPEC.md R-01..R-17; checked against the practice fixture
"""DORA delivery metrics over a JSONL event log (METRIC-SPEC.md sections 1-6).

A pure function: `compute(body)` takes the request body and returns the response object, or raises
`LogError` for a request the specification says must be rejected (400/422).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from itertools import combinations

SPEC_VERSION = "1.0.0"


class LogError(ValueError):
    """The request or the log is malformed (METRIC-SPEC.md sections 1 and 6)."""


# ---------- parsing helpers ----------

def _instant(value: object, what: str) -> datetime:
    from svcdesk.main import parse_instant  # one RFC 3339 parser for the whole service

    if not isinstance(value, str):
        raise LogError(f"{what} must be an RFC 3339 instant")
    try:
        return parse_instant(value)
    except ValueError:
        raise LogError(f"{what} is not an RFC 3339 instant with an offset: {value!r}")


def _fmt(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _str(event: dict, field: str, nullable: bool = False) -> str | None:
    value = event.get(field)
    if value is None and nullable and field in event:
        return None
    if not isinstance(value, str) or not value:
        raise LogError(f"event {event.get('event_id')!r}: {field} must be a non-empty string")
    return value


def _str_list(event: dict, field: str) -> list[str]:
    value = event.get(field)
    if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
        raise LogError(f"event {event.get('event_id')!r}: {field} must be an array of strings")
    return value


# ---------- rounding (R-03, R-04) ----------

def _round_seconds(value: float | Decimal) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _round_rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    ratio = Decimal(numerator) / Decimal(denominator)
    return float(ratio.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return _round_seconds(ordered[mid])
    return _round_seconds((Decimal(ordered[mid - 1]) + Decimal(ordered[mid])) / 2)


def _seconds(later: datetime, earlier: datetime) -> tuple[int, bool]:
    """Whole seconds between two instants, clamped at zero (R-03). Returns (seconds, was_clamped)."""
    delta = Decimal(str((later - earlier).total_seconds()))
    if delta < 0:
        return 0, True
    return _round_seconds(delta), False


# ---------- the log ----------

def _parse_events(raw_events: list) -> tuple[dict, list, dict]:
    """Validate and index the log. Returns (commits by sha, deployments, incidents by id)."""
    seen_ids: set[str] = set()
    commits: dict[str, dict] = {}
    deployments: list[dict] = []
    incidents: dict[str, dict] = {}

    for event in raw_events:
        if not isinstance(event, dict):
            raise LogError("every event must be a JSON object")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 64:
            raise LogError("every event needs an event_id of 1..64 characters")
        if event_id in seen_ids:
            continue  # R-05: the first occurrence wins, later ones are ignored
        seen_ids.add(event_id)

        kind = event.get("type")
        at = _instant(event.get("at"), f"event {event_id!r}: at")

        if kind == "commit":
            sha = _str(event, "sha")
            _str(event, "branch")
            change_id = _str(event, "change_id", nullable=True)
            reverts = _str(event, "reverts", nullable=True)
            if (change_id is None) == (reverts is None):
                raise LogError(f"commit {sha!r}: change_id must be set exactly when reverts is null")
            if sha in commits:
                raise LogError(f"sha {sha!r} appears twice")
            commits[sha] = {"sha": sha, "at": at, "branch": event["branch"],
                            "change_id": change_id, "reverts": reverts}
        elif kind == "deployment":
            outcome = event.get("outcome")
            if outcome not in ("success", "failure"):
                raise LogError(f"deployment {event_id!r}: outcome must be success or failure")
            unplanned = event.get("unplanned")
            if not isinstance(unplanned, bool):
                raise LogError(f"deployment {event_id!r}: unplanned must be a boolean")
            deployments.append({
                "id": _str(event, "deployment_id"),
                "at": at,
                "environment": _str(event, "environment"),
                "outcome": outcome,
                "commits": _str_list(event, "commits"),
                "unplanned": unplanned,
                "caused_by": _str(event, "caused_by", nullable=True),
            })
        elif kind == "incident":
            incident_id = _str(event, "incident_id")
            phase = event.get("phase")
            if phase not in ("opened", "resolved"):
                raise LogError(f"incident {incident_id!r}: phase must be opened or resolved")
            record = incidents.setdefault(incident_id, {"id": incident_id, "opened": None, "resolved": None,
                                                        "deployments": set()})
            if record[phase] is not None:
                raise LogError(f"incident {incident_id!r} has two {phase} events")
            record[phase] = at
            record["deployments"].update(_str_list(event, "deployments"))
        else:
            raise LogError(f"event {event_id!r}: type must be commit, deployment or incident")

    # Well-formedness: every reference resolves (METRIC-SPEC.md section 1).
    deployment_ids = {d["id"] for d in deployments}
    for commit in commits.values():
        if commit["reverts"] is not None and commit["reverts"] not in commits:
            raise LogError(f"commit {commit['sha']!r} reverts an unknown sha {commit['reverts']!r}")
    for deployment in deployments:
        for sha in deployment["commits"]:
            if sha not in commits:
                raise LogError(f"deployment {deployment['id']!r} carries an unknown sha {sha!r}")
        if deployment["caused_by"] is not None and deployment["caused_by"] not in incidents:
            raise LogError(f"deployment {deployment['id']!r} is caused_by an unknown incident")
    for incident in incidents.values():
        if incident["opened"] is None:
            raise LogError(f"incident {incident['id']!r} resolved without being opened")
        for deployment_id in incident["deployments"]:
            if deployment_id not in deployment_ids:
                raise LogError(f"incident {incident['id']!r} names an unknown deployment {deployment_id!r}")

    return commits, deployments, incidents


def _change_of(sha: str, commits: dict, cache: dict) -> str:
    """R-06: a revert inherits, transitively, the change_id of the commit it reverts."""
    if sha in cache:
        return cache[sha]
    path, current = [], sha
    while commits[current]["change_id"] is None:
        path.append(current)
        current = commits[current]["reverts"]
        if current in path or len(path) > len(commits):
            raise LogError(f"revert cycle through sha {sha!r}")
    change = commits[current]["change_id"]
    for item in path + [current]:
        cache[item] = change
    return change


# ---------- the endpoint ----------

def compute(body: object) -> dict:
    if not isinstance(body, dict):
        raise LogError("the body must be a JSON object")
    window = body.get("window")
    if not isinstance(window, dict):
        raise LogError("window is required")
    start = _instant(window.get("from"), "window.from")
    end = _instant(window.get("to"), "window.to")
    if end <= start:
        raise LogError("window.to must be after window.from")
    raw_events = body.get("events")
    if not isinstance(raw_events, list):
        raise LogError("events must be an array")

    commits, all_deployments, incidents = _parse_events(raw_events)
    change_cache: dict[str, str] = {}

    # R-01, R-02: production deployments inside [from, to); order for "first" is (at, deployment_id).
    deployments = sorted(
        (d for d in all_deployments if d["environment"] == "production" and start <= d["at"] < end),
        key=lambda d: (d["at"], d["id"]),
    )
    successes = [d for d in deployments if d["outcome"] == "success"]
    failures = [d for d in deployments if d["outcome"] == "failure"]

    # R-08, R-09, R-10: one lead-time pair per commit, at its first successful deployment; clamp and count.
    lead_times, negative_pairs, paired = [], 0, set()
    for deployment in successes:
        for sha in deployment["commits"]:
            if sha in paired:
                continue
            paired.add(sha)
            seconds, clamped = _seconds(deployment["at"], commits[sha]["at"])
            lead_times.append(seconds)
            negative_pairs += clamped

    off_main = {sha for d in deployments for sha in d["commits"] if commits[sha]["branch"] != "main"}
    without_commits = sum(1 for d in deployments if not d["commits"])

    # R-12, R-13: recovery per failed deployment via its covering incident (earliest opened, then lowest id).
    recoveries, open_failures = [], 0
    for deployment in failures:
        covering = [i for i in incidents.values() if deployment["id"] in i["deployments"]]
        if not covering:
            open_failures += 1
            continue
        first = min(covering, key=lambda i: (i["opened"], i["id"].encode()))
        if first["resolved"] is None:
            open_failures += 1
            continue
        recoveries.append(_seconds(first["resolved"], deployment["at"])[0])

    intervals = [(i["opened"], i["resolved"] if i["resolved"] is not None else end) for i in incidents.values()]
    overlapping = sum(1 for a, b in combinations(intervals, 2) if a[0] < b[1] and b[0] < a[1])

    rework = sum(1 for d in deployments if d["unplanned"] and d["caused_by"] is not None)

    # R-06, R-07: changes and their first commit instants, over the whole log.
    first_commit: dict[str, datetime] = {}
    for sha, commit in commits.items():
        change = _change_of(sha, commits, change_cache)
        if change not in first_commit or commit["at"] < first_commit[change]:
            first_commit[change] = commit["at"]

    # R-16, R-17: ground truth over changes delivered on a successful deployment in the window.
    first_delivery: dict[str, datetime] = {}
    for deployment in successes:
        for sha in deployment["commits"]:
            first_delivery.setdefault(_change_of(sha, commits, change_cache), deployment["at"])
    true_lead_times = [_seconds(at, first_commit[change])[0] for change, at in first_delivery.items()]

    days = Decimal(str((end - start).total_seconds())) / Decimal(86400)
    frequency = float((Decimal(len(deployments)) / days).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))

    return {
        "spec_version": SPEC_VERSION,
        "window": {"from": _fmt(start), "to": _fmt(end)},
        "deployment_frequency_per_day": frequency,
        "change_lead_time_seconds_p50": _median(lead_times),
        "failed_deployment_recovery_time_seconds_p50": _median(recoveries),
        "change_fail_rate": _round_rate(len(failures), len(deployments)),
        "deployment_rework_rate": _round_rate(rework, len(deployments)),
        "counts": {
            "deployments": len(deployments),
            "successful_deployments": len(successes),
            "failed_deployments": len(failures),
            "recovered_failures": len(recoveries),
            "open_failures": open_failures,
            "rework_deployments": rework,
            "lead_time_pairs": len(lead_times),
            "changes": len(first_commit),
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_pairs,
            "deployments_without_commits": without_commits,
            "commits_never_on_main": len(off_main),
            "revert_chains_collapsed": sum(1 for c in commits.values() if c["reverts"] is not None),
            "overlapping_incident_pairs": overlapping,
        },
        "ground_truth": {
            "changes_delivered": len(first_delivery),
            "true_change_lead_time_seconds_p50": _median(true_lead_times),
        },
    }
