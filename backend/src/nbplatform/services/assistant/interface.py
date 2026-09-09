"""Contrato do serviço de assistente de IA."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from nbplatform.domain.assistant import AssistantResult, AssistantTask


class IAssistantService(ABC):
    @abstractmethod
    async def run(self, task: AssistantTask, **kwargs: Any) -> AssistantResult:
        """Executa uma tarefa de IA (não-streaming). NUNCA levanta."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, task: AssistantTask, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        """Executa uma tarefa de IA em streaming (frames `{delta}` / `{done}`)."""
        raise NotImplementedError

    @abstractmethod
    async def inline_complete(self, **kwargs: Any) -> str:
        """Completion inline (ghost text). Devolve "" em qualquer falha."""
        raise NotImplementedError

    @abstractmethod
    async def availability(self) -> dict[str, Any]:
        """Estado de disponibilidade (provider configurado? inline ligado?)."""
        raise NotImplementedError
