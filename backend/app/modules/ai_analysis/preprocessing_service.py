from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.ai.preprocessing.pipeline import ArabicPreprocessingPipeline
from app.models.social import SocialPost


@dataclass
class PostPreprocessingSummary:
    total_candidates: int
    processed: int
    updated: int
    skipped: int
    errors: int
    dry_run: bool

    def to_dict(self) -> dict:
        return asdict(self)


class SocialPostPreprocessingService:
    """
    Applies Arabic preprocessing to collected social posts.

    Business purpose:
    Converts raw social media text into clean text that can be used by
    sentiment analysis, topic classification, complaint detection, and reporting.

    Important:
    - raw_text remains unchanged for auditability.
    - clean_text stores repaired, PII-masked, AI-ready text.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.pipeline = ArabicPreprocessingPipeline()

    def build_query(
        self,
        platform: Optional[str] = None,
        only_unprocessed: bool = True,
        post_id: Optional[UUID] = None,
    ):
        query = self.db.query(SocialPost)

        if platform:
            query = query.filter(SocialPost.platform == platform)

        if post_id:
            query = query.filter(SocialPost.id == post_id)

        if only_unprocessed:
            query = query.filter(SocialPost.clean_text.is_(None))

        return query

    def preprocess_post(
        self,
        post: SocialPost,
        dry_run: bool = False,
    ) -> bool:
        result = self.pipeline.process(post.raw_text or "")

        if not result.clean_text:
            return False

        if dry_run:
            logger.info(
                "Dry run preprocessing | post_id={} | clean_text={}",
                post.id,
                result.clean_text[:120],
            )
            return True

        post.clean_text = result.clean_text

        # Provider language is preferred, but if missing we fill it.
        if not post.language or post.language == "unknown":
            post.language = result.detected_language

        return True

    def preprocess_posts(
        self,
        platform: Optional[str] = "x",
        limit: int = 100,
        only_unprocessed: bool = True,
        dry_run: bool = False,
    ) -> PostPreprocessingSummary:
        query = self.build_query(
            platform=platform,
            only_unprocessed=only_unprocessed,
        )

        total_candidates = query.count()

        posts = (
            query.order_by(SocialPost.collected_at.desc())
            .limit(limit)
            .all()
        )

        processed = 0
        updated = 0
        skipped = 0
        errors = 0

        for post in posts:
            processed += 1

            try:
                changed = self.preprocess_post(post, dry_run=dry_run)

                if changed:
                    updated += 1
                else:
                    skipped += 1

            except Exception as exc:
                errors += 1
                logger.exception(
                    "Failed to preprocess post | post_id={} | error={}",
                    post.id,
                    str(exc),
                )

        if not dry_run:
            self.db.commit()

        summary = PostPreprocessingSummary(
            total_candidates=total_candidates,
            processed=processed,
            updated=updated,
            skipped=skipped,
            errors=errors,
            dry_run=dry_run,
        )

        logger.info("Post preprocessing completed | summary={}", summary.to_dict())

        return summary

    def preprocess_single_post(
        self,
        post_id: UUID,
        dry_run: bool = False,
    ) -> dict:
        post = self.build_query(
            only_unprocessed=False,
            post_id=post_id,
        ).first()

        if not post:
            raise ValueError("Post not found.")

        result = self.pipeline.process(post.raw_text or "")

        if not dry_run:
            post.clean_text = result.clean_text

            if not post.language or post.language == "unknown":
                post.language = result.detected_language

            self.db.commit()

        return {
            "post_id": str(post.id),
            "platform": post.platform,
            "raw_text": post.raw_text,
            "clean_text": result.clean_text,
            "normalized_text": result.normalized_text,
            "detected_language": result.detected_language,
            "hashtags": result.hashtags,
            "mentions": result.mentions,
            "urls": result.urls,
            "contains_pii": result.contains_pii,
            "pii_types": result.pii_types,
            "dry_run": dry_run,
        }
