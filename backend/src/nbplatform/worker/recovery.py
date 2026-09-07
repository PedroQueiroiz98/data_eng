"""Recovery de execuções abandonadas (worker morreu no meio).

RUNNING com heartbeat além do lease → falha a tentativa (LEASE_EXPIRED) e aplica
a mesma decisão de retry/DLQ do fluxo normal. Nunca deixa preso em RUNNING.

Também trata notificações abandonadas em SENDING (mesmo padrão).
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import and_, or_, select

from nbplatform.core.config import get_settings
from nbplatform.db.session import session_scope
from nbplatform.domain.enums import ExecutionStatus
from nbplatform.domain.notifications import NotificationStatus
from nbplatform.models.notification import Notification
from nbplatform.queue.execution_queue import ExecutionQueue
from nbplatform.queue.notification_queue import NotificationQueue
from nbplatform.services.execution_service import ExecutionService
from nbplatform.services.retry_coordinator import RetryCoordinator, RetryDecision
from nbplatform.ws.events import make_event, publish_execution_event

logger = logging.getLogger(__name__)

ERROR_CODE = "LEASE_EXPIRED"


async def recover_stale_executions(redis: Redis) -> int:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.worker_lease_timeout_s)
    queue = ExecutionQueue(redis)
    recovered = 0

    # 1) coleta e falha (transação curta com SKIP LOCKED)
    to_finalize: list[tuple[str, RetryDecision, ExecutionStatus]] = []
    async with session_scope() as session:
        service = ExecutionService(session)
        coordinator = RetryCoordinator(session)
        stale = await service.list_stale_running(older_than=cutoff)
        for execution in stale:
            exec_uuid = execution.id
            failed = await service.force_fail(
                exec_uuid,
                error_code=ERROR_CODE,
                error_message="worker não deu heartbeat dentro do lease",
            )
            if failed is None:
                continue
            decision = await coordinator.decide_and_apply(
                exec_uuid,
                failed_status=ExecutionStatus.FAILED,
                error_code=ERROR_CODE,
                error_message=failed.error_message,
            )
            to_finalize.append((str(exec_uuid), decision, ExecutionStatus.FAILED))
            recovered += 1

    # 2) efeitos no Redis + eventos, após o commit
    for exec_id, decision, failed_status in to_finalize:
        if decision.action == "retry":
            await queue.enqueue_delayed(
                exec_id, attempt=decision.next_attempt, ready_at=decision.ready_at
            )
            await _publish(redis, exec_id, ExecutionStatus.QUEUED, decision)
        else:
            await queue.dead_letter(
                exec_id, attempt=decision.attempt, reason=f"{ERROR_CODE}: {decision.reason}"
            )
            await _publish(redis, exec_id, failed_status, decision)

    if recovered:
        logger.warning("recovery: %d execução(ões) abandonada(s) tratada(s)", recovered)
    return recovered


async def recover_stale_notifications(redis: Redis) -> int:
    """Notificações presas em SENDING porque o worker morreu no meio do envio.

    - devolve à fila principal ids órfãos na lista de processing (crash entre
      `lease` e `ack`);
    - linhas em SENDING há mais de `notification_stale_after_s`: reabre para
      PENDING + re-enfileira (se ainda há tentativas), senão marca FAILED.

    Transação curta; efeitos no Redis só após o commit. Nunca altera o status
    de um Job.
    """
    settings = get_settings()
    queue = NotificationQueue(redis)
    reclaimed = await queue.reclaim_processing()

    cutoff = datetime.now(UTC) - timedelta(seconds=settings.notification_stale_after_s)
    to_requeue: list[str] = []
    failed = 0
    async with session_scope() as session:
        stale = (
            await session.scalars(
                select(Notification).where(
                    Notification.status == NotificationStatus.SENDING,
                    or_(
                        Notification.sending_since < cutoff,
                        and_(
                            Notification.sending_since.is_(None),
                            Notification.created_at < cutoff,
                        ),
                    ),
                )
            )
        ).all()
        for row in stale:
            row.sending_since = None
            if row.attempt < row.max_attempts:
                row.status = NotificationStatus.PENDING
                row.next_retry_at = None
                to_requeue.append(str(row.id))
            else:
                row.status = NotificationStatus.FAILED
                row.error_message = "worker reiniciou durante o envio"
                failed += 1

    for nid in to_requeue:
        await queue.enqueue(nid)

    recovered = len(to_requeue) + failed
    if recovered or reclaimed:
        logger.warning(
            "recovery: %d notificação(ões) presa(s) (%d re-enfileirada(s), %d falha(s)); "
            "%d id(s) reivindicado(s) da fila de processing",
            recovered,
            len(to_requeue),
            failed,
            reclaimed,
        )
    return recovered


async def _publish(
    redis: Redis, exec_id: str, status: ExecutionStatus, decision: RetryDecision
) -> None:
    event = make_event("status_changed", status=status)
    if decision.action == "retry":
        event["attempt"] = decision.next_attempt
        event["retry_in_s"] = round(decision.delay_s, 1)
    with contextlib.suppress(Exception):  # evento é best-effort
        await publish_execution_event(redis, exec_id, event)
