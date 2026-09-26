---
feature: "GET /dora/ticket-events - the ticket lifecycle stream of METRIC-SPEC.md section 7"
predicted_minutes: 50
predicted_at: "2026-09-26T13:32:00Z"
feature_path: src/svcdesk/ticket_events.py
---
<!-- ai-generated: 30% - Claude drafted the wording; the estimate is mine -->

# Prediction (Lab 2, Stretch 1: METR n=1)

I predict that building `GET /dora/ticket-events` will take me 50 minutes (my gut range was 30-45 minutes; I padded it deliberately rather than bet on the optimistic end),
working the way I normally do: with Claude writing most of the code and me reviewing, running the checker and
committing. The clock starts when this prediction is receipted and stops when `verify 2` passes the
ticket-events check (L2-CORE-2.12) with the feature committed.

The feature lives in `src/svcdesk/ticket_events.py`; no commit touching that path exists before the receipt.
