"""workspace: workspaces, workspace_git_repositories, execution source columns

Revision ID: a1b2c3d4e5f6
Revises: 10ff2ca0360d
Create Date: 2026-09-07 18:00:00.000000+00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "10ff2ca0360d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_workspaces_owner_id"), "workspaces", ["owner_id"])

    op.create_table(
        "workspace_git_repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("repo_url", sa.String(length=500), nullable=False),
        sa.Column("repo_name", sa.String(length=200), nullable=True),
        sa.Column("repo_owner", sa.String(length=200), nullable=True),
        sa.Column("default_branch", sa.String(length=200), nullable=True),
        sa.Column("current_branch", sa.String(length=200), nullable=True),
        sa.Column("access_token_ct", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_workspace_git_repo_workspace"),
    )
    op.create_index(
        op.f("ix_workspace_git_repositories_workspace_id"),
        "workspace_git_repositories",
        ["workspace_id"],
    )

    # executions: colunas aditivas para a origem WORKSPACE.
    op.add_column(
        "executions",
        sa.Column(
            "source",
            sa.String(length=20),
            server_default="DB",
            nullable=False,
        ),
    )
    op.add_column(
        "executions", sa.Column("workspace_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "executions", sa.Column("notebook_path", sa.String(length=1024), nullable=True)
    )
    op.add_column(
        "executions", sa.Column("source_commit", sa.String(length=64), nullable=True)
    )
    op.alter_column(
        "executions", "notebook_version_id", existing_type=sa.Uuid(), nullable=True
    )
    op.create_foreign_key(
        "fk_executions_workspace_id",
        "executions",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_executions_workspace", "executions", ["workspace_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_executions_workspace", table_name="executions")
    op.drop_constraint(
        "fk_executions_workspace_id", "executions", type_="foreignkey"
    )
    op.alter_column(
        "executions", "notebook_version_id", existing_type=sa.Uuid(), nullable=False
    )
    op.drop_column("executions", "source_commit")
    op.drop_column("executions", "notebook_path")
    op.drop_column("executions", "workspace_id")
    op.drop_column("executions", "source")

    op.drop_index(
        op.f("ix_workspace_git_repositories_workspace_id"),
        table_name="workspace_git_repositories",
    )
    op.drop_table("workspace_git_repositories")
    op.drop_index(op.f("ix_workspaces_owner_id"), table_name="workspaces")
    op.drop_table("workspaces")
