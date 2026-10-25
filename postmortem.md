---
lab4_postmortem:
  ticket: "3ba75e92-1b55-483b-a69e-6097c02b182c"
  detecting_alert: ShopCheckoutSlow
  onset: 2026-10-12T05:01:00Z
  detection: 2026-10-12T05:06:19Z
  acknowledgement: 2026-10-12T05:06:56Z
  recovery: 2026-10-12T05:08:19Z
  mttd_seconds: 319
  mtta_seconds: 37
  mttr_seconds: 439
  identified_flags: [adFailure, intlShippingSlowdown, emailMemoryLeak]
---
<!-- ai-generated: 80% - Claude drafted it from my analysis of the recording's snapshot; the identification and the action items were reviewed by me -->

# Postmortem: orders took up to 9 seconds, and some ads failed, for about nine minutes

## Date

The incident happened on Monday 12 October 2026, from 05:01 to 05:10 UTC, in the course recording lab4-rec-1. This
postmortem was written on 25 October 2026 from that recording's Prometheus snapshot and ticket.

## Authors

Mateusz Koczorowski, writing as the on-call's reviewer on the recorded path: the page, the ticket and the
rollback in the recording were the lecturer's actions; the investigation and the identification of the fault below
are mine, made from the snapshot's metrics alone.

## Status

Complete for the incident: service was restored and the ticket was acknowledged. The problem record stays open, and
the action items are proposed, not done.

## Summary

From 05:01 to about 05:10 UTC some orders in the web shop took 5 to 9 seconds instead of about 50 ms, about one ad
request in ten failed, and the email service ran close to its memory limit. Three feature flags had started failing at
once; the P1 page came after 5 minutes 19 seconds and the flags were switched off by 05:10.

## Impact

Checkout: the p99 of `oteldemo.CheckoutService/PlaceOrder` went from about 50 ms on the baseline to 9.1 s at 05:05
and 8.8 s at 05:07
(`histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{service_name="checkout", span_kind="SPAN_KIND_SERVER", span_name="oteldemo.CheckoutService/PlaceOrder"}[5m])))`).
Traffic is low in the playground, about 64 orders in the 10 minutes to 05:11, and 1 to 2 of them took longer than
2 s (`increase(...PlaceOrder...{le="2000"}[10m])` against the calls counter): the slow ones were the international
orders that the shipping slowdown hits. No order failed: checkout had no error spans at all.
Ads: 7.6 of about 94 GetAds requests failed in the 10 minutes to 05:11, roughly 8 %, with the 5-minute error ratio
peaking at 12 % (`sum(rate(traces_span_metrics_calls_total{service_name="ad", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[5m])) / sum(rate(traces_span_metrics_calls_total{service_name="ad", span_kind="SPAN_KIND_SERVER"}[5m]))`).
The frontend showed it as failed `GET /api/data` calls, under 1 % of its requests. Email: the container's memory rose
from about 60 MB to a peak of 100.5 MB against a 104.9 MB limit
(`max_over_time(container_memory_usage_total_bytes{container_name="email"}[10m])`); it was not killed, so no
confirmation email was lost, but it was one more burst away from an out-of-memory restart.

## Root Causes

Three feature flags failed together, one from each class of the injector's pool. `intlShippingSlowdown` made
shipping's `POST /ship-order` slow for international orders: its p99 went from about 5 ms to 8.2 s at 05:05, and every
such order waited for it inside PlaceOrder, which is why checkout's latency equals shipping's to within 50 ms at
every instant. `adFailure` made the ad service fail part of its GetAds calls (no ad errors at all before the onset).
`emailMemoryLeak` made the email service leak memory on every confirmation email, up to 96 % of its container limit.
What was already wrong underneath: checkout calls ShipOrder synchronously with no timeout below several seconds and
no fallback, so one slow dependency becomes the customer's wait; and a flag change can reach production with nothing
that ties it to a change record.

## Trigger

At 05:01:00 UTC the three flags switched on together (the first sample of `seeded_fault_active`), a change of
configuration and not of code: no deployment happened in the window.

## Resolution

The flags were switched off through the injector, and the fault ended between 05:10:00 and 05:10:05 UTC, when
`seeded_fault_active` fell to 0. The metrics do not show the order in which the three went off, only that shipping's
p99 was back to milliseconds by the 05:09 sample and that the ad errors stopped by 05:10 (the 5-minute ratio decayed
until about 05:14). The detecting alert had already resolved at 05:08:19, because its window slid past the slow orders
before the last flag was off.

## Detection

The P1 alert `ShopCheckoutSlow` (service checkout) started firing at 05:06:19 UTC, 319 seconds after the onset, on
the symptom customers felt: slow checkout. The pager received the page (`itsm_pager_notifications_total{receiver="pager",status="firing"}` rose at about 05:06:33)
and the ticket was acknowledged 37 seconds after detection. Two P2 alerts on the shop started at the same evaluation and went to chat.
My own `CheckoutLatencyHigh` rule (p95 of PlaceOrder above 2 s for 1 minute) would have been true from 05:04:20 and
firing from about 05:05:20, a minute earlier. Without an alert, a customer complaint about slow orders would have been
the first signal; the ad failures and the email memory alone would not have reached a person at all, since neither
pages.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Put a 2-second timeout and an asynchronous fallback on checkout's ShipOrder call, so a slow carrier delays the shipment, not the order | prevent | checkout team | ITSM-101 |
| Alert in chat (P2) when a container stays above 85 % of its memory limit for 5 minutes | mitigate | platform team | ITSM-102 |
| Record every production feature-flag change as a change in svcdesk, and show the last flag changes on the on-call dashboard | process | SRE on-call | ITSM-103 |
| Lower the checkout latency page's `for` to 1 minute and add a P3 on ShipOrder latency, so a slow dependency is visible before checkout pages | mitigate | SRE on-call | ITSM-104 |

## Lessons Learned

### What went well

A symptom alert on checkout latency paged within 5.5 minutes and the on-call acknowledged in 37 seconds. The span
metrics were enough to separate the three faults afterwards: shipping latency, ad errors and email memory each had
their own signal and their own healthy baseline to compare with.

### What went wrong

Nothing tied the incident to its cause: no metric names a flag, so from the metrics alone the cause had to be
inferred service by service. The detecting alert resolved at 05:08:19, two minutes before the flags were off, so
MTTR as the alert measures it understates the fault by almost two minutes. The recorded AI investigator blamed the
product catalog and a checkout-internal span; both were contradicted by the data (ledger H2, H4).

### Where we got lucky

The email service peaked at 100.5 MB of a 104.9 MB limit: a few more leaking emails and it would have been killed
and restarted, losing confirmations. And no order failed outright: the error class of this fault hit ads, not
payment.

## Timeline

All times UTC, 12 October 2026.

- 04:45:05 - the injector starts; the baseline begins. No P1 fires in the ten minutes before the onset.
- 05:01:00 - **onset**: `adFailure`, `intlShippingSlowdown` and `emailMemoryLeak` switch on (first sample of `seeded_fault_active`).
- 05:02:30 - ad error spans appear (my `AdErrorRate` expression first true).
- 05:04:20 - shipping's ShipOrder p99 and checkout's PlaceOrder p95 cross 2 s.
- 05:06:19 - **detection**: `ShopCheckoutSlow` (P1, checkout) fires; two P2 shop alerts fire at the same evaluation.
- 05:06:33 - the page reaches the pager.
- 05:06:36 - P1 ticket 3ba75e92-1b55-483b-a69e-6097c02b182c created in svcdesk.
- 05:06:56 - **acknowledgement** of the ticket.
- 05:07 - email memory near its peak (100.5 MB of 104.9 MB).
- 05:08:19 - **recovery**: `ShopCheckoutSlow` resolves (last sample 05:08:09 plus the 10 s evaluation interval).
- 05:10:00-05:10:05 - the last flag is off; `seeded_fault_active` falls to 0.
- 05:14 - the ad error ratio has decayed back to baseline.
- AI hypotheses, none acted on: the recorded investigator's claims were each tested after the fact (ai-rca-eval.json).
  H3 (PlaceOrder latency) held only partly: `histogram_quantile(0.99, ...PlaceOrder...) > 2000 unless on() histogram_quantile(0.99, ...ship-order...) < 1000`
  returned 8.8 s at 05:07, because the delay was shipping's. H2 (`...GetProduct... p95 > 100`) and H4
  (`...prepareOrderItemsAndShippingQuoteFromCart... p99 > 1000`) returned nothing at 05:07 and were hallucinated.

## Supporting information

`itsmlab incident 4` on `incident/tsdb-snapshot.tar.gz` and `incident/ticket.json` gives the four instants and the
three durations in the front matter. The queries above, run on the snapshot served with Prometheus 3.15.0, give
every number in Impact and Root Causes. The ledger of the AI investigation is `ai-rca-eval.json`, scoring the
recorded transcript `ai-rca/transcript.md`. The alerting and routing files are `prometheus/demo-alerts.yml`,
`alertmanager/alertmanager.yml` and `alertmanager/routing-tests.yml`.

## Problem record

- Incident record: 3ba75e92-1b55-483b-a69e-6097c02b182c (P1, acknowledged; closed when service was restored)
- Root cause: checkout waits synchronously on shipping's ShipOrder with no short timeout, so a slow carrier path becomes a slow order; email leaks memory under a flag with no memory alert below the kill limit
- Known error: international orders slow down checkout whenever ShipOrder is slow; ad requests can fail without any page; email can be OOM-killed by a leak before anyone is told
- Workaround: switch the failing flags off through the injector (`POST /flags/<flag>/off`); restart the email container if its memory nears the limit
