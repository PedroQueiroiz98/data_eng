"""Fábrica da aplicação FastAPI."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nbplatform.api.routes import executions, health, jobs, notebooks, workflows, ws
from nbplatform.core.config import get_settings
from nbplatform.core.errors import DomainError
from nbplatform.core.logging import configure_logging
from nbplatform.db.session import dispose_engine
from nbplatform.queue.redis_client import close_redis
from nbplatform.services.seed import ensure_dev_user

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, service="api")
    logger.info("api starting", extra={"app_env": settings.app_env})
    if not settings.is_test:
        try:
            await ensure_dev_user()
        except Exception:  # noqa: BLE001 - startup não deve morrer por causa do seed
            logger.exception("seed do usuário dev falhou (seguindo mesmo assim)")
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


def create_app() -> FastAPI:
    app = FastAPI(title="nbplatform API", version="0.1.0", lifespan=lifespan)
    _register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(notebooks.router)
    app.include_router(executions.router)
    app.include_router(workflows.router)
    app.include_router(jobs.router)
    app.include_router(ws.router)
    return app


app = create_app()
