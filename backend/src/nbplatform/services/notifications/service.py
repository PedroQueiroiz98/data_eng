"""NotificationService: resolve canais, monta mensagem, despacha, registra histórico.

Regras (spec §10, §11, §12, §13, §16, §17):
- ausência de configuração nunca falha o Job;
- falha de um provider não impede os outros;
- retry com backoff exponencial e limite;
- idempotência por (job_id, event_type, channel);
- secrets nunca são logados nem retornados.
"""

from __future__ import annotations

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
    NotificationChannel,
    NotificationEvent,
    NotificationMessage,
    NotificationStatus,
)
from nbplatform.models.job import Job
from nbplatform.models.notification import NotificationConfig
from nbplatform.queue.notification_queue import NotificationQueue
from nbplatform.repositories.notification_repository import NotificationRepository
from nbplatform.services.notifications.email_sender import EmailSender, SmtpEmailSender
from nbplatform.services.notifications.message_builder import build_job_message
from nbplatform.services.notifications.providers import (
    BitrixNotificationProvider,
    EmailNotificationProvider,
    NotificationProvider,
)
from nbplatform.services.notifications.resolved_settings import ResolvedSettings, resolve

logger = logging.getLogger(__name__)

_EVENT_FLAG = {
    NotificationEvent.JOB_FAILED: "on_failure",
    NotificationEvent.JOB_SUCCESS: "on_success",
    NotificationEvent.JOB_RETRY: "on_retry",
    NotificationEvent.JOB_CANCELLED: "on_cancelled",
    NotificationEvent.JOB_STARTED: "on_started",
}


class NotificationService:
    def __init__(self, redis: Redis, *, email_sender: EmailSender | None = None) -> None:
        self.redis = redis
        self.settings = get_settings()
        self.queue = NotificationQueue(redis)
        self._cipher = SecretCipher(self.settings.secret_encryption_key)
        self._providers: dict[str, NotificationProvider] = {
            NotificationChannel.EMAIL.value: EmailNotificationProvider(
                email_sender or SmtpEmailSender()
            ),
            NotificationChannel.BITRIX.value: BitrixNotificationProvider(),
        }

    # ── produção (chamado pelo JobOrchestrator) ───────────────────────────
    async def enqueue_job_event(
        self, job_id: uuid.UUID, event: NotificationEvent
    ) -> list[uuid.UUID]:
        """Cria as linhas de histórico (idempotente) e enfileira. Nunca levanta."""
        try:
            return await self._enqueue_job_event(job_id, event)
        except Exception:  # noqa: BLE001 - notificação nunca derruba o Job
            logger.exception(
                "falha ao enfileirar notificações", extra={"job_id": str(job_id)}
            )
            return []

    async def _enqueue_job_event(
        self, job_id: uuid.UUID, event: NotificationEvent
    ) -> list[uuid.UUID]:
        created: list[uuid.UUID] = []
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return []
            repo = NotificationRepository(session)
            cfg = await self._effective_config(repo, job.workflow_id, event)
            channels = _enabled_channels(cfg, event)
            if not cfg or not channels:
                logger.info(
                    "Job FAILED / Notification: No notification channels configured",
                    extra={"job_id": str(job_id), "event": str(event)},
                )
                return []

            message = await build_job_message(session, job, event)
            payload = _serialize(message)

            for channel in channels:
                provider = self._providers[channel.value]
                targets = provider.targets(cfg)
                seq = await self.queue.next_seq()
                nid = await repo.create_if_absent(
                    job_id=job_id,
                    workflow_id=job.workflow_id,
                    execution_id=_maybe_uuid(message.execution_id),
                    channel=channel,
                    event_type=event,
                    recipient=", ".join(targets) if targets else None,
                    max_attempts=self.settings.notification_max_attempts,
                    payload=payload,
                    seq=seq,
                )
                if nid is not None:
                    created.append(nid)
                    logger.info(
                        "Notification created",
                        extra={
                            "job_id": str(job_id),
                            "channel": channel.value,
                            "event": str(event),
                        },
                    )

        for nid in created:
            await self.queue.enqueue(str(nid))
        return created

    # ── consumo (chamado pelo worker) ────────────────────────────────────
    async def dispatch(self, notification_id: uuid.UUID) -> NotificationStatus:
        try:
            return await self._dispatch(notification_id)
        except Exception:  # noqa: BLE001
            logger.exception(
                "falha inesperada ao despachar notificação",
                extra={"notification_id": str(notification_id)},
            )
            return NotificationStatus.FAILED

    async def _dispatch(self, notification_id: uuid.UUID) -> NotificationStatus:
        async with session_scope() as session:
            repo = NotificationRepository(session)
            row = await repo.get(notification_id)
            if row is None:
                return NotificationStatus.FAILED
            if row.status == NotificationStatus.SENT:
                return NotificationStatus.SENT  # idempotência: já enviado

            cfg = (
                await self._effective_config(repo, row.workflow_id, row.event_type)
                if row.workflow_id
                else None
            )
            resolved = resolve(
                await repo.get_settings_row(), self.settings, self._cipher
            )
            row.status = NotificationStatus.SENDING
            row.attempt += 1
            await session.flush()

            attempt = row.attempt
            max_attempts = row.max_attempts
            channel = row.channel
            message = _deserialize(row.payload)

        logger.info(
            "Notification started",
            extra={"notification_id": str(notification_id), "channel": channel.value},
        )
        started = time.perf_counter()
        result = await self._send(channel, message, cfg, resolved)
        took_ms = round((time.perf_counter() - started) * 1000)

        async with session_scope() as session:
            repo = NotificationRepository(session)
            row = await repo.get(notification_id)
            if row is None:
                return NotificationStatus.FAILED
            if result.ok:
                row.status = NotificationStatus.SENT
                row.sent_at = datetime.now(UTC)
                row.error_message = None
                logger.info(
                    "Notification sent",
                    extra={
                        "notification_id": str(notification_id),
                        "channel": channel.value,
                        "duration_ms": took_ms,
                    },
                )
                return NotificationStatus.SENT

            row.error_message = (result.error or "erro desconhecido")[:2000]
            if attempt < max_attempts:
                delay = min(
                    self.settings.notification_retry_initial_delay_s
                    * self.settings.notification_retry_backoff_multiplier ** (attempt - 1),
                    self.settings.notification_retry_max_delay_s,
                )
                row.status = NotificationStatus.PENDING
                row.next_retry_at = datetime.fromtimestamp(time.time() + delay, tz=UTC)
                logger.warning(
                    "Notification failed",
                    extra={
                        "notification_id": str(notification_id),
                        "channel": channel.value,
                        "attempt": attempt,
                        "error": row.error_message,
                        "retry_in_s": round(delay, 1),
                    },
                )
                await self.queue.enqueue_delayed(
                    str(notification_id), ready_at=time.time() + delay
                )
                return NotificationStatus.PENDING

            row.status = NotificationStatus.FAILED
            logger.error(
                "Notification failed (giving up)",
                extra={
                    "notification_id": str(notification_id),
                    "channel": channel.value,
                    "attempt": attempt,
                    "error": row.error_message,
                },
            )
            return NotificationStatus.FAILED

    async def retry(self, notification_id: uuid.UUID) -> None:
        """Reenfileira uma notificação FAILED para nova tentativa manual."""
        async with session_scope() as session:
            row = await NotificationRepository(session).get(notification_id)
            if row is None or row.status == NotificationStatus.SENT:
                return
            row.status = NotificationStatus.PENDING
            row.next_retry_at = None
            if row.attempt >= row.max_attempts:
                row.max_attempts = row.attempt + 1
        await self.queue.enqueue(str(notification_id))

    async def _effective_config(
        self,
        repo: NotificationRepository,
        workflow_id: uuid.UUID,
        event: NotificationEvent,
    ) -> NotificationConfig | None:
        """Config do pipeline; se não houver, cai no fallback global (só JOB_FAILED)."""
        cfg = await repo.get_config(workflow_id)
        if cfg is not None and _enabled_channels(cfg, event):
            return cfg
        if event is not NotificationEvent.JOB_FAILED:
            return cfg

        row = await repo.get_settings_row()
        enabled = (
            row.default_on_failure if row else False
        ) or self.settings.notify_default_on_failure
        if not enabled:
            return cfg

        recipients = (
            list(row.default_email_recipients)
            if row and row.default_email_recipients
            else _split(self.settings.notify_default_email_recipients)
        )
        dialog = (
            (row.default_bitrix_dialog_id if row else "")
            or self.settings.notify_default_bitrix_dialog_id
        ).strip() or None
        if not recipients and not dialog:
            return cfg

        synthetic = NotificationConfig(workflow_id=workflow_id)
        synthetic.on_failure = True
        synthetic.email_enabled = bool(recipients)
        synthetic.email_recipients = recipients
        synthetic.email_cc = []
        synthetic.email_bcc = []
        synthetic.email_subject = None
        synthetic.bitrix_enabled = bool(dialog)
        synthetic.bitrix_dialog_id = dialog
        return synthetic

    async def _send(
        self,
        channel: NotificationChannel,
        message: NotificationMessage,
        cfg: NotificationConfig | None,
        resolved: ResolvedSettings,
    ) -> Any:
        provider = self._providers[channel.value]
        if cfg is None:
            from nbplatform.domain.notifications import ProviderResult

            return ProviderResult.failure("configuração do pipeline removida")
        return await provider.send(message, cfg, resolved)


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _enabled_channels(
    cfg: NotificationConfig | None, event: NotificationEvent
) -> list[NotificationChannel]:
    if cfg is None or not getattr(cfg, _EVENT_FLAG[event], False):
        return []
    out: list[NotificationChannel] = []
    if cfg.email_enabled:
        out.append(NotificationChannel.EMAIL)
    if cfg.bitrix_enabled:
        out.append(NotificationChannel.BITRIX)
    return out


def _serialize(m: NotificationMessage) -> dict[str, Any]:
    data = asdict(m)
    data["event_type"] = str(m.event_type)
    data["timestamp"] = m.timestamp.isoformat()
    return data


def _deserialize(payload: dict[str, Any]) -> NotificationMessage:
    data = dict(payload)
    data["event_type"] = NotificationEvent(data["event_type"])
    ts = data.get("timestamp")
    data["timestamp"] = datetime.fromisoformat(ts) if ts else datetime.now(UTC)
    known = set(NotificationMessage.__dataclass_fields__)
    return NotificationMessage(**{k: v for k, v in data.items() if k in known})


def _maybe_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
