"""NotificationService: resolve providers globais, monta mensagem, despacha, audita.

Regras (spec §5, §6, §7, §16, §17, §18, §19):
- ausência de provider ativo nunca falha o Job (apenas log INFO);
- falha de um provider não impede os outros;
- retry com backoff exponencial e limite, independente do retry do Job;
- idempotência por (scope_id, provider_id, event_type);
- secrets nunca são logados nem retornados.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from nbplatform.core.config import get_settings
from nbplatform.core.crypto import SecretCipher
from nbplatform.db.session import session_scope
from nbplatform.domain.notifications import (
    NotificationEvent,
    NotificationEventType,
    NotificationMessage,
    NotificationStatus,
    idempotency_key,
)
from nbplatform.models.job import Job, JobTask
from nbplatform.queue.notification_queue import NotificationQueue
from nbplatform.repositories.notification_repository import NotificationRepository
from nbplatform.services.notifications.interface import INotificationService
from nbplatform.services.notifications.message_builder import (
    build_job_message,
    build_workflow_message,
)
from nbplatform.services.notifications.providers import ResolvedTarget
from nbplatform.services.notifications.registry import (
    NotificationProviderRegistry,
    UnknownProviderType,
    default_registry,
)

logger = logging.getLogger(__name__)


class NotificationService(INotificationService):
    def __init__(
        self,
        redis: Redis,
        *,
        registry: NotificationProviderRegistry | None = None,
    ) -> None:
        self.redis = redis
        self.settings = get_settings()
        self.queue = NotificationQueue(redis)
        self._cipher = SecretCipher(self.settings.secret_encryption_key)
        self._registry = registry or default_registry()

    # ── produção (chamado pelo JobOrchestrator) ──────────────────────────
    async def notify(self, event: NotificationEvent) -> list[uuid.UUID]:
        try:
            return await self._notify(event)
        except Exception:  # noqa: BLE001 - notificação nunca derruba o Job
            logger.exception(
                "Notification processing failed",
                extra={
                    "event_type": str(event.event_type),
                    "job_id": str(event.job_id),
                },
            )
            return []

    async def _notify(self, event: NotificationEvent) -> list[uuid.UUID]:
        logger.info(
            "Notification processing started",
            extra={
                "event_type": str(event.event_type),
                "job_id": str(event.job_id),
                "execution_id": str(event.execution_id),
            },
        )
        created: list[uuid.UUID] = []
        async with session_scope() as session:
            repo = NotificationRepository(session)
            providers = await repo.enabled_providers()
            if not providers:
                logger.info(
                    "No active notification provider configured",
                    extra={
                        "event_type": str(event.event_type),
                        "job_id": str(event.job_id),
                        "execution_id": str(event.execution_id),
                    },
                )
                return []
            logger.info(
                "Notification providers found",
                extra={"count": len(providers), "event_type": str(event.event_type)},
            )

            message = await self._build_message(session, event)
            if message is None:
                return []
            payload = _serialize(message)
            scope_id = event.scope_id

            for provider in providers:
                if not self._registry.has(provider.provider_type):
                    logger.warning(
                        "Notification provider type has no sender",
                        extra={"provider_type": provider.provider_type},
                    )
                    continue
                sender = self._registry.get(provider.provider_type)
                try:
                    targets = sender.targets(
                        ResolvedTarget(provider.id, provider.configuration_json or {}, "")
                    )
                except Exception:  # noqa: BLE001
                    targets = []
                dedupe = idempotency_key(scope_id, str(provider.id), event.event_type)
                seq = await self.queue.next_seq()
                delivery_id = await repo.create_if_absent(
                    notification_provider_id=provider.id,
                    provider_type=provider.provider_type,
                    event_type=event.event_type,
                    workflow_id=event.workflow_id,
                    job_id=event.job_id,
                    execution_id=event.execution_id,
                    dedupe_key=dedupe,
                    recipient=", ".join(targets) if targets else None,
                    max_attempts=self.settings.notification_max_attempts,
                    payload=payload,
                    seq=seq,
                )
                if delivery_id is not None:
                    created.append(delivery_id)

        for did in created:
            await self.queue.enqueue(str(did))
        return created

    async def _build_message(
        self, session: Any, event: NotificationEvent
    ) -> NotificationMessage | None:
        if event.job_id is None:
            return None
        job = await session.get(Job, event.job_id)
        if job is None:
            return None
        if event.event_type is NotificationEventType.JOB_FAILED:
            task = (
                await session.get(JobTask, event.job_task_id)
                if event.job_task_id
                else None
            )
            if task is None:
                return None
            return await build_job_message(session, job, task)
        return await build_workflow_message(session, job)

    # ── consumo (chamado pelo worker) ───────────────────────────────────
    async def dispatch(
        self, delivery_id: uuid.UUID, *, stop: asyncio.Event | None = None
    ) -> NotificationStatus:
        try:
            return await self._dispatch(delivery_id, stop)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Notification dispatch failed unexpectedly",
                extra={"delivery_id": str(delivery_id)},
            )
            return NotificationStatus.FAILED

    async def _dispatch(
        self, delivery_id: uuid.UUID, stop: asyncio.Event | None
    ) -> NotificationStatus:
        async with session_scope() as session:
            repo = NotificationRepository(session)
            row = await repo.get_delivery(delivery_id)
            if row is None:
                return NotificationStatus.FAILED
            if row.status == NotificationStatus.SENT:
                return NotificationStatus.SENT  # idempotência: já enviado

            provider = (
                await repo.get_provider(row.notification_provider_id)
                if row.notification_provider_id
                else None
            )
            if provider is None or not provider.enabled:
                row.status = NotificationStatus.FAILED
                row.sending_since = None
                row.error_message = "provedor removido ou desativado"
                logger.warning(
                    "Notification skipped: provider gone/disabled",
                    extra={"delivery_id": str(delivery_id)},
                )
                return NotificationStatus.FAILED

            row.status = NotificationStatus.SENDING
            row.sending_since = datetime.now(UTC)
            row.attempt += 1
            await session.flush()

            attempt = row.attempt
            max_attempts = row.max_attempts
            provider_type = provider.provider_type
            config = dict(provider.configuration_json or {})
            secret_ct = provider.secret_ct
            message = _deserialize(row.payload)
            provider_id = provider.id

        if stop is not None and stop.is_set():
            await self.queue.enqueue(str(delivery_id))
            return NotificationStatus.PENDING

        secret = ""
        if secret_ct:
            try:
                secret = self._cipher.decrypt(secret_ct)
            except ValueError:
                secret = ""

        try:
            sender = self._registry.get(provider_type)
        except UnknownProviderType:
            return await self._finish_failure(
                delivery_id, provider_type, attempt, max_attempts,
                f"tipo '{provider_type}' sem implementação",
            )

        logger.info(
            "Notification sending",
            extra={
                "delivery_id": str(delivery_id),
                "provider_type": provider_type,
                "attempt": attempt,
            },
        )
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                sender.send(
                    message,
                    ResolvedTarget(provider_id, config, secret),
                    timeout_s=self.settings.notification_send_timeout_s,
                ),
                timeout=self.settings.notification_send_timeout_s + 5,
            )
        except (TimeoutError, asyncio.CancelledError):
            result = None
        took_ms = round((time.perf_counter() - started) * 1000)

        if result is not None and result.ok:
            async with session_scope() as session:
                row = await NotificationRepository(session).get_delivery(delivery_id)
                if row is None:
                    return NotificationStatus.FAILED
                row.status = NotificationStatus.SENT
                row.sent_at = datetime.now(UTC)
                row.sending_since = None
                row.error_message = None
            logger.info(
                "Notification sent",
                extra={
                    "delivery_id": str(delivery_id),
                    "provider_type": provider_type,
                    "attempt": attempt,
                    "status": "SENT",
                    "duration_ms": took_ms,
                },
            )
            return NotificationStatus.SENT

        error = (
            (result.error if result is not None else None)
            or f"timeout após {self.settings.notification_send_timeout_s:.0f}s"
        )
        return await self._finish_failure(
            delivery_id, provider_type, attempt, max_attempts, error, took_ms
        )

    async def _finish_failure(
        self,
        delivery_id: uuid.UUID,
        provider_type: str,
        attempt: int,
        max_attempts: int,
        error: str,
        took_ms: int | None = None,
    ) -> NotificationStatus:
        async with session_scope() as session:
            row = await NotificationRepository(session).get_delivery(delivery_id)
            if row is None:
                return NotificationStatus.FAILED
            row.error_message = error[:2000]
            row.sending_since = None
            if attempt < max_attempts:
                delay = min(
                    self.settings.notification_retry_initial_delay_s
                    * self.settings.notification_retry_backoff_multiplier ** (attempt - 1),
                    self.settings.notification_retry_max_delay_s,
                )
                row.status = NotificationStatus.PENDING
                row.next_retry_at = datetime.fromtimestamp(time.time() + delay, tz=UTC)
                logger.warning(
                    "Notification sending failed",
                    extra={
                        "delivery_id": str(delivery_id),
                        "provider_type": provider_type,
                        "attempt": attempt,
                        "error": row.error_message,
                        "retry_in_s": round(delay, 1),
                        "duration_ms": took_ms,
                    },
                )
                await self.queue.enqueue_delayed(
                    str(delivery_id), ready_at=time.time() + delay
                )
                return NotificationStatus.PENDING

            row.status = NotificationStatus.FAILED
            logger.error(
                "Notification sending failed (giving up)",
                extra={
                    "delivery_id": str(delivery_id),
                    "provider_type": provider_type,
                    "attempt": attempt,
                    "error": row.error_message,
                    "status": "FAILED",
                },
            )
            return NotificationStatus.FAILED

    async def retry(self, delivery_id: uuid.UUID) -> None:
        """Reenfileira uma delivery não-SENT para nova tentativa manual."""
        async with session_scope() as session:
            row = await NotificationRepository(session).get_delivery(delivery_id)
            if row is None or row.status == NotificationStatus.SENT:
                return
            row.status = NotificationStatus.PENDING
            row.next_retry_at = None
            row.sending_since = None
            if row.attempt >= row.max_attempts:
                row.max_attempts = row.attempt + 1
        await self.queue.enqueue(str(delivery_id))


def _serialize(m: NotificationMessage) -> dict[str, Any]:
    data = asdict(m)
    data["event_type"] = str(m.event_type)
    data["timestamp"] = m.timestamp.isoformat()
    return data


def _deserialize(payload: dict[str, Any]) -> NotificationMessage:
    data = dict(payload)
    data["event_type"] = NotificationEventType(data["event_type"])
    ts = data.get("timestamp")
    data["timestamp"] = datetime.fromisoformat(ts) if ts else datetime.now(UTC)
    known = set(NotificationMessage.__dataclass_fields__)
    return NotificationMessage(**{k: v for k, v in data.items() if k in known})
