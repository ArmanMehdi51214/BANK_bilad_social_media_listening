from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import MonitoringTargetType


class XManualCollectionRequest(BaseModel):
    max_items: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of X posts to fetch in this manual run.",
    )
    sort: str = Field(
        default="Latest",
        description="Apify/X sorting mode. Use Latest for monitoring.",
    )
    target_types: Optional[list[str]] = Field(
        default_factory=lambda: [MonitoringTargetType.BRAND.value],
        description="Monitoring target types to collect. Default is brand monitoring.",
    )
    rule_ids: Optional[list[UUID]] = Field(
        default=None,
        description="Optional specific monitoring rule IDs to collect.",
    )


class XManualCollectionResponse(BaseModel):
    job_id: str
    status: str
    total_fetched: int
    mapped_posts: int
    inserted: int
    duplicates: int
    matches_created: int


class CollectionJobListItem(BaseModel):
    id: str
    platform: str
    job_type: str
    status: str
    query_value: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total_fetched: int = 0
    total_inserted: int = 0
    total_duplicates: int = 0
    total_errors: int = 0
    error_message: Optional[str] = None


class CollectionJobListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CollectionJobListItem]


class CollectionJobDetailResponse(CollectionJobListItem):
    monitoring_rule_id: Optional[str] = None
    cursor_before: Optional[str] = None
    cursor_after: Optional[str] = None
    job_payload: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CollectionJobLogItem(BaseModel):
    id: str
    collection_job_id: str
    level: str
    event_type: str
    message: str
    payload: Optional[dict] = None
    occurred_at: Optional[datetime] = None


class CollectionJobLogsResponse(BaseModel):
    job_id: str
    total: int
    items: list[CollectionJobLogItem]


class CollectedPostAuthor(BaseModel):
    id: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_url: Optional[str] = None


class CollectedPostMatch(BaseModel):
    id: str
    monitoring_rule_id: str
    matched_value: str
    matched_text: Optional[str] = None


class CollectedPostListItem(BaseModel):
    id: str
    platform: str
    external_post_id: str
    raw_text: str
    language: Optional[str] = None
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    quote_count: int = 0
    view_count: int = 0
    author: Optional[CollectedPostAuthor] = None
    matches_count: int = 0


class CollectedPostListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CollectedPostListItem]


class CollectedPostDetailResponse(CollectedPostListItem):
    clean_text: Optional[str] = None
    conversation_id: Optional[str] = None
    parent_external_post_id: Optional[str] = None
    collection_job_id: Optional[str] = None
    raw_payload: Optional[dict] = None
    matches: list[CollectedPostMatch] = Field(default_factory=list)
