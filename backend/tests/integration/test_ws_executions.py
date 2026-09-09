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


def _token(tc: TestClient) -> str:
    s = get_settings()
    resp = tc.post(
        "/api/auth/login", json={"email": s.admin_email, "password": s.admin_password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def tc() -> TestClient:
    with TestClient(create_app()) as client:
        client.headers["Authorization"] = f"Bearer {_token(client)}"
        yield client


def _make_execution(tc: TestClient) -> str:
    nb_path = f"nb-{time.time()}.ipynb"
    skeleton = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "cells": [
            {
                "cell_type": "code",
                "metadata": {},
                "source": "print('ok')\n",
                "outputs": [],
                "execution_count": None,
            }
        ],
    }
    w = tc.put("/api/workspace/file", params={"path": nb_path}, json={"notebook": skeleton})
    assert w.status_code == 200, w.text
    ex = tc.post("/api/workspace/execute", json={"notebook_path": nb_path})
    assert ex.status_code == 202, ex.text
    return ex.json()["id"]


def test_snapshot_then_live_event(tc: TestClient) -> None:
    exec_id = _make_execution(tc)
    settings = get_settings()
    redis = SyncRedis.from_url(settings.redis_url)
    token = _token(tc)

    with tc.websocket_connect(f"/ws/executions/{exec_id}?token={token}") as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["execution"]["id"] == exec_id
        assert snapshot["execution"]["status"] == "QUEUED"
        assert snapshot["logs"] == []

        channel = settings.exec_event_channel(exec_id)
        event = {"type": "log", "seq": 1, "level": "INFO", "message": "olá", "ts": "t"}
        for _ in range(50):
            if redis.publish(channel, json.dumps(event)) > 0:
                break
            time.sleep(0.05)

        received = ws.receive_json()
        assert received == event


def test_ws_without_token_is_rejected(tc: TestClient) -> None:
    exec_id = _make_execution(tc)
    with pytest.raises(Exception), tc.websocket_connect(f"/ws/executions/{exec_id}") as ws:  # noqa: B017
        ws.receive_json()


def test_unknown_execution_closes(tc: TestClient) -> None:
    token = _token(tc)
    bad = f"/ws/executions/00000000-0000-0000-0000-000000000000?token={token}"
    with pytest.raises(Exception), tc.websocket_connect(bad) as ws:  # noqa: B017
        ws.receive_json()
