from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.social import PostMatch, SocialAuthor, SocialPost


class CollectedPostService:
    """
    Read-only service for collected posts.

    Business purpose:
    Provides the dashboard/live-feed layer with searchable social media posts
    collected from X and stored in the historical archive.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_posts(
        self,
        platform: Optional[str] = None,
        language: Optional[str] = None,
        search: Optional[str] = None,
        collection_job_id: Optional[UUID] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[SocialPost]]:
        query = self.db.query(SocialPost)

        if platform:
            query = query.filter(SocialPost.platform == platform)

        if language:
            query = query.filter(SocialPost.language == language)

        if collection_job_id:
            query = query.filter(SocialPost.collection_job_id == collection_job_id)

        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    SocialPost.raw_text.ilike(pattern),
                    SocialPost.clean_text.ilike(pattern),
                )
            )

        total = query.count()

        posts = (
            query.order_by(
                SocialPost.published_at.desc().nullslast(),
                SocialPost.collected_at.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        return total, posts

    def get_post(self, post_id: UUID) -> Optional[SocialPost]:
        return self.db.query(SocialPost).filter(SocialPost.id == post_id).first()

    def get_author(self, author_id) -> Optional[SocialAuthor]:
        if not author_id:
            return None

        return self.db.query(SocialAuthor).filter(SocialAuthor.id == author_id).first()

    def count_matches(self, post_id) -> int:
        return (
            self.db.query(func.count(PostMatch.id))
            .filter(PostMatch.post_id == post_id)
            .scalar()
            or 0
        )

    def get_matches(self, post_id) -> list[PostMatch]:
        return (
            self.db.query(PostMatch)
            .filter(PostMatch.post_id == post_id)
            .order_by(PostMatch.created_at.asc())
            .all()
        )
