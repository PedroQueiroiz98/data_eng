"""Detecção de identificadores sensíveis para o editor inteligente.

Nomes suspeitos (password, token, secret, api_key, ...) não devem aparecer em
completions/hover com valor, nem no inspetor de variáveis em texto claro.
"""

from __future__ import annotations

import re

MASK = "********"

_SUSPICIOUS = re.compile(
    r"(password|passwd|senha|secret|segredo|token|api[_-]?key|apikey|access[_-]?key"
    r"|secret[_-]?key|client[_-]?secret|private[_-]?key|credential|credencial"
    r"|auth[_-]?token|bearer|conn[_-]?str|connection[_-]?string|dsn|sasl)",
    re.IGNORECASE,
)


def is_sensitive_name(name: str) -> bool:
    return bool(_SUSPICIOUS.search(name or ""))


def mask_value(name: str, value: str | None) -> str | None:
    """Mascara o valor se o nome for suspeito; senão devolve como está."""
    if value is None:
        return None
    return MASK if is_sensitive_name(name) else value
