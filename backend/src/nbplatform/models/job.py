from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nbplatform.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from nbplatform.domain.enums import JobStatus, JobTaskStatus, LogLevel, TriggerType


class Job(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_wf_created", "workflow_id", "created_at"),)

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=20),
        default=JobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    trigger_type: Mapped[TriggerType] = mapped_column(
        Enum(TriggerType, native_enum=False, length=20),
        default=TriggerType.MANUAL,
        nullable=False,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)

    tasks: Mapped[list[JobTask]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobTask(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_tasks"
    __table_args__ = (Index("ix_job_tasks_job_status", "job_id", "status"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    workflow_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_tasks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[JobTaskStatus] = mapped_column(
        Enum(JobTaskStatus, native_enum=False, length=20),
        default=JobTaskStatus.PENDING,
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    error_message: Mapped[str | None] = mapped_column(Text)

    job: Mapped[Job] = relationship(back_populates="tasks")


class JobLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_logs"
    __table_args__ = (Index("ix_job_logs_job_seq", "job_id", "seq"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    job_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_tasks.id", ondelete="CASCADE"), index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL")
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, native_enum=False, length=10), default=LogLevel.INFO, nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
