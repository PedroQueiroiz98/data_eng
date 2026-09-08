"""Abstração de sender de notificação (spec §9).

O DB model `NotificationProvider` guarda a config; o *envio* é feito por um
`NotificationSender`. O `NotificationService` nunca ramifica por tipo — resolve
pelo `NotificationProviderRegistry`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from nbplatform.domain.notifications import NotificationMessage, ProviderResult


class ConfigError(Exception):
    """Configuração de provider inválida (levantada por `validate_config`)."""


@dataclass(frozen=True)
class ResolvedTarget:
    """Config resolvida de UM provider para um envio: JSON público + secret decifrado."""

    provider_id: uuid.UUID
    config: dict[str, Any] = field(default_factory=dict)
    secret: str = ""


class NotificationSender(Protocol):
    #: identificador do tipo ("EMAIL", "BITRIX", ...)
    provider_type: str

    def validate_config(self, config: dict[str, Any], *, has_secret: bool) -> None:
        """Valida `configuration_json`. Levanta `ConfigError` se inválida."""
        ...

    def summary(self, config: dict[str, Any]) -> str:
        """Resumo curto para a listagem (ex.: 'smtp.foo:587 · 3 destinatários')."""
        ...

    def targets(self, target: ResolvedTarget) -> list[str]:
        """Destinatários resolvidos (para o histórico); [] se não configurado."""
        ...

    async def send(
        self,
        message: NotificationMessage,
        target: ResolvedTarget,
        *,
        timeout_s: float,
    ) -> ProviderResult:
        """Envia. NÃO deve levantar — devolve `ProviderResult`."""
        ...
