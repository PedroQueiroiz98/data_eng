"""Decide, após uma falha de execução, entre re-enfileirar (backoff) ou DLQ.

Aplica só as transições no banco; os efeitos no Redis (delayed queue / DLQ) ficam
a cargo de quem chama, DEPOIS do commit — para o worker não achar a execução
antes de ela estar persistida como QUEUED.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from nbplatform.core.config import get_settings
from nbplatform.domain.enums import ErrorClass, ExecutionStatus
from nbplatform.domain.error_classification import classify
from nbplatform.domain.retry_policy import RetryPolicy
from nbplatform.services.execution_service import ExecutionService


@dataclass(frozen=True)
class RetryDecision:
    action: str  # "retry" | "dead"
    error_class: ErrorClass
    attempt: int  # tentativa que falhou
    next_attempt: int = 0
    delay_s: float = 0.0
    ready_at: float = 0.0
    reason: str = ""


class RetryCoordinator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.executions = ExecutionService(session)
        self.settings = get_settings()

    def policy(self) -> RetryPolicy:
        return RetryPolicy.from_dict(self.settings.default_retry_policy_dict())

    async def decide_and_apply(
        self,
        execution_id: uuid.UUID,
        *,
        failed_status: ExecutionStatus,
        error_code: str | None,
        error_message: str | None,
    ) -> RetryDecision:
        execution = await self.executions.get(execution_id)
        attempt = execution.attempt
        error_class = classify(error_code, error_message)
        policy = self.policy()

        if policy.should_retry(attempt=attempt, error_class=error_class):
            await self.executions.requeue_for_retry(execution_id)
            delay = policy.delay_for_attempt(attempt)
            return RetryDecision(
                action="retry",
                error_class=error_class,
                attempt=attempt,
                next_attempt=attempt + 1,
                delay_s=delay,
                ready_at=time.time() + delay,
            )

        reason = (
            f"retries esgotados (attempt {attempt}/{policy.max_retries})"
            if attempt > policy.max_retries
            else f"erro {error_class.value} não elegível a retry"
        )
        return RetryDecision(
            action="dead", error_class=error_class, attempt=attempt, reason=reason
        )
