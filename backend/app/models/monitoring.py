import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MonitoringRuleType, MonitoringTargetType, PlatformType


class MonitoringRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "monitoring_rules"

    platform: Mapped[str] = mapped_column(
        String(50),
        default=PlatformType.X.value,
        nullable=False,
        index=True,
    )

    rule_type: Mapped[str] = mapped_column(
        String(50),
        default=MonitoringRuleType.KEYWORD.value,
        nullable=False,
        index=True,
    )

    target_type: Mapped[str] = mapped_column(
        String(50),
        default=MonitoringTargetType.GENERAL.value,
        nullable=False,
        index=True,
    )

    value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    normalized_value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
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

    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "rule_type",
            "target_type",
            "normalized_value",
            name="uq_monitoring_rules_unique_value",
        ),
        Index("ix_monitoring_rules_active_platform", "is_active", "platform"),
    )
