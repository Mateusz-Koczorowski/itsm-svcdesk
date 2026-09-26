# ai-generated: 90% - Claude drafted the business-hours clock from API.md section 4; decisions (C1) are mine
"""Priority matrix and SLA clocks (API.md sections 3 and 4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
OPEN_HOUR = 8
CLOSE_HOUR = 16

# C3 = matrix: priority comes from impact x urgency only; reporter.vip never changes it (R-05 kept, R-06 rejected).
MATRIX = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}

# (acknowledge within, resolve within) per priority (R-12).
TARGETS = {
    "P1": (timedelta(minutes=15), timedelta(hours=4)),
    "P2": (timedelta(hours=1), timedelta(hours=8)),
    "P3": (timedelta(hours=4), timedelta(hours=24)),
    "P4": (timedelta(hours=8), timedelta(hours=72)),
}

# C1 = wallclock: P1 targets run around the clock (R-14 kept, R-13 not applied to P1).
WALLCLOCK_PRIORITIES = {"P1"}


def priority_for(impact: int, urgency: int) -> str:
    return MATRIX[(impact, urgency)]


def uses_business_clock(priority: str) -> bool:
    return priority not in WALLCLOCK_PRIORITIES


def is_business_time(instant: datetime) -> bool:
    """True when the instant falls inside [08:00, 16:00) Monday..Friday, Europe/Warsaw."""
    local = instant.astimezone(WARSAW)
    return local.weekday() < 5 and OPEN_HOUR <= local.hour < CLOSE_HOUR


def _next_opening(local: datetime) -> datetime:
    """08:00 of the next business day strictly after the given local date (naive local time)."""
    day = (local + timedelta(days=1)).replace(hour=OPEN_HOUR, minute=0, second=0, microsecond=0)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def add_business_time(start: datetime, target: timedelta) -> datetime:
    """Consume `target` from consecutive business windows, starting at `start` (API.md section 4).

    Works on naive Europe/Warsaw wall time: DST transitions fall on Sundays at night, never inside a window,
    so wall-time arithmetic inside a window equals elapsed time. A target that ends exactly at 16:00 is due at
    16:00 that day (the tie rule).
    """
    local = start.astimezone(WARSAW).replace(tzinfo=None)
    remaining = target
    while True:
        if local.weekday() >= 5 or local.hour >= CLOSE_HOUR:
            local = _next_opening(local)
        elif local.hour < OPEN_HOUR:
            local = local.replace(hour=OPEN_HOUR, minute=0, second=0, microsecond=0)
        closing = local.replace(hour=CLOSE_HOUR, minute=0, second=0, microsecond=0)
        available = closing - local
        if remaining <= available:
            due_local = local + remaining
            return due_local.replace(tzinfo=WARSAW).astimezone(timezone.utc)
        remaining -= available
        local = _next_opening(local)


def due_instants(priority: str, created_at: datetime) -> tuple[datetime, datetime]:
    ack, resolve = TARGETS[priority]
    if uses_business_clock(priority):
        return add_business_time(created_at, ack), add_business_time(created_at, resolve)
    return created_at + ack, created_at + resolve
