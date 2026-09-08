"""workflow_tasks: notebook como arquivo do Workspace (workspace_id + notebook_path)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-08 15:30:00.000000+00:00

Espelha a migração 0009 (que adicionou os campos análogos em `executions`).
`notebook_id` permanece (nullable) para workflows legados; o orquestrador dá
preferência a (workspace_id, notebook_path). O backfill dos campos novos é feito
pelo script `python -m nbplatform.scripts.migrate_legacy_notebooks`.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_tasks",
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "workflow_tasks",
        sa.Column("notebook_path", sa.String(length=1024), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_tasks_workspace_id",
        "workflow_tasks",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_workflow_tasks_workspace_id", "workflow_tasks", ["workspace_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_tasks_workspace_id", table_name="workflow_tasks")
    op.drop_constraint(
        "fk_workflow_tasks_workspace_id", "workflow_tasks", type_="foreignkey"
    )
    op.drop_column("workflow_tasks", "notebook_path")
    op.drop_column("workflow_tasks", "workspace_id")
