<!-- ai-generated: 80% - Claude drafted from REQUIREMENTS.md and API.md; conflict resolutions chosen by me -->
# Feature specification: svcdesk v1 (Lab 1)

Status: frozen for the specs receipt, before any code under `src/`.
Sources: REQUIREMENTS.md (R-01..R-25) and API.md (the enforced contract). Where they differ in precision,
API.md wins (as REQUIREMENTS.md itself states).

## 1. Scope

A small HTTP/JSON service desk API for an internal IT desk (about 400 people, three offices). It computes
ticket priority, runs a ticket state machine, keeps two SLA clocks and reports breach and pause, so that the
Monday report can be produced with one call per ticket. Out of scope for v1: authentication, pagination,
validation of `related_to`, public holidays, notifications.

## 2. Conflict resolutions (decided before building)

REQUIREMENTS.md contains three pairs that cannot both hold. Each is resolved by rejecting the minimal
conflicting part of one requirement; everything else in the pair is kept and implemented.

| id | pair | resolution | rejected part |
|---|---|---|---|
| C1 | R-13 (all SLA clocks pause outside business hours) vs R-14 (P1 runs around the clock) | `wallclock` | R-13 does not apply to P1. Both P1 targets (ack 15 min, resolve 4 h) are wall-clock; P2..P4 stay on the business-hours clock. A P1 is never `paused`. |
| C2 | R-09 (a closed ticket is immutable) vs R-10 (reopen a resolved *or closed* ticket within 7 days) | `immutable` | "or closed" in R-10. Reopen works from `resolved` within 7 days of `resolved_at`; a `closed` ticket always answers 409 and further work goes into a new ticket with `related_to`. |
| C3 | R-05 (priority from the matrix and nothing else) vs R-06 (VIP never lower than P2) | `matrix` | R-06. `reporter.vip` is stored and returned but never changes the priority. |

The reasoning (service owner, customer outcome, what we give up) is in `DECISIONS.md`.

## 3. Interface (API.md §1)

| method and path | success | errors |
|---|---|---|
| `GET /health` | 200 `{"status":"ok","service":"svcdesk"}` | - |
| `POST /tickets` | 201 Ticket | 400/422 `{"error":{...}}` on validation |
| `GET /tickets` | 200 `[Ticket]`, optional exact filters `state`, `priority`, no pagination | - |
| `GET /tickets/{id}` | 200 Ticket | 404 `{"error":{...}}` |
| `GET /tickets/{id}/sla` | 200 SLA report (§7) | 404 |
| `POST /tickets/{id}/ack\|start\|resolve\|close\|reopen` | 200 Ticket | 409 invalid transition, 404 unknown id |
| any unknown path | 404 JSON body | wrong method on known path: 404 or 405 |

All bodies are `application/json` (R-01). Every error body has a top-level `error` object with `code` and
`message` (`validation`, `not_found`, `invalid_transition`, `reopen_window_expired`, `ticket_closed`).

## 4. Ticket model and validation (R-03, R-17, R-18, R-20, API.md §2, §7)

- `id`: opaque UUID assigned by the service (R-18).
- `title` required, 1..200 chars; `description` optional, 0..4000, default `""`.
- `reporter.name` required, 1..100; `reporter.email` optional (default null); `reporter.vip` optional bool
  (default false).
- `impact`, `urgency` required integers 1..3; strings (`"high"`), booleans and out-of-range values are 422.
- `related_to` optional string or null, stored, not validated.
- Server-owned fields in the request (`id`, `priority`, `state`, timestamps, `sla`) and unknown fields are
  silently ignored, never an error (R-20).
- Response adds `priority`, `state`, `created_at`, `acknowledged_at`, `resolved_at`, `closed_at` (null until
  the event), and `sla: {ack_due_at, resolve_due_at}`. All instants are UTC with a `Z` suffix (R-17).

## 5. Priority (R-04, R-05, C3 = matrix)

| impact \ urgency | 1 | 2 | 3 |
|---|---|---|---|
| 1 | P1 | P2 | P3 |
| 2 | P2 | P3 | P4 |
| 3 | P3 | P4 | P4 |

Priority is computed once, at creation, from this matrix only. A `priority` in the body is ignored; VIP does
not change it (impact 3, urgency 3, vip true is P4).

## 6. SLA targets and clocks (R-12, R-13, R-14, C1 = wallclock; API.md §4)

| priority | ack within | resolve within | clock |
|---|---|---|---|
| P1 | 15 min | 4 h | wall-clock: `created_at + target` |
| P2 | 1 h | 8 h | business hours |
| P3 | 4 h | 24 h | business hours |
| P4 | 8 h | 72 h | business hours |

Business hours: Monday to Friday, half-open window [08:00, 16:00) in `Europe/Warsaw`, DST-aware, holidays are
business days. Algorithm: convert `created_at` to Europe/Warsaw; if outside a window, move to the next opening;
consume the target from consecutive windows; a target that ends exactly at 16:00 is due at 16:00 that day (tie
rule); convert back to UTC. Due instants are fixed at creation and never change (reopen does not extend them,
R-11). The implementation must reproduce every vector T1..T8 of API.md §4 exactly, using the wall-clock columns
for P1 (T3: ack 2026-10-16T15:15:00Z, resolve 2026-10-16T19:00:00Z; T6: 2027-01-15T16:05:00Z, 2027-01-15T19:50:00Z).

## 7. Breach and pause (R-15, R-16; API.md §5)

`GET /tickets/{id}/sla` returns `{priority, ack_due_at, resolve_due_at, ack_breached, resolve_breached, paused}`
evaluated at `now`:

- `ack_breached`: not acknowledged and `now > ack_due_at`, or `acknowledged_at > ack_due_at`. Equality is not
  a breach.
- `resolve_breached`: not resolved and `now > resolve_due_at`, or `resolved_at > resolve_due_at`. A reopened
  ticket is not resolved again, against the original `resolve_due_at`.
- `paused`: state is not `resolved`/`closed`, the resolve target is on the business-hours clock (P2..P4), and
  `now` is outside a business window. Always false for P1 (C1 = wallclock).

## 8. State machine (R-07, R-08, R-10, R-11, C2 = immutable; API.md §6)

| action | from | to | side effect |
|---|---|---|---|
| ack | new | acknowledged | `acknowledged_at = now` |
| start | acknowledged | in_progress | - |
| resolve | in_progress | resolved | `resolved_at = now` |
| close | resolved | closed | `closed_at = now` |
| reopen | resolved, and `now <= resolved_at + 7 days` | in_progress | clears `resolved_at` (and `closed_at`) |

Everything else is 409 with `error.code = invalid_transition` (no shortcuts). Reopen of a resolved ticket
after 7 days is 409 `reopen_window_expired`. Reopen of a closed ticket is 409 `ticket_closed` regardless of
age (C2). Unknown id is 404.

## 9. Test clock (R-21; API.md §8)

When `SVCDESK_TEST_CLOCK` is `1` or `true`, the `X-Test-Clock` header (RFC 3339 with an offset) is `now` for
that request only: it sets created/ack/resolve/close timestamps and is the reference for breach, pause and the
reopen window. It is never compared across requests and never checked for monotonicity. A header that does not
parse, or a naive timestamp, is 422. Without the header, `now` is real UTC. With the variable unset or `0`,
the header is ignored.

## 10. Runtime and packaging (R-22, R-23, R-24; API.md §9, §10)

- Python 3.13, FastAPI, uvicorn; image built from `python:3.13-slim` (has tzdata for Europe/Warsaw); all
  dependencies installed at build time, no network at run time.
- Compose service `svcdesk` with `build: .`, port 8080 in the container, `SVCDESK_TEST_CLOCK: "1"`, a named
  volume at `/data` for a SQLite file so tickets survive a restart; no bind mounts.
- `/health` answers within 120 s of `docker compose up`.

## 11. Acceptance

Done when `itsmlab verify 1` reports L1-CORE-1..4 as pass (L1-CORE-5 skip locally) with the observation line
`C1=wallclock C2=immutable C3=matrix`, and `DECISIONS.md` declares the same values.
