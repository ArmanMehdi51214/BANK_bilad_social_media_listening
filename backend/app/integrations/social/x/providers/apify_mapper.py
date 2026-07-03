from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Optional

from app.integrations.social.base.schemas import SocialAuthorData, SocialPostData
from app.models.enums import PlatformType


class ApifyTweetMapper:
    @staticmethod
    def normalize_text(value: str) -> str:
        value = unicodedata.normalize("NFKC", value or "")
        value = value.strip().lower()
        value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        value = value.replace("ى", "ي").replace("ة", "ه").replace("ـ", "")
        value = re.sub(r"\s+", " ", value)
        return value

    @staticmethod
    def clean_query_value(value: str) -> str:
        value = (value or "").strip()
        value = value.strip('"').strip("'")
        return value

    @staticmethod
    def parse_twitter_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except Exception:
            return None

    @staticmethod
    def safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def extract_matched_values(self, raw_text: str, query_values: list[str]) -> list[str]:
        normalized_text = self.normalize_text(raw_text)
        matched = []

        for query in query_values:
            clean_query = self.clean_query_value(query)
            normalized_query = self.normalize_text(clean_query)

            if normalized_query and normalized_query in normalized_text:
                matched.append(clean_query)

        return matched

    def map_author(self, item: dict[str, Any]) -> Optional[SocialAuthorData]:
        author = item.get("author")

        if not isinstance(author, dict):
            return None

        external_author_id = str(author.get("id") or "").strip()

        if not external_author_id:
            return None

        return SocialAuthorData(
            platform=PlatformType.X.value,
            external_author_id=external_author_id,
            username=author.get("userName"),
            display_name=author.get("name"),
            profile_url=author.get("url") or author.get("twitterUrl"),
            raw_payload=author,
        )

    def map_post(
        self,
        item: dict[str, Any],
        query_values: list[str],
    ) -> Optional[SocialPostData]:
        if not isinstance(item, dict):
            return None

        if item.get("noResults") is True:
            return None

        if item.get("type") and item.get("type") != "tweet":
            return None

        external_post_id = str(item.get("id") or "").strip()

        if not external_post_id:
            return None

        raw_text = item.get("fullText") or item.get("text") or ""

        if not raw_text.strip():
            return None

        return SocialPostData(
            platform=PlatformType.X.value,
            external_post_id=external_post_id,
            raw_text=raw_text,
            clean_text=None,
            author=self.map_author(item),
            language=item.get("lang"),
            source_url=item.get("url") or item.get("twitterUrl"),
            conversation_id=str(item.get("conversationId")) if item.get("conversationId") else None,
            parent_external_post_id=str(item.get("inReplyToId")) if item.get("inReplyToId") else None,
            published_at=self.parse_twitter_datetime(item.get("createdAt")),
            like_count=self.safe_int(item.get("likeCount")),
            reply_count=self.safe_int(item.get("replyCount")),
            repost_count=self.safe_int(item.get("retweetCount")),
            quote_count=self.safe_int(item.get("quoteCount")),
            view_count=self.safe_int(item.get("viewCount")),
            raw_payload=item,
            matched_values=self.extract_matched_values(raw_text, query_values),
        )

    def map_items(
        self,
        items: list[dict[str, Any]],
        query_values: list[str],
    ) -> list[SocialPostData]:
        posts = []

        for item in items:
            mapped_post = self.map_post(item, query_values)
            if mapped_post:
                posts.append(mapped_post)

        return posts
