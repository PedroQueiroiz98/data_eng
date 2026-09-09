"""Assistente de IA do editor de notebooks (spec §4-§18).

Provider-agnóstico: `AssistantService` resolve o provider ativo pelo
`AssistantProviderRegistry` e nunca ramifica por tipo. Adicionar um provider =
nova classe em `providers/` + uma linha em `registry.default_registry()`.
"""

from nbplatform.services.assistant.interface import IAssistantService
from nbplatform.services.assistant.service import AssistantService

__all__ = ["IAssistantService", "AssistantService"]
