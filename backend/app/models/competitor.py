from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class Competitor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "competitors"

    name_en: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    name_ar: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    normalized_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    aliases: Mapped[list["CompetitorAlias"]] = relationship(
        "CompetitorAlias",
        back_populates="competitor",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_competitors_normalized_name"),
        Index("ix_competitors_name_en", "name_en"),
        Index("ix_competitors_name_ar", "name_ar"),
    )


class CompetitorAlias(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "competitor_aliases"

    competitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    alias: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    normalized_alias: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    language: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    competitor: Mapped["Competitor"] = relationship(
        "Competitor",
        back_populates="aliases",
    )

    __table_args__ = (
        UniqueConstraint(
            "competitor_id",
            "normalized_alias",
            name="uq_competitor_aliases_competitor_id_normalized_alias",
        ),
        Index("ix_competitor_aliases_normalized_alias", "normalized_alias"),
    )
