"""Env do kernel: Variáveis (visíveis) + Secrets (cifrados) + WORKSPACE_ROOT.

Espelha `ExecutionManager._build_env` (sem a parte de pip, que é por-execução).
`WORKSPACE_ROOT` liga o pacote `workspace_sdk` dentro do notebook.
"""

from __future__ import annotations

from nbplatform.db.session import session_scope
from nbplatform.services.secret_service import SecretService
from nbplatform.services.variable_service import VariableService


async def resolve_workspace_env(workspace_root: str) -> tuple[dict[str, str], list[str]]:
    """Retorna (env, secret_values) — `secret_values` para mascarar em logs/outputs."""
    async with session_scope() as session:
        variables = await VariableService(session).resolve()
        secrets = await SecretService(session).resolve_all()
    env: dict[str, str] = {}
    env.update({k: str(v) for k, v in variables.items()})
    env.update({k: str(v) for k, v in secrets.items()})
    env["WORKSPACE_ROOT"] = workspace_root
    secret_values = [v for v in secrets.values() if v]
    return env, secret_values
