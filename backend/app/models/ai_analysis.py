from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AIAnalysisStatus, EntityType, SentimentLabel


class AIAnalysisResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_analysis_results"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=AIAnalysisStatus.COMPLETED.value,
        nullable=False,
        index=True,
    )

    sentiment_label: Mapped[str] = mapped_column(
        String(50),
        default=SentimentLabel.UNKNOWN.value,
        nullable=False,
        index=True,
    )

    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sentiment_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    is_complaint: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    complaint_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    pipeline_version: Mapped[str] = mapped_column(
        String(100),
        default="v1",
        nullable=False,
        index=True,
    )

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    topics: Mapped[list["PostTopic"]] = relationship(
        "PostTopic",
        back_populates="analysis_result",
        cascade="all, delete-orphan",
    )

    entities: Mapped[list["PostEntity"]] = relationship(
        "PostEntity",
        back_populates="analysis_result",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_ai_analysis_results_post_current", "post_id", "is_current"),
        Index("ix_ai_analysis_results_sentiment_current", "sentiment_label", "is_current"),
        Index("ix_ai_analysis_results_complaint_current", "is_complaint", "is_current"),
    )


class PostTopic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "post_topics"

    analysis_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_analysis_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topic_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    analysis_result: Mapped["AIAnalysisResult"] = relationship(
        "AIAnalysisResult",
        back_populates="topics",
    )

    __table_args__ = (
        Index("ix_post_topics_post_primary", "post_id", "is_primary"),
        Index("ix_post_topics_topic_confidence", "topic_id", "confidence"),
    )


class PostEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "post_entities"

    analysis_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_analysis_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        default=EntityType.OTHER.value,
        nullable=False,
        index=True,
    )

    value: Mapped[str] = mapped_column(String(500), nullable=False)

    normalized_value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    competitor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competitors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    start_char: Mapped[Optional[int]] = mapped_column(nullable=True)
    end_char: Mapped[Optional[int]] = mapped_column(nullable=True)

    analysis_result: Mapped["AIAnalysisResult"] = relationship(
        "AIAnalysisResult",
        back_populates="entities",
    )

    __table_args__ = (
        Index("ix_post_entities_post_type", "post_id", "entity_type"),
        Index("ix_post_entities_type_normalized", "entity_type", "normalized_value"),
        Index("ix_post_entities_competitor_post", "competitor_id", "post_id"),
    )
