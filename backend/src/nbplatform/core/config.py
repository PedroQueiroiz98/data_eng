"""Configuração da aplicação (12-factor via variáveis de ambiente)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://nbplatform:nbplatform@localhost:5432/nbplatform"
    redis_url: str = "redis://localhost:6379/0"

    secret_encryption_key: str = "CHANGE_ME_generate_a_real_fernet_key_base64_32bytes="

    max_concurrent_jobs: int = 5
    max_concurrent_executions: int = 5

    execution_timeout_s: int = 1800
    worker_heartbeat_interval_s: int = 10
    worker_lease_timeout_s: int = 60

    backend_port: int = 8000

    # Diretório de artefatos de execução (volume compartilhado worker/api).
    executions_dir: str = "/data/executions"

    # Prefixos de chaves Redis (mantidos aqui para não espalhar strings mágicas).
    redis_heartbeat_prefix: str = "nbp:heartbeat:"
    redis_queue_executions: str = "nbp:queue:executions"
    redis_queue_executions_processing: str = "nbp:queue:executions:processing"
    redis_dlq_executions: str = "nbp:dlq:executions"
    redis_exec_seq_prefix: str = "nbp:execseq:"
    redis_exec_event_prefix: str = "nbp:events:execution:"

    def exec_seq_key(self, execution_id: str) -> str:
        return f"{self.redis_exec_seq_prefix}{execution_id}"

    def exec_event_channel(self, execution_id: str) -> str:
        return f"{self.redis_exec_event_prefix}{execution_id}"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    def heartbeat_key(self, service: str) -> str:
        return f"{self.redis_heartbeat_prefix}{service}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
