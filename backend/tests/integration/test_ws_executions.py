from __future__ import annotations

import json
import time

import pytest
from redis import Redis as SyncRedis
from starlette.testclient import TestClient

from nbplatform.api.main import create_app
from nbplatform.core.config import get_settings
from tests.conftest import requires_services

pytestmark = requires_services


@pytest.fixture
def tc() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def _make_execution(tc: TestClient) -> str:
    nb = tc.post("/api/notebooks", json={"name": "ws"})
    assert nb.status_code == 201
    ex = tc.post(f"/api/notebooks/{nb.json()['id']}/execute", json={})
    assert ex.status_code == 202
    return ex.json()["id"]


def test_snapshot_then_live_event(tc: TestClient) -> None:
    exec_id = _make_execution(tc)
    settings = get_settings()
    redis = SyncRedis.from_url(settings.redis_url)

    with tc.websocket_connect(f"/ws/executions/{exec_id}") as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["execution"]["id"] == exec_id
        assert snapshot["execution"]["status"] == "QUEUED"
        assert snapshot["logs"] == []

        channel = settings.exec_event_channel(exec_id)
        event = {"type": "log", "seq": 1, "level": "INFO", "message": "olá", "ts": "t"}
        # publica até o subscribe do handler estar ativo
        for _ in range(50):
            if redis.publish(channel, json.dumps(event)) > 0:
                break
            time.sleep(0.05)

        received = ws.receive_json()
        assert received == event


def test_unknown_execution_closes(tc: TestClient) -> None:
    bad = "/ws/executions/00000000-0000-0000-0000-000000000000"
    with pytest.raises(Exception), tc.websocket_connect(bad) as ws:  # noqa: B017
        ws.receive_json()
