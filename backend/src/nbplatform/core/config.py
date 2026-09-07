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

    # Dev only — gere uma chave real em produção (docs no .env.example).
    secret_encryption_key: str = "iY0uDAIk3AqhPlmaVTZOGf-Bajj5kjmIDRZiwqRLvDc="

    # ─── Auth ───
    jwt_secret: str = "dev-only-change-me-jwt-secret-0123456789abcdef"
    jwt_expire_minutes: int = 720
    admin_email: str = "admin@nbplatform.local"
    admin_password: str = "admin"

    # ─── Sandbox de execução ───
    execution_sandbox: Literal["subprocess", "docker"] = "subprocess"
    sandbox_image: str = "nbplatform-backend"
    sandbox_cpus: str = "1"
    sandbox_memory: str = "512m"
    sandbox_pids_limit: int = 256

    # ─── Instalação de pacotes por execução (pip) ───
    # Habilita `%pip install` nas células e a lista de dependências do notebook
    # (metadata.nbplatform.dependencies), instaladas num diretório isolado por
    # execução e adicionadas ao PYTHONPATH. Nunca toca no site-packages do sistema.
    execution_pip_install: bool = True
    execution_pip_timeout_s: int = 300
    execution_pip_index_url: str = ""
    execution_pip_max_packages: int = 50

    # ─── Inteligência do editor (LSP via Jedi) ───
    lsp_enabled: bool = True
    # Interpretador cujo site-packages o Jedi enxerga (default: o próprio, que
    # roda a mesma imagem do worker/kernel). "" => usa sys.executable.
    lsp_environment_path: str = ""
    lsp_timeout_s: float = 6.0
    lsp_max_source_chars: int = 200_000
    lsp_max_completions: int = 100

    max_concurrent_jobs: int = 5
    max_concurrent_executions: int = 5

    execution_timeout_s: int = 1800
    worker_heartbeat_interval_s: int = 10
    worker_lease_timeout_s: int = 60
    recovery_interval_s: int = 30

    # Política de retry padrão para execuções avulsas (workflow tasks trazem a sua).
    execution_max_retries: int = 2
    execution_retry_initial_delay_s: float = 10.0
    execution_retry_backoff_multiplier: float = 2.0
    execution_retry_max_delay_s: float = 300.0
    execution_retry_mode: str = "TRANSIENT_ONLY"

    backend_port: int = 8000

    # Diretório de artefatos de execução (volume compartilhado worker/api).
    executions_dir: str = "/data/executions"

    # Prefixos de chaves Redis (mantidos aqui para não espalhar strings mágicas).
    redis_heartbeat_prefix: str = "nbp:heartbeat:"
    redis_queue_executions: str = "nbp:queue:executions"
    redis_queue_executions_processing: str = "nbp:queue:executions:processing"
    redis_queue_executions_delayed: str = "nbp:queue:executions:delayed"
    redis_dlq_executions: str = "nbp:dlq:executions"
    redis_exec_seq_prefix: str = "nbp:execseq:"
    redis_exec_event_prefix: str = "nbp:events:execution:"
    redis_cancel_prefix: str = "nbp:cancel:"
    redis_job_seq_prefix: str = "nbp:jobseq:"
    redis_job_event_prefix: str = "nbp:events:job:"
    redis_job_cancel_prefix: str = "nbp:jobcancel:"

    def exec_seq_key(self, execution_id: str) -> str:
        return f"{self.redis_exec_seq_prefix}{execution_id}"

    def exec_event_channel(self, execution_id: str) -> str:
        return f"{self.redis_exec_event_prefix}{execution_id}"

    def cancel_key(self, execution_id: str) -> str:
        return f"{self.redis_cancel_prefix}{execution_id}"

    def job_seq_key(self, job_id: str) -> str:
        return f"{self.redis_job_seq_prefix}{job_id}"

    def job_event_channel(self, job_id: str) -> str:
        return f"{self.redis_job_event_prefix}{job_id}"

    def job_cancel_key(self, job_id: str) -> str:
        return f"{self.redis_job_cancel_prefix}{job_id}"

    def default_retry_policy_dict(self) -> dict[str, object]:
        return {
            "max_retries": self.execution_max_retries,
            "initial_delay_seconds": self.execution_retry_initial_delay_s,
            "backoff_multiplier": self.execution_retry_backoff_multiplier,
            "max_delay_seconds": self.execution_retry_max_delay_s,
            "retry_mode": self.execution_retry_mode,
        }

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    def heartbeat_key(self, service: str) -> str:
        return f"{self.redis_heartbeat_prefix}{service}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
