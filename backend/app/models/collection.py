from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CollectionJobStatus, PlatformType


class CollectionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collection_jobs"

    platform: Mapped[str] = mapped_column(
        String(50),
        default=PlatformType.X.value,
        nullable=False,
        index=True,
    )

    job_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=CollectionJobStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    monitoring_rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitoring_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    query_value: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        index=True,
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    total_fetched: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_inserted: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_duplicates: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    cursor_before: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    cursor_after: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    job_payload: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    logs: Mapped[list["CollectionJobLog"]] = relationship(
        "CollectionJobLog",
        back_populates="collection_job",
        cascade="all, delete-orphan",
    )

    posts: Mapped[list["SocialPost"]] = relationship(
        "SocialPost",
        back_populates="collection_job",
    )

    __table_args__ = (
        Index("ix_collection_jobs_platform_status", "platform", "status"),
        Index("ix_collection_jobs_platform_started_at", "platform", "started_at"),
        Index("ix_collection_jobs_rule_started_at", "monitoring_rule_id", "started_at"),
    )


class CollectionJobLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "collection_job_logs"

    collection_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    level: Mapped[str] = mapped_column(
        String(50),
        default="info",
        nullable=False,
        index=True,
    )

    event_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    payload: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    collection_job: Mapped["CollectionJob"] = relationship(
        "CollectionJob",
        back_populates="logs",
    )

    __table_args__ = (
        Index("ix_collection_job_logs_job_level", "collection_job_id", "level"),
        Index("ix_collection_job_logs_job_occurred_at", "collection_job_id", "occurred_at"),
    )
