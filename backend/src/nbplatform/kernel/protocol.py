"""Tradução de mensagens iopub do kernel → outputs no formato nbformat.

Os mesmos dicts de output são renderizados no frontend (`components/notebook/mime/`)
tanto ao vivo quanto quando gravados no `.ipynb`.
"""

from __future__ import annotations

from typing import Any

from nbplatform.core.masking import mask_secrets


def _mask(text: str, secrets: list[str]) -> str:
    return mask_secrets(text, secrets) if secrets else text


def _mask_bundle(data: dict[str, Any], secrets: list[str]) -> dict[str, Any]:
    if not secrets:
        return data
    out: dict[str, Any] = {}
    for mime, val in data.items():
        if isinstance(val, str):
            out[mime] = mask_secrets(val, secrets)
        elif isinstance(val, list) and all(isinstance(x, str) for x in val):
            out[mime] = [mask_secrets(x, secrets) for x in val]
        else:
            out[mime] = val
    return out


def iopub_to_output(
    msg_type: str, content: dict[str, Any], secrets: list[str]
) -> dict[str, Any] | None:
    """iopub message → dict de output nbformat, ou None se a msg não gera output."""
    if msg_type == "stream":
        return {
            "output_type": "stream",
            "name": content.get("name", "stdout"),
            "text": _mask(str(content.get("text", "")), secrets),
        }
    if msg_type in ("execute_result", "display_data"):
        out: dict[str, Any] = {
            "output_type": msg_type,
            "data": _mask_bundle(dict(content.get("data", {})), secrets),
            "metadata": dict(content.get("metadata", {})),
        }
        if msg_type == "execute_result":
            out["execution_count"] = content.get("execution_count")
        return out
    if msg_type == "error":
        return {
            "output_type": "error",
            "ename": content.get("ename", ""),
            "evalue": _mask(str(content.get("evalue", "")), secrets),
            "traceback": [_mask(str(line), secrets) for line in content.get("traceback", [])],
        }
    return None
