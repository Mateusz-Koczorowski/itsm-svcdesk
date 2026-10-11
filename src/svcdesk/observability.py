# ai-generated: 90% - Claude wrote the middleware and the registry from MONITORING-SPEC.md M-03 to M-07; the ladder is designed from my own measurement
"""The RED histogram of svcdesk and GET /metrics (MONITORING-SPEC.md M-03 to M-07).

One histogram, `http_server_request_duration_seconds`, in seconds, labelled exactly with the OpenTelemetry HTTP
attributes in their Prometheus form. Every request the service answers is observed once, by a pure ASGI middleware
that times the whole exchange, from the request arriving to the last byte of the response.
"""

from __future__ import annotations

import time

from prometheus_client import CollectorRegistry, Histogram, disable_created_metrics, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_PLAIN_0_0_4
from starlette.requests import Request
from starlette.responses import Response

disable_created_metrics()  # no `_created` series: fewer series, nothing the checker needs

# The ladder: at most 30 finite boundaries (M-06), designed from the measured p99 (M-11, M-13).
# Measured with `itsmlab load 3` (login mateusz-koczorowski): p50 15 ms, p95 28 ms, p99 (q) 114.3 ms, p99.9 135 ms,
# with a slow mode from about 80 to 160 ms. 27 boundaries: 5 ms steps where the median lives, 10 ms steps from 50 to
# 160 ms so that every q in (0.05, 0.2] is resolved (bucket width at most 20 % of q, M-11), 0.2 as the latency SLI
# threshold (M-13), then a coarse tail up to the 3 s upstream timeout.
LADDER = (
    0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04,
    0.05, 0.06, 0.07, 0.08, 0.09, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16,
    0.18, 0.2, 0.25, 0.3, 0.5, 1.0, 2.0, 3.0,
)

UNMATCHED = "unmatched"  # the one constant route value for every request that matches no route (M-05)

REGISTRY = CollectorRegistry(auto_describe=True)  # only our histogram: no process or GC series to grow
REQUEST_DURATION = Histogram(
    "http_server_request_duration_seconds",
    "Duration of HTTP server requests, from the request arriving to the last byte of the response.",
    labelnames=("http_request_method", "http_route", "http_response_status_code"),
    buckets=LADDER,
    registry=REGISTRY,
)


def _route_template(scope: dict) -> str:
    """The template of the matched route (`/tickets/{ticket_id}`), never the raw path (M-05)."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path else UNMATCHED


class MetricsMiddleware:
    """Times every HTTP request once; /metrics itself is left out (M-04)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status = {"code": 500}
        observed = False

        def observe() -> None:
            nonlocal observed
            if observed:
                return
            observed = True
            REQUEST_DURATION.labels(
                http_request_method=scope.get("method", "GET"),
                http_route=_route_template(scope),
                http_response_status_code=str(status["code"]),
            ).observe(time.perf_counter() - start)

        async def send_and_observe(message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                observe()

        try:
            await self.app(scope, receive, send_and_observe)
        finally:
            observe()  # an exception or a dropped connection is still one observation


async def metrics(_: Request) -> Response:
    """The Prometheus text exposition format 0.0.4, with a text/plain Content-Type (M-03)."""
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_PLAIN_0_0_4)


def install(app) -> None:
    app.add_middleware(MetricsMiddleware)
    app.add_route("/metrics", metrics, methods=["GET"], include_in_schema=False)
