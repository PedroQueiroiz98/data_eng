"""Liveness (`/health`) e readiness (`/ready`)."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from nbplatform.services.health_service import get_readiness

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: o processo está de pé. Não toca em dependências."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    """Readiness: Postgres, Redis, Worker e Scheduler respondendo."""
    result = await get_readiness()
    if not result.ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result.as_dict()
