"""Contrato de um provider de IA (OpenAI, Azure, Ollama, ...).

`typing.Protocol` (não ABC): a classe concreta só declara `provider_type` e
implementa os métodos. Mesma forma do `NotificationSender`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from nbplatform.domain.assistant import AssistantRequest, AssistantResult


class ConfigError(Exception):
    """Configuração de provider inválida (levantada por `validate_config`)."""


@dataclass(frozen=True)
class ResolvedAssistant:
    """Config resolvida de UM provider para uma chamada: JSON público + secret."""

    provider_id: uuid.UUID
    config: dict[str, Any] = field(default_factory=dict)
    secret: str = ""


class AssistantProvider(Protocol):
    #: identificador do tipo ("OPENAI", "AZURE_OPENAI", "OLLAMA", ...)
    provider_type: str

    def validate_config(self, config: dict[str, Any], *, has_secret: bool) -> None:
        """Valida `configuration_json`. Levanta `ConfigError` se inválida."""
        ...

    def summary(self, config: dict[str, Any]) -> str:
        """Resumo curto para a listagem (ex.: 'gpt-4o-mini @ api.openai.com')."""
        ...

    async def complete(
        self,
        request: AssistantRequest,
        target: ResolvedAssistant,
        *,
        timeout_s: float,
    ) -> AssistantResult:
        """Uma resposta completa. NÃO deve levantar — devolve `AssistantResult`."""
        ...

    def supports_stream(self) -> bool:
        """True se `stream()` entrega deltas de verdade (senão cai no fallback)."""
        ...

    def stream(
        self,
        request: AssistantRequest,
        target: ResolvedAssistant,
        *,
        timeout_s: float,
    ) -> AsyncIterator[str]:
        """Deltas de texto. Implementação padrão: um único delta = `complete().text`."""
        ...
