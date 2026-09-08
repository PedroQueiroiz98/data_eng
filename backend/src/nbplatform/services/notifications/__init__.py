"""Central de Notificações (spec §1).

Job/Workflow FAILED → `NotificationService.notify(event)` → providers globais
ativos (Email, Bitrix) → `NotificationDelivery`. Desacoplado: os Jobs só emitem
um `NotificationEvent`; novos providers entram pelo `NotificationProviderRegistry`.
"""

from nbplatform.services.notifications.interface import INotificationService
from nbplatform.services.notifications.service import NotificationService

__all__ = ["INotificationService", "NotificationService"]
