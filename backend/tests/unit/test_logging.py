from __future__ import annotations

import json
import logging

from nbplatform.core.logging import JsonFormatter


def test_json_formatter_emits_valid_json_with_extras() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello %s", args=("world",), exc_info=None,
    )
    record.worker_id = "worker-abc"  # campo extra
    payload = json.loads(formatter.format(record))
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["worker_id"] == "worker-abc"
    assert "ts" in payload
