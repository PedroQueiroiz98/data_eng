from __future__ import annotations

import pytest
from sqlalchemy import inspect

from nbplatform.db.session import get_engine
from tests.conftest import requires_services

pytestmark = pytest.mark.asyncio

EXPECTED_TABLES = {
    "users",
    "notebooks",
    "notebook_versions",
    "executions",
    "execution_logs",
    "workflows",
    "workflow_tasks",
    "workflow_dependencies",
    "jobs",
    "job_tasks",
    "job_logs",
    "schedules",
    "variables",
    "secrets",
    "audit_logs",
    "alembic_version",
}


@requires_services
async def test_all_domain_tables_exist_after_migration() -> None:
    async with get_engine().connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = EXPECTED_TABLES - tables
    assert not missing, f"tabelas ausentes: {sorted(missing)}"
