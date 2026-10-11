---
lab3_first_draft:
  source: ai
  tool: "ChatGPT, model GPT 6 Sol (High), as shown in the app, fresh conversation, 11 October 2026"
  ladder: [0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0]
  verdict: refuted
  evidence: {p99_seconds: 0.1143, bucket: [0.1, 0.2], relative_width: 0.875}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: 0.1143, bucket: [0.04, 0.5], relative_width: 4.024}
---
<!-- ai-generated: 75% - the answer is the assistant's verbatim; Claude wrote the verdicts from my load 3 measurement -->

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

**Refuted.** My measurement (`itsmlab load 3`, login `mateusz-koczorowski`, 60 s open-loop at 40 requests per
second) gave a p99 of **0.1143 s**. In the assistant's ladder that p99 falls in the bucket **(0.1, 0.2]**, which is
0.1 s wide: 0.1 / 0.1143 = **87.5 %** of the p99, more than four times the 20 % that M-11 allows. The result does not
depend on the exact run: 0.95q (0.109 s) and 1.05q (0.120 s) land in the same bucket.

What that means in practice: `histogram_quantile` assumes the requests in a bucket are spread evenly across it, so
from (0.1, 0.2] it can report any p99 between 100 and 200 ms. It did exactly that on my run: with this ladder my own
histogram reported a p99 of **160.7 ms** while the real one was 114.3 ms, 41 % too high, with nothing on the
dashboard to say so. The ladder is not a bad generic default: it is denser than Go's or Python's, it has the 1 s
boundary for its assumed SLO, and it covers the upstream timeout. But it was designed without my distribution,
and my p99 sits in a slow mode between 80 and 160 ms that only one of its buckets covers.

## The draft alert rule

The assistant assumed an SLO of 95 % of searches within 1 s and wrote one rule: the share of requests slower than
1 s over 5 minutes above 5 %, with a minimum of 50 requests in 5 minutes and `for: 10m`. For my service it would
never fire on anything kb-index normally does, because nothing I measured is anywhere near 1 s (p99.99 157 ms), and
with a single 5-minute window it would both flap on short spikes and say nothing about how fast the budget is being
spent. Its labels (`method`, `route`) and its job (`fastapi`) do not match my metrics either.

What I kept: the idea of counting good requests from the bucket at the threshold (`le`) instead of computing a
`histogram_quantile`, and putting the SLO threshold exactly on a bucket boundary; both are in my latency SLI
(`le="0.2"`). What I replaced: the single window with two windows per alert, the fixed 5 % with burn-rate thresholds
derived from my objectives (14.4 and 6), the 1 s threshold with 0.2 s chosen from my distribution, and the traffic
guard, which the multiwindow ratio makes unnecessary. I also added an availability SLI, which the draft did not
have at all, and the only alert that pages is on that SLI.

## Verdict on the instructor's flawed ladder

**Refuted**, as it must be. Twelve of its fourteen boundaries are below 40 ms, where my median (15 ms) and p95
(28 ms) live, so it describes the fast path well. Then it jumps from 0.04 to 0.5 s: my p99 of **0.1143 s** falls in
**(0.04, 0.5]**, which is 0.46 s wide, 0.46 / 0.1143 = **402.4 %** of the p99. `histogram_quantile` could report
anything from 40 to 500 ms there, and the whole slow mode that decides the p99 is invisible inside a single bucket.
