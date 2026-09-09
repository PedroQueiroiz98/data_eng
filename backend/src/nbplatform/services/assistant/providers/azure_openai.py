from __future__ import annotations

from typing import Any

from nbplatform.services.assistant.providers._openai_compat import OpenAICompatBase
from nbplatform.services.assistant.providers.base import ConfigError

_DEFAULT_API_VERSION = "2024-06-01"


class AzureOpenAIAssistantProvider(OpenAICompatBase):
    provider_type = "AZURE_OPENAI"

    def validate_config(self, config: dict[str, Any], *, has_secret: bool) -> None:
        if not str(config.get("endpoint") or "").strip():
            raise ConfigError("Endpoint do Azure é obrigatório.")
        if not str(config.get("deployment") or "").strip():
            raise ConfigError("Nome do deployment é obrigatório.")
        if not has_secret:
            raise ConfigError("API key é obrigatória.")

    def summary(self, config: dict[str, Any]) -> str:
        return f"{config.get('deployment') or '—'} @ {config.get('endpoint') or '—'}"

    def _model(self, config: dict[str, Any]) -> str:
        # no Azure o "model" vai na URL (deployment); o body ainda leva um nome.
        return str(config.get("deployment") or "")

    def _endpoint(self, config: dict[str, Any]) -> str:
        endpoint = str(config.get("endpoint") or "").rstrip("/")
        deployment = str(config.get("deployment") or "")
        api_version = str(config.get("api_version") or _DEFAULT_API_VERSION)
        return (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={api_version}"
        )

    def _headers(self, config: dict[str, Any], secret: str) -> dict[str, str]:
        return {"api-key": secret, "Content-Type": "application/json"}
