"""Política de retry centralizada. Nenhum outro módulo decide backoff/limite."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from nbplatform.domain.enums import ErrorClass, RetryMode


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 0
    initial_delay_seconds: float = 10.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 600.0
    retry_mode: RetryMode = RetryMode.TRANSIENT_ONLY

    def delay_for_attempt(self, attempt: int) -> float:
        """Espera (s) antes da próxima tentativa, dado que `attempt` (1-indexed) falhou.

        attempt=1 -> initial_delay; attempt=2 -> initial_delay*mult; ... capado em max.
        """
        exponent = max(0, attempt - 1)
        raw = self.initial_delay_seconds * (self.backoff_multiplier**exponent)
        return min(raw, self.max_delay_seconds)

    def should_retry(self, *, attempt: int, error_class: ErrorClass) -> bool:
        """`attempt` é a tentativa que acabou de falhar (1-indexed)."""
        if attempt > self.max_retries:
            return False
        if self.retry_mode is RetryMode.TRANSIENT_ONLY:
            return error_class is ErrorClass.TRANSIENT
        return True  # RetryMode.ANY

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["retry_mode"] = self.retry_mode.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RetryPolicy:
        if not data:
            return cls()
        mode = data.get("retry_mode", RetryMode.TRANSIENT_ONLY)
        return cls(
            max_retries=int(data.get("max_retries", 0)),
            initial_delay_seconds=float(data.get("initial_delay_seconds", 10.0)),
            backoff_multiplier=float(data.get("backoff_multiplier", 2.0)),
            max_delay_seconds=float(data.get("max_delay_seconds", 600.0)),
            retry_mode=RetryMode(mode),
        )
