"""workflows.owner_id — isolamento de Workflow por usuário

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-09 02:00:00.000000+00:00

Cada Workflow passa a ter um dono. NULL = legado/global (admin vê tudo). As
listagens de Workflow/Job/Schedule filtram pelo usuário autenticado.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_workflows_owner_id",
        "workflows",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_workflows_owner_id", "workflows", ["owner_id"])
    op.create_index("ix_jobs_created_by", "jobs", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_jobs_created_by", table_name="jobs")
    op.drop_index("ix_workflows_owner_id", table_name="workflows")
    op.drop_constraint("fk_workflows_owner_id", "workflows", type_="foreignkey")
    op.drop_column("workflows", "owner_id")
