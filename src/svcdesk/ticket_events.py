# ai-generated: 90% - Claude wrote it from METRIC-SPEC.md section 7; I reviewed it and ran the checker
"""GET /dora/ticket-events: every ticket's lifecycle as a stream of instants (METRIC-SPEC.md section 7)."""

from __future__ import annotations

from datetime import datetime, timezone

# phase -> (timestamp field on the ticket, state at that instant). No in_progress: Lab 1 records no instant for it.
PHASES = (
    ("created", "created_at", "new"),
    ("acknowledged", "acknowledged_at", "acknowledged"),
    ("resolved", "resolved_at", "resolved"),
    ("closed", "closed_at", "closed"),
)


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def stream(tickets: list[dict]) -> list[dict]:
    """One event per lifecycle instant that has occurred, ordered by (at, ticket_id) ascending.

    Within one ticket and one instant the lifecycle order is kept (the sort is stable).
    """
    events = []
    for ticket in tickets:
        for phase, field, state in PHASES:
            value = ticket.get(field)
            if not value:
                continue  # an absent timestamp emits no event
            events.append((_instant(value), ticket["id"], {
                "ticket_id": ticket["id"],
                "at": value,
                "phase": phase,
                "priority": ticket["priority"],
                "state": state,
            }))
    events.sort(key=lambda item: (item[0], item[1]))
    return [event for _, _, event in events]
