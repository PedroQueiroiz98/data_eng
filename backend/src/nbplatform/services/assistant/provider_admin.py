"""CRUD dos providers de IA globais + teste síncrono.

Regra de secret (API key): o valor cru nunca sai. `None`/`""`/`MASK` mantêm o
valor atual; qualquer outro texto grava uma nova key cifrada (Fernet).
`is_default`: no máximo um provider habilitado é o default.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.crypto import SecretCipher
from nbplatform.core.errors import DomainValidationError, NotFoundError
from nbplatform.domain.assistant import (
    AssistantProviderType,
    AssistantRequest,
    AssistantTask,
    ChatMessage,
)
from nbplatform.models.assistant import AssistantProvider
from nbplatform.repositories.assistant_repository import AssistantRepository
from nbplatform.schemas.assistant import (
    MASK,
    AssistantProviderCreate,
    AssistantProviderRead,
    AssistantProviderUpdate,
    AssistantTestResult,
)
from nbplatform.services.assistant.providers import ConfigError, ResolvedAssistant
from nbplatform.services.assistant.registry import (
    AssistantProviderRegistry,
    UnknownProviderType,
    default_registry,
)


def _cipher() -> SecretCipher:
    return SecretCipher(get_settings().secret_encryption_key)


def _keep_secret(value: str | None) -> bool:
    return value is None or value == "" or value == MASK


async def _refresh_ts(session: AsyncSession, row: AssistantProvider) -> None:
    await session.refresh(row, attribute_names=["created_at", "updated_at"])


def _to_read(
    row: AssistantProvider, registry: AssistantProviderRegistry
) -> AssistantProviderRead:
    summary = ""
    if registry.has(row.provider_type):
        try:
            summary = registry.get(row.provider_type).summary(row.configuration_json)
        except Exception:  # noqa: BLE001
            summary = ""
    return AssistantProviderRead(
        id=row.id,
        name=row.name,
        description=row.description,
        provider_type=row.provider_type,
        enabled=row.enabled,
        is_default=row.is_default,
        configuration=row.configuration_json or {},
        has_key=row.secret_ct is not None,
        summary=summary,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _registry() -> AssistantProviderRegistry:
    return default_registry()


def _validate(
    registry: AssistantProviderRegistry,
    provider_type: AssistantProviderType,
    configuration: dict[str, Any],
    *,
    has_secret: bool,
) -> None:
    try:
        registry.get(provider_type).validate_config(configuration, has_secret=has_secret)
    except UnknownProviderType as exc:
        raise DomainValidationError(f"Tipo de provider desconhecido: {exc}.") from exc
    except ConfigError as exc:
        raise DomainValidationError(str(exc)) from exc


async def list_providers(session: AsyncSession) -> list[AssistantProviderRead]:
    registry = _registry()
    rows = await AssistantRepository(session).list_providers()
    return [_to_read(r, registry) for r in rows]


async def get_provider(
    session: AsyncSession, provider_id: uuid.UUID
) -> AssistantProviderRead:
    row = await AssistantRepository(session).get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")
    return _to_read(row, _registry())


async def create_provider(
    session: AsyncSession, payload: AssistantProviderCreate
) -> AssistantProviderRead:
    registry = _registry()
    repo = AssistantRepository(session)
    if await repo.name_exists(payload.name):
        raise DomainValidationError(f"Já existe um provider chamado '{payload.name}'.")
    has_secret = not _keep_secret(payload.secret)
    _validate(registry, payload.provider_type, payload.configuration, has_secret=has_secret)
    row = AssistantProvider(
        name=payload.name.strip(),
        description=(payload.description or None),
        provider_type=payload.provider_type,
        enabled=payload.enabled,
        is_default=payload.is_default and payload.enabled,
        configuration_json=payload.configuration,
    )
    if has_secret:
        row.secret_ct = _cipher().encrypt(payload.secret or "")
    session.add(row)
    await session.flush()
    if row.is_default:
        await repo.clear_default(exclude=row.id)
    await _refresh_ts(session, row)
    return _to_read(row, registry)


async def update_provider(
    session: AsyncSession, provider_id: uuid.UUID, payload: AssistantProviderUpdate
) -> AssistantProviderRead:
    registry = _registry()
    repo = AssistantRepository(session)
    row = await repo.get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")

    if payload.name is not None:
        if await repo.name_exists(payload.name, exclude=provider_id):
            raise DomainValidationError(f"Já existe um provider chamado '{payload.name}'.")
        row.name = payload.name.strip()
    if payload.description is not None:
        row.description = payload.description or None
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.configuration is not None:
        row.configuration_json = payload.configuration
    if payload.is_default is not None:
        row.is_default = payload.is_default and row.enabled

    if not _keep_secret(payload.secret):
        row.secret_ct = _cipher().encrypt(payload.secret or "")

    _validate(
        registry, row.provider_type, row.configuration_json, has_secret=row.secret_ct is not None
    )
    await session.flush()
    if row.is_default:
        await repo.clear_default(exclude=row.id)
    await _refresh_ts(session, row)
    return _to_read(row, registry)


async def set_enabled(
    session: AsyncSession, provider_id: uuid.UUID, enabled: bool
) -> AssistantProviderRead:
    repo = AssistantRepository(session)
    row = await repo.get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")
    row.enabled = enabled
    if not enabled:
        row.is_default = False
    await session.flush()
    await _refresh_ts(session, row)
    return _to_read(row, _registry())


async def delete_provider(session: AsyncSession, provider_id: uuid.UUID) -> None:
    row = await AssistantRepository(session).get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")
    await session.delete(row)
    await session.flush()


async def test_provider(
    session: AsyncSession,
    provider_id: uuid.UUID,
    *,
    registry: AssistantProviderRegistry | None = None,
) -> AssistantTestResult:
    registry = registry or _registry()
    row = await AssistantRepository(session).get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")
    try:
        provider = registry.get(row.provider_type)
    except UnknownProviderType:
        return AssistantTestResult(ok=False, error=f"tipo '{row.provider_type}' sem implementação")
    secret = ""
    if row.secret_ct:
        try:
            secret = _cipher().decrypt(row.secret_ct)
        except ValueError:
            return AssistantTestResult(ok=False, error="API key corrompida")
    target = ResolvedAssistant(
        provider_id=row.id, config=dict(row.configuration_json or {}), secret=secret
    )
    req = AssistantRequest(
        task=AssistantTask.CHAT,
        messages=[
            ChatMessage("system", "Responda apenas com a palavra OK."),
            ChatMessage("user", "ping"),
        ],
        max_tokens=5,
        temperature=0.0,
    )
    timeout_s = min(15.0, get_settings().assistant_request_timeout_s)
    try:
        result = await asyncio.wait_for(
            provider.complete(req, target, timeout_s=timeout_s), timeout=timeout_s + 5
        )
    except (TimeoutError, asyncio.CancelledError):
        return AssistantTestResult(ok=False, error=f"timeout após {timeout_s:.0f}s")
    except Exception as exc:  # noqa: BLE001
        return AssistantTestResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    if result.ok:
        return AssistantTestResult(ok=True, detail=result.model or "ok")
    return AssistantTestResult(ok=False, error=result.error or "falha desconhecida")
