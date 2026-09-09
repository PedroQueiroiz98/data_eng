"""Registry tipo→provider. Adicionar um provider = nova classe + uma linha aqui."""

from __future__ import annotations

from collections.abc import Iterable

from nbplatform.services.assistant.providers import (
    AssistantProvider,
    AzureOpenAIAssistantProvider,
    OllamaAssistantProvider,
    OpenAIAssistantProvider,
)
from nbplatform.services.assistant.providers._openai_compat import ClientFactory


class UnknownProviderType(KeyError):
    """Nenhum provider registrado para o tipo pedido."""


class AssistantProviderRegistry:
    def __init__(self, providers: Iterable[AssistantProvider]) -> None:
        self._by_type: dict[str, AssistantProvider] = {p.provider_type: p for p in providers}

    def get(self, provider_type: str) -> AssistantProvider:
        try:
            return self._by_type[provider_type]
        except KeyError as exc:
            raise UnknownProviderType(provider_type) from exc

    def has(self, provider_type: str) -> bool:
        return provider_type in self._by_type

    def types(self) -> list[str]:
        return list(self._by_type)


def default_registry(*, client_factory: ClientFactory | None = None) -> AssistantProviderRegistry:
    return AssistantProviderRegistry(
        [
            OpenAIAssistantProvider(client_factory),
            AzureOpenAIAssistantProvider(client_factory),
            OllamaAssistantProvider(client_factory),
        ]
    )
