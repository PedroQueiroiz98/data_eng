from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nbplatform.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from nbplatform.domain.enums import TaskType, WorkflowStatus


class Workflow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflows"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, native_enum=False, length=20),
        default=WorkflowStatus.DRAFT,
        nullable=False,
        index=True,
    )

    tasks: Mapped[list[WorkflowTask]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    dependencies: Mapped[list[WorkflowDependency]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_tasks"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[TaskType] = mapped_column(
        Enum(TaskType, native_enum=False, length=20),
        default=TaskType.NOTEBOOK,
        nullable=False,
    )
    notebook_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notebooks.id", ondelete="RESTRICT"), index=True
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    timeout_s: Mapped[int | None] = mapped_column(Integer)
    max_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    workflow: Mapped[Workflow] = relationship(back_populates="tasks")


class WorkflowDependency(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workflow_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id", "from_task_id", "to_task_id", name="uq_workflow_edge"
        ),
    )

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    workflow: Mapped[Workflow] = relationship(back_populates="dependencies")
