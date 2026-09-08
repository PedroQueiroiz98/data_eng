"""Contrato do serviço de notificações (spec §5)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from nbplatform.domain.notifications import NotificationEvent


class INotificationService(ABC):
    @abstractmethod
    async def notify(self, event: NotificationEvent) -> list[uuid.UUID]:
        """Processa um evento notificável. NUNCA levanta; devolve os ids das
        `NotificationDelivery` criadas (vazio se nenhum provider ativo)."""
        raise NotImplementedError
