# ai-generated: 90% - Claude wrote it from MONITORING-SPEC.md M-02 and the kb-index interface in HANDOUT.md; reviewed against the checks
"""GET /kb/search: one call to kb-index per request, no cache, no retry (MONITORING-SPEC.md M-02)."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

KB_INDEX_URL = os.environ.get("KB_INDEX_URL", "http://kb-index:8080").rstrip("/")
UPSTREAM_TIMEOUT_SECONDS = 3.0  # at least 2 s (M-02); kb-index's slow mode stays far below it

# One pooled client for the life of the process. httpx never retries a request on its own (retries=0).
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(UPSTREAM_TIMEOUT_SECONDS),
            limits=httpx.Limits(max_connections=128, max_keepalive_connections=64),
        )
    return _client


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@router.get("/kb/search")
async def kb_search(request: Request) -> JSONResponse:
    q = request.query_params.get("q")
    if q is None or not 1 <= len(q) <= 200:
        return _error(422, "validation", "q is required, 1..200 characters")

    try:
        upstream = await _get_client().get(f"{KB_INDEX_URL}/search", params={"q": q})
    except httpx.HTTPError as exc:  # timeout, connection refused or reset
        return _error(502, "upstream_unavailable", f"kb-index did not answer: {type(exc).__name__}")

    if upstream.status_code != 200:
        return _error(502, "upstream_unavailable", f"kb-index answered {upstream.status_code}")
    try:
        hits = upstream.json()["hits"]
    except (ValueError, KeyError, TypeError):
        return _error(502, "upstream_unavailable", "kb-index answered something that is not a search result")
    return JSONResponse(status_code=200, content={"query": q, "hits": hits})
