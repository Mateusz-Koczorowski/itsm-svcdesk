---
lab3_slo:
  service: svcdesk
  route: /kb/search
  window: 30d
  slis:
    availability:
      objective: 0.995
      good: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search", http_response_status_code!~"4..|5.."}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search", http_response_status_code!~"4.."}[5m]))'
      error_budget: {fraction: 0.005, minutes: 216}
    latency:
      objective: 0.99
      threshold_seconds: 0.2
      good: 'sum(rate(http_server_request_duration_seconds_bucket{job="svcdesk", http_route="/kb/search", le="0.2"}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 432}
  alerts:
    - {alert: KbSearchAvailabilityFastBurn, sli: availability, burn_rate: 14.4, long_window: 1h, short_window: 5m}
    - {alert: KbSearchAvailabilitySlowBurn, sli: availability, burn_rate: 6, long_window: 6h, short_window: 30m}
    - {alert: KbSearchLatencyFastBurn, sli: latency, burn_rate: 14.4, long_window: 1h, short_window: 5m}
    - {alert: KbSearchLatencySlowBurn, sli: latency, burn_rate: 6, long_window: 6h, short_window: 30m}
---
<!-- ai-generated: 75% - Claude drafted the prose and the arithmetic from my load 3 measurement; I chose the window, the objectives and the severities -->

# SLO for `GET /kb/search`

What I measured with `itsmlab load 3` on my own kb-index profile (login `mateusz-koczorowski`, 60 s open-loop at
40 requests per second, 2,400 requests): p50 15.2 ms, p90 22.6 ms, p95 28.0 ms, **p99 (q) 114.3 ms**, p99.9 134.8 ms,
p99.99 156.8 ms; kb-index measured directly gave q_kb = 118.9 ms. 2 of 2,400 searches came back 502 (0.08 %). oha's
own histogram shows the shape: almost everything between 6 and 37 ms, a gap, and a slow mode of roughly 4 % of the
requests between 80 and 160 ms. Nothing was slower than about 160 ms.

The window is 30 days (43,200 minutes), so that the budget covers a month of the desk's work and survives a bad
weekend without resetting.

## Availability

The SLI is the share of valid `/kb/search` requests that did not end in a 5xx. A request counts as valid unless it
was refused with a 4xx: a missing or 201-character `q` is the client's mistake, not an outage, and counting it would
let a buggy client spend our budget. Every 502 counts as bad, including those caused by kb-index, because the user
does not care whose fault it was.

Objective **99.5 %**, so the error budget is 0.5 % of requests, or 216 minutes of a complete outage in 30 days.
kb-index fails a small share of searches on its own and svcdesk cannot fix that (no retry is allowed): I measured
0.08 %. 99.9 % would leave only 0.02 percentage points between the dependency's normal failure rate and a breach,
so a slightly unlucky day would page someone for something nobody can act on, and Lab 6's canary gate would roll
back an honest release. 99.5 % is about six times kb-index's own failure rate: its normal behaviour spends a sixth
of the budget, and the rest is there for real incidents.

## Latency

The SLI is the share of `/kb/search` requests answered within **0.2 s**, counted from the `le="0.2"` bucket, which is
a boundary of my ladder (so the SLI counts requests instead of interpolating). Objective **99 %**: an error budget
of 1 % of requests, 432 minutes in 30 days.

Why 0.2 s: it sits just above the whole distribution I measured, slow mode included (p99.99 157 ms). The slow mode
is the normal behaviour of kb-index, about 4 % of searches, and a person searching the knowledge base does not
notice the difference between 15 ms and 150 ms. A threshold inside the slow mode, for example 0.1 s, would make
roughly 2 % of requests "bad" every day, more than a 99 % objective allows, so the SLO would be breached by a
dependency that is working as designed. At 0.2 s the SLI stays near 100 % in normal operation and drops only when
kb-index gets genuinely slower (its `latency_factor` degradation, or an overloaded svcdesk), which is what the alert
should detect. 99 % rather than 99.9 % because the tail I measured is wide: at 99.9 % a few slow seconds in a quiet
hour would be enough to page. The threshold is also below Lab 6's limit of 1 s.

## Alerts

| alert | SLI | burn rate | long / short window | budget spent when it fires | severity: page or chat |
|---|---|---|---|---|---|
| KbSearchAvailabilityFastBurn | availability | 14.4 | 1h / 5m | 2 % of the 30-day budget in 1 hour | **P1, page** |
| KbSearchAvailabilitySlowBurn | availability | 6 | 6h / 30m | 5 % in 6 hours | P2, chat |
| KbSearchLatencyFastBurn | latency | 14.4 | 1h / 5m | 2 % in 1 hour | P2, chat |
| KbSearchLatencySlowBurn | latency | 6 | 6h / 30m | 5 % in 6 hours | P3, chat / ticket |

The thresholds follow from the burn rate: 14.4 x 0.005 = 7.2 % of searches failing, 6 x 0.005 = 3 %, and for
latency 14.4 x 0.01 = 14.4 % and 6 x 0.01 = 6 % of searches slower than 0.2 s. Each rule needs both windows above
the threshold: the long window proves the problem is real, the short one proves it is still happening, so the alert
stops within minutes of the recovery instead of half a long window later.

Only the fast availability burn pages a person. At a burn rate of 14.4 the whole 30-day budget is gone in about
two days, and in practice it means kb-index is down or svcdesk returns 502 for one search in fourteen: agents
cannot find known workarounds while they are on the phone. Waking someone at 3 am costs that person a night, and
the desk's users pay hours of failed searches if we wait until 9 am, so the page is worth it. The slow availability
burn (6x, the budget lasts five days) goes to chat: it will not run out before the morning, and a person woken
for it could not do more than the day shift would.

Latency never pages. A slow search is still a working search; even a 14.4x latency burn means 14 % of searches take
longer than 0.2 s, which annoys agents but does not stop them. It goes to chat as P2 during the day and P3 for the
slow burn, which is a capacity or dependency ticket rather than an incident. Paging on it would teach the on-call
person to ignore pages.

## Buckets

The ladder has 27 finite boundaries (the limit is 30): 0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, then every
10 ms from 0.05 to 0.16, then 0.18, 0.2, 0.25, 0.3, 0.5, 1, 2 and 3 s.

My q of 114.3 ms falls in the bucket (0.11, 0.12], 10 ms wide, which is 8.7 % of q; the rule allows 20 %. The grader
measures on another machine with other random draws, so I did not design for my number but for a band: every q from
0.05 s to 0.2 s is resolved (10 ms buckets up to 0.16 s and 20 ms buckets up to 0.2 s, each at most 20 % of any value
inside it). That is about 56 % below and 75 % above my q, far more than the ±10 % the handout asks for, because
the slow mode itself spans 80 to 160 ms and the p99 can land anywhere in it.

The rest of the boundaries are spent where they answer a question. The 5 ms steps up to 30 ms show the median and
the p95 (15 and 28 ms), so the dashboard can tell a slower fast path from a heavier slow mode. 0.2 s is the latency
SLI threshold. 0.25 to 3 s is a coarse tail that only has to say "much slower than normal"; 3 s is the upstream
timeout, so anything in `+Inf` is a request svcdesk itself was slow on.
