"""Abstração de provider de notificação (spec §1)."""

from __future__ import annotations

from typing import Protocol

from nbplatform.domain.notifications import NotificationMessage, ProviderResult
from nbplatform.models.notification import NotificationConfig
from nbplatform.services.notifications.resolved_settings import ResolvedSettings


class NotificationProvider(Protocol):
    #: identificador do canal ("EMAIL", "BITRIX", ...)
    type: str

    def targets(self, config: NotificationConfig) -> list[str]:
        """Destinatários resolvidos (para o histórico); [] se não configurado."""
        ...

    async def send(
        self,
        message: NotificationMessage,
        config: NotificationConfig,
        settings: ResolvedSettings,
    ) -> ProviderResult:
        """Envia. NÃO deve levantar — devolve `ProviderResult`."""
        ...
