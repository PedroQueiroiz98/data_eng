from __future__ import annotations

from typing import Any

from nbplatform.services.lsp import kernel_bridge
from nbplatform.services.lsp.jedi_backend import Completion


def _jedi(label: str, kind: str = "function", call: bool = True) -> Completion:
    return Completion(label=label, insert_text=label, kind=kind, call=call)


def test_cursor_offset_maps_line_col_to_absolute() -> None:
    code = "a = 1\nb = 2\nc."
    assert kernel_bridge.cursor_offset(code, 0, 0) == 0
    assert kernel_bridge.cursor_offset(code, 1, 0) == 6
    assert kernel_bridge.cursor_offset(code, 2, 2) == 14


def test_merge_kernel_wins_and_dedupes() -> None:
    kc = kernel_bridge.KernelCompletion(
        matches=["df.columns", "df.merge(", "df.head("],
        types={"df.merge(": "function", "df.columns": "instance"},
    )
    jedi_items = [_jedi("columns", kind="instance", call=False), _jedi("to_csv")]
    out = kernel_bridge.merge(jedi_items, kc, "")
    labels = [c.label for c in out]
    # kernel primeiro, sem duplicar `columns`, e mantém o item só-Jedi
    assert labels[:3] == ["columns", "merge", "head"]
    assert "to_csv" in labels
    assert labels.count("columns") == 1
    merge_item = next(c for c in out if c.label == "merge")
    assert merge_item.detail == "kernel"
    assert merge_item.call is True


def test_merge_infers_call_from_trailing_paren() -> None:
    kc = kernel_bridge.KernelCompletion(matches=["obj.run(", "obj.value"])
    out = kernel_bridge.merge([], kc, "")
    by_label = {c.label: c for c in out}
    assert by_label["run"].call is True
    assert by_label["value"].call is False


def test_merge_filters_sensitive_kernel_matches() -> None:
    kc = kernel_bridge.KernelCompletion(matches=["cfg.api_key", "cfg.host"])
    out = kernel_bridge.merge([], kc, "")
    assert {c.label for c in out} == {"host"}


def test_merge_without_kernel_returns_jedi_untouched() -> None:
    jedi_items = [_jedi("append"), _jedi("extend")]
    assert kernel_bridge.merge(jedi_items, None, "") is jedi_items
    assert kernel_bridge.merge(jedi_items, kernel_bridge.KernelCompletion(), "") is jedi_items


class _FakeRedis:
    def __init__(self, reply: Any = None) -> None:
        self._reply = reply
        self.pushed: list[str] = []

    async def rpush(self, _key: str, value: str) -> int:
        self.pushed.append(value)
        return 1

    async def blpop(self, _keys: list[str], timeout: int = 0) -> Any:
        return self._reply


async def test_request_completion_returns_none_on_blpop_timeout() -> None:
    redis = _FakeRedis(reply=None)
    r = await kernel_bridge.request_completion(redis, "sid", "df.", 3, 1.0)
    assert r is None
    assert redis.pushed  # a op foi enfileirada


async def test_request_completion_parses_reply() -> None:
    import json

    payload = json.dumps(
        {
            "matches": ["df.columns", "df.head("],
            "cursor_start": 0,
            "cursor_end": 3,
            "metadata": {
                "_jupyter_types_experimental": [
                    {"text": "df.head(", "type": "function"},
                ]
            },
        }
    )
    redis = _FakeRedis(reply=("nbp:kernel:rpc:x", payload))
    r = await kernel_bridge.request_completion(redis, "sid", "df.", 3, 1.0)
    assert r is not None
    assert r.matches == ["df.columns", "df.head("]
    assert r.types["df.head("] == "function"
