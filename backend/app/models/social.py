from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PlatformType


class SocialAuthor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "social_authors"

    platform: Mapped[str] = mapped_column(
        String(50),
        default=PlatformType.X.value,
        nullable=False,
        index=True,
    )

    external_author_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    display_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    profile_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    raw_payload: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    posts: Mapped[list["SocialPost"]] = relationship(
        "SocialPost",
        back_populates="author",
    )

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "external_author_id",
            name="uq_social_authors_platform_external_author_id",
        ),
        Index("ix_social_authors_platform_username", "platform", "username"),
    )


class SocialPost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "social_posts"

    platform: Mapped[str] = mapped_column(
        String(50),
        default=PlatformType.X.value,
        nullable=False,
        index=True,
    )

    external_post_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_authors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    collection_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collection_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    clean_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    language: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )

    source_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    conversation_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    parent_external_post_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    like_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    reply_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    repost_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    quote_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    view_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    raw_payload: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    author: Mapped[Optional["SocialAuthor"]] = relationship(
        "SocialAuthor",
        back_populates="posts",
    )

    collection_job: Mapped[Optional["CollectionJob"]] = relationship(
        "CollectionJob",
        back_populates="posts",
    )

    matches: Mapped[list["PostMatch"]] = relationship(
        "PostMatch",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "external_post_id",
            name="uq_social_posts_platform_external_post_id",
        ),
        Index("ix_social_posts_platform_published_at", "platform", "published_at"),
        Index("ix_social_posts_platform_collected_at", "platform", "collected_at"),
        Index("ix_social_posts_language_collected_at", "language", "collected_at"),
    )


class PostMatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "post_matches"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    monitoring_rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitoring_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    matched_value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    matched_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    post: Mapped["SocialPost"] = relationship(
        "SocialPost",
        back_populates="matches",
    )

    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "monitoring_rule_id",
            "matched_value",
            name="uq_post_matches_post_id_monitoring_rule_id_matched_value",
        ),
        Index("ix_post_matches_monitoring_rule_id_post_id", "monitoring_rule_id", "post_id"),
    )
