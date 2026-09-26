---
actual_minutes: 29
predicted_minutes: 50
ratio_actual_over_predicted: 0.58
---
<!-- ai-generated: 70% - Claude drafted from my prediction receipt and the git history; the numbers are mine -->

# METR n=1 replication (Lab 2, Stretch 1)

- Feature: `GET /dora/ticket-events` (METRIC-SPEC.md section 7), in `src/svcdesk/ticket_events.py`.
- Prediction: 50 minutes, receipted at 2026-09-26T13:34:05Z (issue #123).
- Actual: 29 minutes, measured as elapsed time from the prediction receipt to the commit that shipped the
  feature (2026-09-26T14:03:27Z), which is the stopping rule written in PREDICTION.md.
- Ratio actual/predicted: 29/50 = **0.58**.

## What happened

My gut estimate was 30 to 45 minutes and I deliberately padded it to 50, because I did not want to bet on the
optimistic end. The outcome came in well under the prediction. The feature was small and fully specified:
METRIC-SPEC.md section 7 fixes the shape, the ordering and the mapping from timestamps to phases, and the
checker has one published check for it (L2-CORE-2.12). Claude wrote the code; my part was
running `verify 2` and committing. The first checker run already passed 2.12, so there was no debugging loop.

## What this does and does not say

This is one task, one person, and a task chosen to be easy to specify, so it says nothing general about AI
productivity. It is also the opposite setting from the METR study: there, experienced developers worked on
large, unfamiliar-to-the-model codebases with implicit requirements, and the verification cost ate the time the
assistant saved. Here the requirements were explicit and machine-checked, which is exactly where an assistant
is cheapest to verify. The more interesting number is my padding: I predicted almost twice the time I needed,
which suggests I discount AI help by default rather than overrate it.
