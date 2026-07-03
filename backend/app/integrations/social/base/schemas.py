from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class SocialAuthorData:
    platform: str
    external_author_id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    raw_payload: Optional[dict[str, Any]] = None


@dataclass
class SocialPostData:
    platform: str
    external_post_id: str
    raw_text: str
    author: Optional[SocialAuthorData] = None
    clean_text: Optional[str] = None
    language: Optional[str] = None
    source_url: Optional[str] = None
    conversation_id: Optional[str] = None
    parent_external_post_id: Optional[str] = None
    published_at: Optional[datetime] = None
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    quote_count: int = 0
    view_count: int = 0
    raw_payload: Optional[dict[str, Any]] = None
    matched_values: list[str] = field(default_factory=list)


@dataclass
class CollectionRequest:
    platform: str
    query_values: list[str]
    max_items: int
    sort: str = "Latest"
    language: Optional[str] = None


@dataclass
class CollectionResult:
    platform: str
    query_values: list[str]
    total_fetched: int
    posts: list[SocialPostData]
    raw_response: Optional[Any] = None
