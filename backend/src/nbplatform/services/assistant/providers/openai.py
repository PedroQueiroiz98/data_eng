from __future__ import annotations

from typing import Any

from nbplatform.services.assistant.providers._openai_compat import OpenAICompatBase
from nbplatform.services.assistant.providers.base import ConfigError

_DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAIAssistantProvider(OpenAICompatBase):
    provider_type = "OPENAI"

    def validate_config(self, config: dict[str, Any], *, has_secret: bool) -> None:
        if not str(config.get("model") or "").strip():
            raise ConfigError("Informe o modelo (ex.: gpt-4o-mini).")
        if not has_secret:
            raise ConfigError("API key é obrigatória.")

    def summary(self, config: dict[str, Any]) -> str:
        base = str(config.get("base_url") or _DEFAULT_BASE).replace("https://", "")
        return f"{config.get('model') or '—'} @ {base}"

    def _endpoint(self, config: dict[str, Any]) -> str:
        base = str(config.get("base_url") or _DEFAULT_BASE).rstrip("/")
        return f"{base}/chat/completions"

    def _headers(self, config: dict[str, Any], secret: str) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
        org = str(config.get("organization") or "").strip()
        if org:
            headers["OpenAI-Organization"] = org
        return headers
