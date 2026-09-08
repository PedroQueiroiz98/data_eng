"""Registry type→sender (spec §10).

Adicionar um novo provider (ex.: Slack) = criar `SlackNotificationProvider` e
somar uma linha em `default_registry`. O `NotificationService` não muda.
"""

from __future__ import annotations

from collections.abc import Iterable

from nbplatform.services.notifications.email_sender import EmailSender
from nbplatform.services.notifications.providers import (
    BitrixNotificationProvider,
    EmailNotificationProvider,
    NotificationSender,
)


class UnknownProviderType(KeyError):
    """Nenhum sender registrado para o tipo pedido."""


class NotificationProviderRegistry:
    def __init__(self, senders: Iterable[NotificationSender]) -> None:
        self._by_type: dict[str, NotificationSender] = {s.provider_type: s for s in senders}

    def get(self, provider_type: str) -> NotificationSender:
        try:
            return self._by_type[provider_type]
        except KeyError as exc:
            raise UnknownProviderType(provider_type) from exc

    def has(self, provider_type: str) -> bool:
        return provider_type in self._by_type

    def types(self) -> list[str]:
        return list(self._by_type)


def default_registry(*, email_sender: EmailSender | None = None) -> NotificationProviderRegistry:
    return NotificationProviderRegistry(
        [
            EmailNotificationProvider(email_sender),
            BitrixNotificationProvider(),
        ]
    )
