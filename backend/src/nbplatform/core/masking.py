"""Masking de valores sensíveis (logs de execução e parâmetros exibidos na UI)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

MASK = "***"
PARAM_MASK = "********"
_MIN_LEN = 4  # não mascara valores curtos demais (ruído)

_SENSITIVE_KEY = re.compile(
    r"(password|passwd|senha|secret|segredo|token|api[_-]?key|apikey|access[_-]?key"
    r"|secret[_-]?key|client[_-]?secret|private[_-]?key|credential|credencial"
    r"|auth[_-]?token|bearer|conn[_-]?str|connection[_-]?string|dsn)",
    re.IGNORECASE,
)


def mask_secrets(text: str, values: Iterable[str]) -> str:
    for value in values:
        if value and len(value) >= _MIN_LEN and value in text:
            text = text.replace(value, MASK)
    return text


def is_sensitive_key(name: str) -> bool:
    """True quando o nome do parâmetro sugere um segredo (password, token, ...)."""
    return bool(_SENSITIVE_KEY.search(name or ""))


def mask_params(params: Mapping[str, Any]) -> dict[str, Any]:
    """Copia o mapa mascarando valores de chaves sensíveis (para exibição na UI)."""
    return {
        key: (PARAM_MASK if is_sensitive_key(key) else value)
        for key, value in params.items()
    }
