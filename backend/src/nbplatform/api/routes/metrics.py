"""`GET /metrics` — exposição Prometheus (público, para scraping)."""

from __future__ import annotations

from fastapi import APIRouter, Response

from nbplatform.api.deps import RedisDep, SessionDep
from nbplatform.core.metrics import collect_snapshot, render

router = APIRouter(tags=["observability"])

_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@router.get("/metrics")
async def metrics(session: SessionDep, redis: RedisDep) -> Response:
    snapshot = await collect_snapshot(session, redis)
    return Response(content=render(snapshot), media_type=_CONTENT_TYPE)
