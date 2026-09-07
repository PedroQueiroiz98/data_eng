"""Serviço centralizado de notificações (spec §1).

Job FAILED → NotificationService → providers (Email, Bitrix) → histórico.
Desacoplado: os Jobs só chamam `NotificationService.enqueue_job_event(...)`.
"""

from nbplatform.services.notifications.service import NotificationService

__all__ = ["NotificationService"]
