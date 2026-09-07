from __future__ import annotations

from nbplatform.core.config import Settings


def test_defaults_are_sane() -> None:
    s = Settings(_env_file=None)
    assert s.app_env in {"dev", "test", "prod"}
    assert s.max_concurrent_executions >= 1
    assert s.execution_timeout_s > 0
    assert s.worker_lease_timeout_s >= s.worker_heartbeat_interval_s


def test_heartbeat_key_namespacing() -> None:
    s = Settings(_env_file=None, redis_heartbeat_prefix="nbp:hb:")
    assert s.heartbeat_key("worker") == "nbp:hb:worker"
    assert s.heartbeat_key("scheduler") == "nbp:hb:scheduler"


def test_is_test_flag() -> None:
    assert Settings(_env_file=None, app_env="test").is_test is True
    assert Settings(_env_file=None, app_env="dev").is_test is False


def test_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CONCURRENT_EXECUTIONS", "12")
    monkeypatch.setenv("APP_ENV", "prod")
    s = Settings(_env_file=None)
    assert s.max_concurrent_executions == 12
    assert s.app_env == "prod"
