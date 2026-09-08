"""CRUD dos providers globais de notificação + teste síncrono.

Regra de secret: o valor cru nunca sai. Ao gravar, `None`/`""`/`"********"`
mantêm o valor atual; qualquer outro texto grava um novo secret cifrado (Fernet).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.core.crypto import SecretCipher
from nbplatform.core.errors import DomainValidationError, NotFoundError
from nbplatform.domain.notifications import (
    NotificationEventType,
    NotificationMessage,
    NotificationProviderType,
)
from nbplatform.models.notification import NotificationProvider
from nbplatform.repositories.notification_repository import NotificationRepository
from nbplatform.schemas.notification import (
    MASK,
    NotificationProviderCreate,
    NotificationProviderRead,
    NotificationProviderUpdate,
    NotificationTestResult,
)
from nbplatform.services.notifications.providers import ConfigError, ResolvedTarget
from nbplatform.services.notifications.registry import (
    NotificationProviderRegistry,
    UnknownProviderType,
    default_registry,
)


def _cipher() -> SecretCipher:
    return SecretCipher(get_settings().secret_encryption_key)


def _keep_secret(value: str | None) -> bool:
    return value is None or value == "" or value == MASK


async def _refresh_ts(session: AsyncSession, row: NotificationProvider) -> None:
    # `updated_at`/`created_at` têm server_default/onupdate sem default Python:
    # ficam "expired" após o flush e a serialização dispararia IO lazy
    # (MissingGreenlet no asyncpg). Refrescar explicitamente resolve.
    await session.refresh(row, attribute_names=["created_at", "updated_at"])


def _to_read(
    row: NotificationProvider, registry: NotificationProviderRegistry
) -> NotificationProviderRead:
    summary = ""
    if registry.has(row.provider_type):
        try:
            summary = registry.get(row.provider_type).summary(row.configuration_json)
        except Exception:  # noqa: BLE001 - resumo nunca derruba a listagem
            summary = ""
    has_secret = row.secret_ct is not None
    return NotificationProviderRead(
        id=row.id,
        name=row.name,
        description=row.description,
        provider_type=row.provider_type,
        enabled=row.enabled,
        configuration=row.configuration_json or {},
        has_password=has_secret and row.provider_type == NotificationProviderType.EMAIL,
        has_credential=has_secret and row.provider_type == NotificationProviderType.BITRIX,
        summary=summary,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_providers(
    session: AsyncSession, *, registry: NotificationProviderRegistry | None = None
) -> list[NotificationProviderRead]:
    registry = registry or default_registry()
    rows = await NotificationRepository(session).list_providers()
    return [_to_read(r, registry) for r in rows]


async def get_provider(
    session: AsyncSession,
    provider_id: uuid.UUID,
    *,
    registry: NotificationProviderRegistry | None = None,
) -> NotificationProviderRead:
    registry = registry or default_registry()
    row = await NotificationRepository(session).get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")
    return _to_read(row, registry)


def _validate(
    registry: NotificationProviderRegistry,
    provider_type: NotificationProviderType,
    configuration: dict,
    *,
    has_secret: bool,
) -> None:
    try:
        registry.get(provider_type).validate_config(
            configuration, has_secret=has_secret
        )
    except UnknownProviderType as exc:
        raise DomainValidationError(f"Tipo de provider desconhecido: {exc}.") from exc
    except ConfigError as exc:
        raise DomainValidationError(str(exc)) from exc


async def create_provider(
    session: AsyncSession,
    payload: NotificationProviderCreate,
    *,
    registry: NotificationProviderRegistry | None = None,
) -> NotificationProviderRead:
    registry = registry or default_registry()
    repo = NotificationRepository(session)
    if await repo.name_exists(payload.name):
        raise DomainValidationError(f"Já existe um provider chamado '{payload.name}'.")
    has_secret = not _keep_secret(payload.secret)
    _validate(
        registry, payload.provider_type, payload.configuration, has_secret=has_secret
    )
    row = NotificationProvider(
        name=payload.name.strip(),
        description=(payload.description or None),
        provider_type=payload.provider_type,
        enabled=payload.enabled,
        configuration_json=payload.configuration,
    )
    if has_secret:
        row.secret_ct = _cipher().encrypt(payload.secret or "")
    session.add(row)
    await session.flush()
    await _refresh_ts(session, row)
    return _to_read(row, registry)


async def update_provider(
    session: AsyncSession,
    provider_id: uuid.UUID,
    payload: NotificationProviderUpdate,
    *,
    registry: NotificationProviderRegistry | None = None,
) -> NotificationProviderRead:
    registry = registry or default_registry()
    repo = NotificationRepository(session)
    row = await repo.get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")

    if payload.name is not None:
        if await repo.name_exists(payload.name, exclude=provider_id):
            raise DomainValidationError(
                f"Já existe um provider chamado '{payload.name}'."
            )
        row.name = payload.name.strip()
    if payload.description is not None:
        row.description = payload.description or None
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.configuration is not None:
        row.configuration_json = payload.configuration

    replace_secret = not _keep_secret(payload.secret)
    if replace_secret:
        row.secret_ct = _cipher().encrypt(payload.secret or "")

    _validate(
        registry,
        row.provider_type,
        row.configuration_json,
        has_secret=row.secret_ct is not None,
    )
    await session.flush()
    await _refresh_ts(session, row)
    return _to_read(row, registry)


async def set_enabled(
    session: AsyncSession,
    provider_id: uuid.UUID,
    enabled: bool,
    *,
    registry: NotificationProviderRegistry | None = None,
) -> NotificationProviderRead:
    registry = registry or default_registry()
    row = await NotificationRepository(session).get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")
    row.enabled = enabled
    await session.flush()
    await _refresh_ts(session, row)
    return _to_read(row, registry)


async def delete_provider(session: AsyncSession, provider_id: uuid.UUID) -> None:
    row = await NotificationRepository(session).get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")
    await session.delete(row)
    await session.flush()


def _test_message() -> NotificationMessage:
    env = get_settings().app_env
    environment = {"prod": "production", "dev": "development", "test": "test"}.get(env, env)
    now = datetime.now(UTC)
    return NotificationMessage(
        event_type=NotificationEventType.JOB_FAILED,
        title="🔔 Teste — Central de Notificações",
        message="Notificação de teste enviada pela Central de Notificações.",
        environment=environment,
        pipeline_name="Central de Notificações",
        job_name="Teste de provider",
        execution_id="teste",
        timestamp=now,
        attempt=1,
        error_type="TestNotification",
        error_message="Este é um envio de teste. Nenhuma execução falhou.",
        correlation_id="test",
        metadata={
            "Ambiente": environment,
            "Erro": "—",
            "Componente": "—",
            "Evento": "TESTE",
            "Data/Hora": now.isoformat(),
            "Event ID": "test",
            "Correlation ID": "test",
            "Workflow": "Central de Notificações",
            "Job": "Teste de provider",
            "Execution ID": "teste",
            "Attempt": "1",
            "Duration": "—",
        },
    )


async def test_provider(
    session: AsyncSession,
    _redis: Redis,
    provider_id: uuid.UUID,
    *,
    registry: NotificationProviderRegistry | None = None,
) -> NotificationTestResult:
    registry = registry or default_registry()
    row = await NotificationRepository(session).get_provider(provider_id)
    if row is None:
        raise NotFoundError(f"Provider {provider_id} não encontrado.")
    try:
        sender = registry.get(row.provider_type)
    except UnknownProviderType:
        return NotificationTestResult(
            ok=False, error=f"tipo '{row.provider_type}' sem implementação"
        )
    secret = ""
    if row.secret_ct:
        try:
            secret = _cipher().decrypt(row.secret_ct)
        except ValueError:
            return NotificationTestResult(ok=False, error="secret corrompido")

    target = ResolvedTarget(
        provider_id=row.id, config=row.configuration_json or {}, secret=secret
    )
    timeout_s = get_settings().notification_send_timeout_s
    try:
        result = await asyncio.wait_for(
            sender.send(_test_message(), target, timeout_s=timeout_s),
            timeout=timeout_s + 5,
        )
    except TimeoutError:
        return NotificationTestResult(ok=False, error=f"timeout após {timeout_s:.0f}s")
    except Exception as exc:  # noqa: BLE001
        return NotificationTestResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    return NotificationTestResult(
        ok=result.ok, detail=result.detail, error=result.error
    )
