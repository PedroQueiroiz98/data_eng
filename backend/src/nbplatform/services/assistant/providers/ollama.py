from __future__ import annotations

from typing import Any

from nbplatform.services.assistant.providers._openai_compat import OpenAICompatBase
from nbplatform.services.assistant.providers.base import ConfigError

_DEFAULT_BASE = "http://localhost:11434"


class OllamaAssistantProvider(OpenAICompatBase):
    """Ollama local via endpoint compatível com OpenAI (`/v1/chat/completions`)."""

    provider_type = "OLLAMA"

    def validate_config(self, config: dict[str, Any], *, has_secret: bool) -> None:
        if not str(config.get("base_url") or _DEFAULT_BASE).strip():
            raise ConfigError("Base URL do Ollama é obrigatória.")
        if not str(config.get("model") or "").strip():
            raise ConfigError("Informe o modelo (ex.: llama3.1).")

    def summary(self, config: dict[str, Any]) -> str:
        return f"{config.get('model') or '—'} @ {config.get('base_url') or _DEFAULT_BASE}"

    def _endpoint(self, config: dict[str, Any]) -> str:
        base = str(config.get("base_url") or _DEFAULT_BASE).rstrip("/")
        return f"{base}/v1/chat/completions"

    def _headers(self, config: dict[str, Any], secret: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
        return headers
