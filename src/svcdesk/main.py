# ai-generated: 90% - Claude drafted from specs/001-svcdesk/spec.md; I chose C1/C2/C3 and reviewed the state machine
"""svcdesk HTTP API (API.md sections 1, 2, 5, 6, 7, 8)."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from svcdesk import sla
from svcdesk.store import default_store

app = FastAPI(title="svcdesk", docs_url=None, redoc_url=None, openapi_url=None)
store = default_store()

REOPEN_WINDOW = timedelta(days=7)
STATES = ("new", "acknowledged", "in_progress", "resolved", "closed")
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return error(exc.status, exc.code, exc.message)


@app.exception_handler(StarletteHTTPException)
async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return error(exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error(422, "validation", "invalid request")


# ---------- time ----------

def fmt(instant: datetime | None) -> str | None:
    if instant is None:
        return None
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_instant(value: str) -> datetime:
    if not RFC3339.match(value):
        raise ValueError(value)
    parsed = datetime.fromisoformat(value.replace("z", "Z").replace("t", "T").replace(" ", "T"))
    if parsed.tzinfo is None:
        raise ValueError(value)
    return parsed.astimezone(timezone.utc)


def test_clock_enabled() -> bool:
    return os.environ.get("SVCDESK_TEST_CLOCK", "").strip().lower() in ("1", "true")


def now_for(request: Request) -> datetime:
    """`now` for this request only (R-21, API.md section 8)."""
    header = request.headers.get("x-test-clock")
    if header is not None and test_clock_enabled():
        try:
            return parse_instant(header.strip())
        except ValueError:
            raise ApiError(422, "validation", "X-Test-Clock is not an RFC 3339 instant with an offset")
    return datetime.now(timezone.utc)


# ---------- validation ----------

def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_create(body: object) -> dict:
    """Checks R-03 / API.md section 7; server-owned and unknown fields are ignored (R-20)."""
    if not isinstance(body, dict):
        raise ApiError(422, "validation", "body must be a JSON object")

    title = body.get("title")
    if not isinstance(title, str) or not 1 <= len(title) <= 200:
        raise ApiError(422, "validation", "title is required, 1..200 characters")

    description = body.get("description")
    if description is None:
        description = ""
    if not isinstance(description, str) or len(description) > 4000:
        raise ApiError(422, "validation", "description must be a string of at most 4000 characters")

    reporter = body.get("reporter")
    if not isinstance(reporter, dict):
        raise ApiError(422, "validation", "reporter is required")
    name = reporter.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 100:
        raise ApiError(422, "validation", "reporter.name is required, 1..100 characters")
    email = reporter.get("email")
    if email is not None and not isinstance(email, str):
        raise ApiError(422, "validation", "reporter.email must be a string or null")
    vip = reporter.get("vip", False)
    if vip is None:
        vip = False
    if not isinstance(vip, bool):
        raise ApiError(422, "validation", "reporter.vip must be a boolean")

    levels = {}
    for field in ("impact", "urgency"):
        value = body.get(field)
        if not _is_int(value) or not 1 <= value <= 3:
            raise ApiError(422, "validation", f"{field} is required, an integer 1..3")
        levels[field] = value

    related_to = body.get("related_to")
    if related_to is not None and not isinstance(related_to, str):
        raise ApiError(422, "validation", "related_to must be a string or null")

    return {
        "title": title,
        "description": description,
        "reporter": {"name": name, "email": email, "vip": vip},
        "impact": levels["impact"],
        "urgency": levels["urgency"],
        "related_to": related_to,
    }


# ---------- helpers ----------

def load(ticket_id: str) -> dict:
    ticket = store.get(ticket_id)
    if ticket is None:
        raise ApiError(404, "not_found", f"ticket {ticket_id} does not exist")
    return ticket


def ts(ticket: dict, field: str) -> datetime | None:
    value = ticket.get(field)
    return parse_instant(value) if value else None


def invalid_transition(ticket: dict, action: str) -> ApiError:
    return ApiError(409, "invalid_transition", f"cannot {action} a ticket in state {ticket['state']}")


# ---------- endpoints ----------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "svcdesk"}


@app.post("/tickets", status_code=201)
async def create_ticket(request: Request) -> JSONResponse:
    now = now_for(request)
    try:
        body = await request.json()
    except Exception:
        raise ApiError(422, "validation", "body must be valid JSON")
    fields = validate_create(body)
    priority = sla.priority_for(fields["impact"], fields["urgency"])  # C3 = matrix: vip ignored
    ack_due, resolve_due = sla.due_instants(priority, now)
    ticket = {
        "id": str(uuid.uuid4()),
        **fields,
        "priority": priority,
        "state": "new",
        "created_at": fmt(now),
        "acknowledged_at": None,
        "resolved_at": None,
        "closed_at": None,
        "sla": {"ack_due_at": fmt(ack_due), "resolve_due_at": fmt(resolve_due)},
    }
    store.insert(ticket)
    return JSONResponse(status_code=201, content=ticket)


@app.get("/tickets")
def list_tickets(state: str | None = None, priority: str | None = None) -> list[dict]:
    tickets = store.all()
    if state is not None:
        tickets = [t for t in tickets if t["state"] == state]
    if priority is not None:
        tickets = [t for t in tickets if t["priority"] == priority]
    return tickets


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> dict:
    return load(ticket_id)


@app.get("/tickets/{ticket_id}/sla")
def get_sla(ticket_id: str, request: Request) -> dict:
    ticket = load(ticket_id)
    now = now_for(request)
    ack_due = parse_instant(ticket["sla"]["ack_due_at"])
    resolve_due = parse_instant(ticket["sla"]["resolve_due_at"])
    acknowledged_at = ts(ticket, "acknowledged_at")
    resolved_at = ts(ticket, "resolved_at")
    is_open = ticket["state"] not in ("resolved", "closed")

    ack_breached = acknowledged_at > ack_due if acknowledged_at else now > ack_due
    resolve_breached = resolved_at > resolve_due if resolved_at else now > resolve_due
    paused = is_open and sla.uses_business_clock(ticket["priority"]) and not sla.is_business_time(now)

    return {
        "priority": ticket["priority"],
        "ack_due_at": ticket["sla"]["ack_due_at"],
        "resolve_due_at": ticket["sla"]["resolve_due_at"],
        "ack_breached": ack_breached,
        "resolve_breached": resolve_breached,
        "paused": paused,
    }


@app.post("/tickets/{ticket_id}/ack")
def ack(ticket_id: str, request: Request) -> dict:
    ticket = load(ticket_id)
    now = now_for(request)
    if ticket["state"] != "new":
        raise invalid_transition(ticket, "acknowledge")
    ticket["state"] = "acknowledged"
    ticket["acknowledged_at"] = fmt(now)
    store.update(ticket)
    return ticket


@app.post("/tickets/{ticket_id}/start")
def start(ticket_id: str, request: Request) -> dict:
    ticket = load(ticket_id)
    now_for(request)
    if ticket["state"] != "acknowledged":
        raise invalid_transition(ticket, "start")
    ticket["state"] = "in_progress"
    store.update(ticket)
    return ticket


@app.post("/tickets/{ticket_id}/resolve")
def resolve(ticket_id: str, request: Request) -> dict:
    ticket = load(ticket_id)
    now = now_for(request)
    if ticket["state"] != "in_progress":
        raise invalid_transition(ticket, "resolve")
    ticket["state"] = "resolved"
    ticket["resolved_at"] = fmt(now)
    store.update(ticket)
    return ticket


@app.post("/tickets/{ticket_id}/close")
def close(ticket_id: str, request: Request) -> dict:
    ticket = load(ticket_id)
    now = now_for(request)
    if ticket["state"] != "resolved":
        raise invalid_transition(ticket, "close")
    ticket["state"] = "closed"
    ticket["closed_at"] = fmt(now)
    store.update(ticket)
    return ticket


@app.post("/tickets/{ticket_id}/reopen")
def reopen(ticket_id: str, request: Request) -> dict:
    ticket = load(ticket_id)
    now = now_for(request)
    if ticket["state"] == "closed":
        # C2 = immutable: a closed ticket is never reopened (R-09 kept, "or closed" of R-10 rejected).
        raise ApiError(409, "ticket_closed", "a closed ticket is immutable; open a new ticket with related_to")
    if ticket["state"] != "resolved":
        raise invalid_transition(ticket, "reopen")
    resolved_at = ts(ticket, "resolved_at")
    if resolved_at is None or now > resolved_at + REOPEN_WINDOW:
        raise ApiError(409, "reopen_window_expired", "the 7-day reopen window has passed")
    ticket["state"] = "in_progress"
    ticket["resolved_at"] = None
    ticket["closed_at"] = None
    store.update(ticket)
    return ticket
