"""Fábrica da aplicação FastAPI."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from nbplatform.api.deps import get_current_user
from nbplatform.api.routes import (
    audit,
    auth,
    executions,
    health,
    jobs,
    metrics,
    notebooks,
    schedules,
    secrets,
    variables,
    workflows,
    ws,
)
from nbplatform.core.config import get_settings
from nbplatform.core.errors import DomainError
from nbplatform.core.logging import configure_logging
from nbplatform.db.session import dispose_engine
from nbplatform.queue.redis_client import close_redis
from nbplatform.services.seed import ensure_admin_user

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, service="api")
    logger.info("api starting", extra={"app_env": settings.app_env})
    if not settings.is_test:
        try:
            await ensure_admin_user()
        except Exception:  # noqa: BLE001 - startup não deve morrer por causa do seed
            logger.exception("seed do admin falhou (seguindo mesmo assim)")
    yield
    await close_redis()
    await dispose_engine()
    logger.info("api stopped")


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )


_access_logger = logging.getLogger("nbplatform.access")


def _register_access_log(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        if request.url.path not in ("/health", "/ready", "/metrics"):
            _access_logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="nbplatform API", version="0.1.0", lifespan=lifespan)
    _register_error_handlers(app)
    _register_access_log(app)

    # Públicos
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth.router)

    # Protegidos por JWT
    protected = [Depends(get_current_user)]
    for module in (
        notebooks,
        executions,
        workflows,
        jobs,
        schedules,
        variables,
        secrets,
        audit,
    ):
        app.include_router(module.router, dependencies=protected)

    # WebSocket (auth própria via ?token=)
    app.include_router(ws.router)
    return app


app = create_app()
