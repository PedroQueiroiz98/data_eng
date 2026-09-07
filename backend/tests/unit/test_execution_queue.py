from __future__ import annotations

import json

from nbplatform.queue.execution_queue import QueueMessage


def test_queue_message_decode() -> None:
    raw = json.dumps({"execution_id": "abc", "attempt": 2, "enqueued_at": 1.0})
    msg = QueueMessage.decode(raw)
    assert msg.execution_id == "abc"
    assert msg.attempt == 2
    assert msg.raw == raw


def test_queue_message_decode_defaults_attempt() -> None:
    msg = QueueMessage.decode(json.dumps({"execution_id": "xyz"}))
    assert msg.attempt == 1
