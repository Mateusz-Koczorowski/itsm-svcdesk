---
lab3_first_draft:
  source: ai
  tool: "ChatGPT, model GPT 6 Sol (High), as shown in the app, fresh conversation, 11 October 2026"
  ladder: [0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0]
  verdict: TODO
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
---
<!-- ai-generated: 50% - the answer is the assistant's verbatim; Claude formatted the file, the verdicts follow after my measurement -->

# The assistant's first draft, and two verdicts

Asked before any measurement or design, in a fresh conversation with no access to the lab's documents. The answer
below is quoted line by line (`> `) so that its own headings and code stay inside this section; nothing in it was
edited.

## Prompt

I'm adding a knowledge-base search endpoint `GET /kb/search` to a Python FastAPI service. On every request it calls an upstream search index over HTTP and returns its results. I want to instrument it with a Prometheus histogram `http_server_request_duration_seconds` (labels: method, route, status code). Please give me (1) the histogram bucket boundaries in seconds that I should use, and (2) a Prometheus alerting rule for this endpoint.

## Answer

> Assuming an initial objective of 95% of searches completing within 1 second and an upstream timeout near 5 seconds:
> 1. Histogram buckets
>
> ```
> KB_SEARCH_BUCKETS = (
>     0.025,
>     0.050,
>     0.100,
>     0.200,
>     0.300,
>     0.500,
>     0.750,
>     1.000,  # SLO boundary
>     1.500,
>     2.000,
>     3.000,
>     5.000,  # expected upstream timeout
>     7.500,
>     10.000,
> )
> ```
>
> The Prometheus client automatically adds `+Inf`. The exact `1.0` boundary is important: it lets the alert calculate the percentage meeting the SLO without percentile interpolation. Buckets around 100–500 ms also provide useful detail for normal upstream-search latency. Prometheus recommends putting a bucket exactly at a known SLO threshold. [Prometheus histogram guidance](https://prometheus.io/docs/practices/histograms/)
> 2. Alerting rule
> This alerts when more than 5% of `/kb/search` requests exceed one second for 10 minutes. The traffic condition avoids noisy alerts from tiny samples.
>
> ```
> groups:
>   - name: knowledge-base
>     rules:
>       - alert: KBSearchHighLatency
>         expr: |
>           (
>             1 -
>             (
>               sum(rate(http_server_request_duration_seconds_bucket{
>                 job="fastapi",
>                 method="GET",
>                 route="/kb/search",
>                 le="1.0"
>               }[5m]))
>               /
>               sum(rate(http_server_request_duration_seconds_count{
>                 job="fastapi",
>                 method="GET",
>                 route="/kb/search"
>               }[5m]))
>             )
>           ) > 0.05
>           and
>           sum(increase(http_server_request_duration_seconds_count{
>             job="fastapi",
>             method="GET",
>             route="/kb/search"
>           }[5m])) >= 50
>         for: 10m
>         labels:
>           severity: warning
>         annotations:
>           summary: "Knowledge-base search latency is above its objective"
>           description: >-
>             More than 5% of GET /kb/search requests have taken longer
>             than 1 second for 10 minutes.
> ```
>
> Replace `job="fastapi"` with the actual scrape job. Also verify whether the Python client exports the boundary label as `le="1.0"` or `le="1"`.
> This ratio-based alert is preferable to `histogram_quantile(0.95, ...)` here because it measures the exact percentage violating the objective. The `for` clause ensures the condition persists before firing. [Prometheus alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
> After collecting representative production data, adjust the 1-second objective and buckets to match the endpoint’s actual user-facing SLO and upstream timeout. Use the templated route `/kb/search`, never raw request paths or query strings, as the `route` label.

## Verdict on the draft ladder

TODO after the measurement.

## The draft alert rule

TODO after the measurement.

## Verdict on the instructor's flawed ladder

TODO after the measurement.
