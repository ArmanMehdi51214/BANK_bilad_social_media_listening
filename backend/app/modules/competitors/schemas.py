from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompetitorAliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=255)
    language: Optional[str] = Field(default=None, max_length=20)
    is_active: bool = True


class CompetitorAliasUpdate(BaseModel):
    alias: Optional[str] = Field(default=None, min_length=1, max_length=255)
    language: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = None


class CompetitorAliasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    competitor_id: UUID
    alias: str
    normalized_alias: str
    language: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CompetitorCreate(BaseModel):
    name_en: str = Field(min_length=1, max_length=255)
    name_ar: Optional[str] = Field(default=None, max_length=255)
    aliases: list[CompetitorAliasCreate] = []
    is_active: bool = True
    create_monitoring_rules: bool = True


class CompetitorUpdate(BaseModel):
    name_en: Optional[str] = Field(default=None, min_length=1, max_length=255)
    name_ar: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None


class CompetitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name_en: str
    name_ar: Optional[str]
    normalized_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    aliases: list[CompetitorAliasResponse] = []


class CompetitorListResponse(BaseModel):
    success: bool = True
    message: str = "Competitors loaded successfully"
    items: list[CompetitorResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
