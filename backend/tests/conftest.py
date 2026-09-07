from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(scope="session", autouse=True)
def _clear_settings_cache() -> None:
    from nbplatform.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _flush_test_redis() -> None:
    """Limpa o Redis de teste (idealmente um DB dedicado, ex.: .../1)."""
    if not os.environ.get("NBP_INTEGRATION"):
        return
    import contextlib

    from redis import Redis as SyncRedis

    from nbplatform.core.config import get_settings

    with contextlib.suppress(Exception):
        SyncRedis.from_url(get_settings().redis_url).flushdb()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _dispose_engine_at_end() -> AsyncIterator[None]:
    yield
    from nbplatform.db.session import dispose_engine
    from nbplatform.queue.redis_client import close_redis

    await close_redis()
    await dispose_engine()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    from nbplatform.api.main import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as ac,
    ):
        yield ac


def _services_available() -> bool:
    """True se DATABASE_URL/REDIS_URL apontam para hosts alcançáveis (ambiente compose)."""
    return os.environ.get("NBP_INTEGRATION", "").lower() in {"1", "true", "yes"} or bool(
        os.environ.get("DATABASE_URL")
    )


requires_services = pytest.mark.skipif(
    not _services_available(),
    reason="Requer Postgres e Redis (rode via `make test-backend` ou defina NBP_INTEGRATION=1).",
)
