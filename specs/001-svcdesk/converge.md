<!-- ai-generated: 80% - Claude compared the spec with the built service and the checker run; reviewed by me -->
# Converge report: spec.md vs the built svcdesk

Compared `specs/001-svcdesk/spec.md` (receipted before any code) with the implementation in `src/svcdesk/`
and a local `itsmlab verify 1` run (Core pass, observations C1=wallclock C2=immutable C3=matrix).

| requirement | spec says | built | status |
|---|---|---|---|
| R-02 | `/health` 200 with status ok | `main.health` | converged |
| R-04, R-05 | priority from the matrix only | `sla.MATRIX`, computed once at create | converged |
| R-06 | VIP never below P2 | rejected by C3 = matrix; vip stored, ignored | converged (by decision) |
| R-07, R-08 | five states, one endpoint per action, 409 otherwise | one handler per action in `main.py` | converged |
| R-09, R-10, R-11 | closed immutable, reopen from resolved within 7 days | `reopen`: 409 `ticket_closed`, window on `resolved_at` | converged (C2 = immutable) |
| R-12, R-13, R-14 | P1 wall-clock, P2..P4 business hours, tie rule | `sla.due_instants`, `add_business_time` | converged; T1..T8 reproduced |
| R-15, R-16 | breach and pause at `now` | `get_sla`; P1 never paused | converged |
| R-20 | 400/422 with `error`, server-owned fields ignored | `validate_create` builds the ticket from known fields only | converged |
| R-21 | per-request test clock, malformed is 422 | `now_for` | converged |
| R-22, R-23, R-24 | compose, named volume, no network at run time | Dockerfile installs at build, SQLite in `/data` | converged; R-23 not checked in Lab 1 |

Divergences: none found. Open points for Lab 2: `related_to` is stored but not validated (out of scope in
spec section 1); restart persistence (R-23) is implemented but untested by the checker.
