from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.integrations.social.base.schemas import CollectionRequest, CollectionResult, SocialPostData
from app.integrations.social.factory import get_x_collector
from app.models.collection import CollectionJob, CollectionJobLog
from app.models.enums import CollectionJobStatus, PlatformType
from app.models.monitoring import MonitoringRule
from app.models.social import PostMatch, SocialAuthor, SocialPost


class XCollectionService:
    """
    Collects X/Twitter data using the configured provider and persists it.

    Responsibilities:
    - Load active monitoring rules
    - Create collection job
    - Call X collector
    - Save authors
    - Save posts
    - Save post/rule matches
    - Track inserted/duplicate/error counts

    This service does not perform AI analysis.
    AI analysis will run after posts are stored.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.collector = get_x_collector()

    @staticmethod
    def normalize_text(value: str) -> str:
        value = unicodedata.normalize("NFKC", value or "")
        value = value.strip().lower()
        value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        value = value.replace("ى", "ي").replace("ة", "ه").replace("ـ", "")
        value = re.sub(r"\s+", " ", value)
        return value

    def get_active_rules(
        self,
        target_types: Optional[list[str]] = None,
        rule_ids: Optional[list[str]] = None,
    ) -> list[MonitoringRule]:
        query = self.db.query(MonitoringRule).filter(
            MonitoringRule.platform == PlatformType.X.value,
            MonitoringRule.is_active.is_(True),
        )

        if target_types:
            query = query.filter(MonitoringRule.target_type.in_(target_types))

        if rule_ids:
            query = query.filter(MonitoringRule.id.in_(rule_ids))

        return query.order_by(MonitoringRule.created_at.asc()).all()

    def create_collection_job(
        self,
        query_values: list[str],
        max_items: int,
        sort: str,
    ) -> CollectionJob:
        now = datetime.now(timezone.utc)

        job = CollectionJob(
            platform=PlatformType.X.value,
            job_type="manual_x_collection",
            status=CollectionJobStatus.RUNNING.value,
            query_value=", ".join(query_values)[:500],
            started_at=now,
            total_fetched=0,
            total_inserted=0,
            total_duplicates=0,
            total_errors=0,
            job_payload={
                "query_values": query_values,
                "max_items": max_items,
                "sort": sort,
            },
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        self.add_job_log(
            job_id=job.id,
            level="info",
            event_type="collection_started",
            message="X collection job started.",
            payload={"query_count": len(query_values), "max_items": max_items, "sort": sort},
            commit=True,
        )

        return job

    def add_job_log(
        self,
        job_id,
        level: str,
        event_type: str,
        message: str,
        payload: Optional[dict] = None,
        commit: bool = False,
    ) -> None:
        log = CollectionJobLog(
            collection_job_id=job_id,
            level=level,
            event_type=event_type,
            message=message,
            payload=payload,
        )

        self.db.add(log)

        if commit:
            self.db.commit()

    def mark_job_failed(self, job: CollectionJob, error_message: str) -> None:
        self.db.rollback()

        job.status = CollectionJobStatus.FAILED.value
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = error_message
        job.total_errors = (job.total_errors or 0) + 1

        self.add_job_log(
            job_id=job.id,
            level="error",
            event_type="collection_failed",
            message=error_message,
            payload=None,
            commit=False,
        )

        self.db.commit()

    def get_or_create_author(self, post_data: SocialPostData) -> Optional[SocialAuthor]:
        if not post_data.author:
            return None

        author_data = post_data.author

        author = (
            self.db.query(SocialAuthor)
            .filter(
                SocialAuthor.platform == author_data.platform,
                SocialAuthor.external_author_id == author_data.external_author_id,
            )
            .first()
        )

        if not author:
            author = SocialAuthor(
                platform=author_data.platform,
                external_author_id=author_data.external_author_id,
                username=author_data.username,
                display_name=author_data.display_name,
                profile_url=author_data.profile_url,
                raw_payload=author_data.raw_payload,
            )
            self.db.add(author)
            self.db.flush()
            return author

        author.username = author_data.username
        author.display_name = author_data.display_name
        author.profile_url = author_data.profile_url
        author.raw_payload = author_data.raw_payload

        return author

    def save_or_update_post(
        self,
        post_data: SocialPostData,
        collection_job: CollectionJob,
    ) -> tuple[SocialPost, bool]:
        existing_post = (
            self.db.query(SocialPost)
            .filter(
                SocialPost.platform == post_data.platform,
                SocialPost.external_post_id == post_data.external_post_id,
            )
            .first()
        )

        author = self.get_or_create_author(post_data)

        if existing_post:
            existing_post.like_count = post_data.like_count
            existing_post.reply_count = post_data.reply_count
            existing_post.repost_count = post_data.repost_count
            existing_post.quote_count = post_data.quote_count
            existing_post.view_count = post_data.view_count
            existing_post.raw_payload = post_data.raw_payload
            existing_post.clean_text = post_data.clean_text
            existing_post.language = post_data.language
            existing_post.source_url = post_data.source_url

            if author:
                existing_post.author_id = author.id

            self.db.flush()
            return existing_post, False

        new_post = SocialPost(
            platform=post_data.platform,
            external_post_id=post_data.external_post_id,
            author_id=author.id if author else None,
            collection_job_id=collection_job.id,
            raw_text=post_data.raw_text,
            clean_text=post_data.clean_text,
            language=post_data.language,
            source_url=post_data.source_url,
            conversation_id=post_data.conversation_id,
            parent_external_post_id=post_data.parent_external_post_id,
            published_at=post_data.published_at,
            collected_at=datetime.now(timezone.utc),
            like_count=post_data.like_count,
            reply_count=post_data.reply_count,
            repost_count=post_data.repost_count,
            quote_count=post_data.quote_count,
            view_count=post_data.view_count,
            raw_payload=post_data.raw_payload,
        )

        self.db.add(new_post)
        self.db.flush()

        return new_post, True

    def save_post_matches(
        self,
        post: SocialPost,
        post_data: SocialPostData,
        rules_by_normalized_value: dict[str, list[MonitoringRule]],
    ) -> int:
        created_count = 0

        for matched_value in post_data.matched_values:
            normalized_value = self.normalize_text(matched_value)
            matching_rules = rules_by_normalized_value.get(normalized_value, [])

            for rule in matching_rules:
                existing_match = (
                    self.db.query(PostMatch)
                    .filter(
                        PostMatch.post_id == post.id,
                        PostMatch.monitoring_rule_id == rule.id,
                        PostMatch.matched_value == rule.value,
                    )
                    .first()
                )

                if existing_match:
                    continue

                match = PostMatch(
                    post_id=post.id,
                    monitoring_rule_id=rule.id,
                    matched_value=rule.value,
                    matched_text=matched_value,
                )

                self.db.add(match)
                created_count += 1

        return created_count

    def save_collection_result(
        self,
        collection_job: CollectionJob,
        result: CollectionResult,
        rules: list[MonitoringRule],
    ) -> dict:
        inserted_count = 0
        duplicate_count = 0
        match_count = 0

        rules_by_normalized_value: dict[str, list[MonitoringRule]] = {}

        for rule in rules:
            rules_by_normalized_value.setdefault(rule.normalized_value, []).append(rule)

        for post_data in result.posts:
            post, inserted = self.save_or_update_post(
                post_data=post_data,
                collection_job=collection_job,
            )

            if inserted:
                inserted_count += 1
            else:
                duplicate_count += 1

            match_count += self.save_post_matches(
                post=post,
                post_data=post_data,
                rules_by_normalized_value=rules_by_normalized_value,
            )

        collection_job.status = CollectionJobStatus.SUCCESS.value
        collection_job.finished_at = datetime.now(timezone.utc)
        collection_job.total_fetched = result.total_fetched
        collection_job.total_inserted = inserted_count
        collection_job.total_duplicates = duplicate_count
        collection_job.total_errors = 0

        self.add_job_log(
            job_id=collection_job.id,
            level="info",
            event_type="collection_completed",
            message="X collection job completed successfully.",
            payload={
                "total_fetched": result.total_fetched,
                "mapped_posts": len(result.posts),
                "inserted": inserted_count,
                "duplicates": duplicate_count,
                "matches_created": match_count,
            },
            commit=False,
        )

        self.db.commit()

        return {
            "job_id": str(collection_job.id),
            "status": collection_job.status,
            "total_fetched": result.total_fetched,
            "mapped_posts": len(result.posts),
            "inserted": inserted_count,
            "duplicates": duplicate_count,
            "matches_created": match_count,
        }

    async def collect_active_rules(
        self,
        max_items: int = 10,
        sort: str = "Latest",
        target_types: Optional[list[str]] = None,
        rule_ids: Optional[list[str]] = None,
    ) -> dict:
        rules = self.get_active_rules(
            target_types=target_types,
            rule_ids=rule_ids,
        )

        if not rules:
            raise ValueError("No active X monitoring rules found.")

        query_values = [rule.value for rule in rules]

        collection_job = self.create_collection_job(
            query_values=query_values,
            max_items=max_items,
            sort=sort,
        )

        try:
            result = await self.collector.collect(
                CollectionRequest(
                    platform=PlatformType.X.value,
                    query_values=query_values,
                    max_items=max_items,
                    sort=sort,
                )
            )

            summary = self.save_collection_result(
                collection_job=collection_job,
                result=result,
                rules=rules,
            )

            logger.info("X collection saved successfully | summary={}", summary)

            return summary

        except Exception as exc:
            error_message = str(exc)
            self.mark_job_failed(collection_job, error_message)
            logger.exception("X collection failed")
            raise
