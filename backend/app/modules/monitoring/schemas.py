from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MonitoringRuleType, MonitoringTargetType, PlatformType


class MonitoringRuleCreate(BaseModel):
    platform: PlatformType = PlatformType.X
    rule_type: MonitoringRuleType
    target_type: MonitoringTargetType
    value: str = Field(min_length=1, max_length=500)
    language: Optional[str] = Field(default=None, max_length=20)
    is_active: bool = True


class MonitoringRuleUpdate(BaseModel):
    platform: Optional[PlatformType] = None
    rule_type: Optional[MonitoringRuleType] = None
    target_type: Optional[MonitoringTargetType] = None
    value: Optional[str] = Field(default=None, min_length=1, max_length=500)
    language: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = None


class MonitoringRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    rule_type: str
    target_type: str
    value: str
    normalized_value: str
    language: Optional[str]
    is_active: bool
    created_by_user_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class MonitoringRuleListResponse(BaseModel):
    success: bool = True
    message: str = "Monitoring rules loaded successfully"
    items: list[MonitoringRuleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
