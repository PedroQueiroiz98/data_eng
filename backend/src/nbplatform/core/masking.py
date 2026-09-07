"""Masking de valores sensíveis em texto (logs de execução)."""

from __future__ import annotations

from collections.abc import Iterable

MASK = "***"
_MIN_LEN = 4  # não mascara valores curtos demais (ruído)


def mask_secrets(text: str, values: Iterable[str]) -> str:
    for value in values:
        if value and len(value) >= _MIN_LEN and value in text:
            text = text.replace(value, MASK)
    return text
