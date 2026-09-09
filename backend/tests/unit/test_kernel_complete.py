from __future__ import annotations

import asyncio
import json
from typing import Any

from nbplatform.kernel.manager import KernelSessionManager
from nbplatform.kernel.session import KernelSession


class _FakeKC:
    """Fake do KernelClient: só `complete`/`inspect` + `get_shell_msg`."""

    def __init__(self, reply: dict[str, Any]) -> None:
        self._reply = reply
        self._delivered = False

    def complete(self, _code: str, _cursor_pos: int) -> str:
        return "msg-1"

    def inspect(self, _code: str, _cursor_pos: int, detail_level: int = 0) -> str:
        return "msg-1"

    async def get_shell_msg(self) -> dict[str, Any]:
        if self._delivered:
            await asyncio.sleep(0)
            raise TimeoutError
        self._delivered = True
        return self._reply


def _session() -> KernelSession:
    return KernelSession(
        "sid",
        cwd="/tmp",
        env={},
        secret_values=[],
        startup_timeout=1.0,
        exec_timeout=1.0,
    )


async def test_complete_reply_parses_matches_and_types() -> None:
    sess = _session()
    sess.kc = _FakeKC(
        {
            "parent_header": {"msg_id": "msg-1"},
            "msg_type": "complete_reply",
            "content": {
                "matches": ["df.columns", "df.head("],
                "cursor_start": 0,
                "cursor_end": 3,
                "metadata": {
                    "_jupyter_types_experimental": [{"text": "df.head(", "type": "function"}]
                },
            },
        }
    )
    payload = await sess._complete_reply("df.", 3)
    assert payload["matches"] == ["df.columns", "df.head("]
    assert payload["metadata"]["_jupyter_types_experimental"][0]["type"] == "function"


async def test_complete_reply_masks_secret_values() -> None:
    sess = _session()
    sess.secret_values = ["s3cr3t-token-value"]
    sess.kc = _FakeKC(
        {
            "parent_header": {"msg_id": "msg-1"},
            "msg_type": "complete_reply",
            "content": {"matches": ["s3cr3t-token-value"], "metadata": {}},
        }
    )
    payload = await sess._complete_reply("x", 1)
    assert "s3cr3t-token-value" not in payload["matches"]


async def test_inspect_reply_returns_text_plain() -> None:
    sess = _session()
    sess.kc = _FakeKC(
        {
            "parent_header": {"msg_id": "msg-1"},
            "msg_type": "inspect_reply",
            "content": {"found": True, "data": {"text/plain": "Docstring of df"}},
        }
    )
    payload = await sess._inspect_reply("df", 2)
    assert payload["found"] is True
    assert "Docstring" in payload["text"]


async def test_do_introspect_replies_empty_when_no_kernel() -> None:
    got: list[tuple[str, dict[str, Any]]] = []

    async def _reply(rid: str, payload: dict[str, Any]) -> None:
        got.append((rid, payload))

    sess = _session()
    sess.reply = _reply
    sess.kc = None
    await sess._do_introspect("__complete__", {"request_id": "r1", "code": "x", "cursor_pos": 1})
    assert got == [("r1", {"matches": []})]


class _FakeRedis:
    def __init__(self) -> None:
        self.pushed: list[str] = []

    async def rpush(self, _key: str, value: str) -> int:
        self.pushed.append(value)
        return 1

    async def expire(self, _key: str, _ttl: int) -> bool:
        return True


class _FakeSession:
    def __init__(self, status: str, qsize: int = 0) -> None:
        self.status = status
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        for _ in range(qsize):
            self.queue.put_nowait({})
        self.enqueued: list[dict[str, Any]] = []

    async def enqueue(self, item: dict[str, Any]) -> None:
        self.enqueued.append(item)


async def test_manager_complete_skips_when_busy() -> None:
    redis = _FakeRedis()
    mgr = KernelSessionManager(redis)  # type: ignore[arg-type]
    mgr.sessions["sid"] = _FakeSession("busy")  # type: ignore[assignment]
    await mgr.complete("sid", "df.", 3, "r1")
    # não enfileirou; respondeu vazio via Redis
    assert mgr.sessions["sid"].enqueued == []  # type: ignore[attr-defined]
    assert json.loads(redis.pushed[0]) == {"matches": []}


async def test_manager_complete_skips_when_queue_not_empty() -> None:
    redis = _FakeRedis()
    mgr = KernelSessionManager(redis)  # type: ignore[arg-type]
    mgr.sessions["sid"] = _FakeSession("idle", qsize=1)  # type: ignore[assignment]
    await mgr.complete("sid", "df.", 3, "r1")
    assert mgr.sessions["sid"].enqueued == []  # type: ignore[attr-defined]


async def test_manager_complete_enqueues_when_idle() -> None:
    redis = _FakeRedis()
    mgr = KernelSessionManager(redis)  # type: ignore[arg-type]
    sess = _FakeSession("idle")
    mgr.sessions["sid"] = sess  # type: ignore[assignment]
    await mgr.complete("sid", "df.", 3, "r1")
    assert sess.enqueued == [
        {"op": "__complete__", "code": "df.", "cursor_pos": 3, "request_id": "r1"}
    ]


async def test_manager_complete_skips_when_no_session() -> None:
    redis = _FakeRedis()
    mgr = KernelSessionManager(redis)  # type: ignore[arg-type]
    await mgr.complete("missing", "df.", 3, "r1")
    assert json.loads(redis.pushed[0]) == {"matches": []}
