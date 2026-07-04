from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.ai.topics.rule_based import BaselineArabicTopicClassifier, TopicPrediction
from app.models.ai_analysis import AIAnalysisResult, PostTopic
from app.models.social import SocialPost
from app.models.topic import TopicCategory


@dataclass
class TopicClassificationSummary:
    total_candidates: int
    processed: int
    inserted: int
    skipped: int
    errors: int
    dry_run: bool

    def to_dict(self) -> dict:
        return asdict(self)


class SocialPostTopicClassificationService:
    """
    Classifies collected posts into configured management topic categories.

    Business purpose:
    Enables executive dashboards to answer:
    - What services are being discussed?
    - Which issues are increasing?
    - Which areas need management attention?
    """

    PIPELINE_VERSION = "topic-baseline-ar-v1"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.classifier = BaselineArabicTopicClassifier()
        self.post_topic_columns = {
            column.name for column in inspect(PostTopic).columns
        }
        self.analysis_columns = {
            column.name for column in inspect(AIAnalysisResult).columns
        }
        self.topic_columns = {
            column.name for column in inspect(TopicCategory).columns
        }

    def _topic_lookup(self) -> dict[str, TopicCategory]:
        topics = self.db.query(TopicCategory).all()
        lookup: dict[str, TopicCategory] = {}

        for topic in topics:
            if "slug" in self.topic_columns and getattr(topic, "slug", None):
                lookup[str(topic.slug).lower()] = topic

            if "name_en" in self.topic_columns and getattr(topic, "name_en", None):
                lookup[str(topic.name_en).strip().lower().replace(" ", "_")] = topic

            if "name_ar" in self.topic_columns and getattr(topic, "name_ar", None):
                lookup[str(topic.name_ar).strip().lower()] = topic

        return lookup

    def _get_topic_for_prediction(
        self,
        prediction: TopicPrediction,
        topic_lookup: dict[str, TopicCategory],
    ) -> Optional[TopicCategory]:
        possible_keys = [
            prediction.slug,
            prediction.label.strip().lower().replace(" ", "_"),
            prediction.label.strip().lower(),
        ]

        for key in possible_keys:
            topic = topic_lookup.get(key)
            if topic:
                return topic

        return topic_lookup.get("other")

    def _latest_analysis_result(self, post_id) -> Optional[AIAnalysisResult]:
        query = self.db.query(AIAnalysisResult).filter(
            AIAnalysisResult.post_id == post_id
        )

        if "is_current" in self.analysis_columns:
            current = query.filter(AIAnalysisResult.is_current.is_(True)).first()
            if current:
                return current

        if "analyzed_at" in self.analysis_columns:
            return query.order_by(AIAnalysisResult.analyzed_at.desc()).first()

        return query.first()

    def build_post_query(
        self,
        platform: Optional[str] = "x",
        only_unclassified: bool = True,
        post_id: Optional[UUID] = None,
    ):
        query = self.db.query(SocialPost)

        if platform:
            query = query.filter(SocialPost.platform == platform)

        if post_id:
            query = query.filter(SocialPost.id == post_id)

        query = query.filter(SocialPost.clean_text.isnot(None))

        if only_unclassified:
            classified_post_ids_query = self.db.query(PostTopic.post_id)
            query = query.filter(~SocialPost.id.in_(classified_post_ids_query))

        return query

    def _delete_existing_post_topics(self, post_id) -> None:
        self.db.query(PostTopic).filter(PostTopic.post_id == post_id).delete(
            synchronize_session=False
        )

    def _filtered_post_topic_payload(self, payload: dict) -> dict:
        return {
            key: value
            for key, value in payload.items()
            if key in self.post_topic_columns
        }

    def _build_post_topic_payload(
        self,
        post: SocialPost,
        topic: TopicCategory,
        analysis_result: Optional[AIAnalysisResult],
        prediction: TopicPrediction,
        is_primary: bool,
    ) -> dict:
        candidate_payload = {
            "post_id": post.id,
            "topic_id": topic.id,
            "analysis_result_id": analysis_result.id if analysis_result else None,
            "confidence": prediction.confidence,
            "is_primary": is_primary,
        }

        return self._filtered_post_topic_payload(candidate_payload)

    def classify_post(
        self,
        post: SocialPost,
        topic_lookup: dict[str, TopicCategory],
        dry_run: bool = False,
    ) -> int:
        text_for_classification = post.clean_text or post.raw_text or ""
        predictions = self.classifier.classify(text_for_classification)

        if dry_run:
            logger.info(
                "Dry run topic classification | post_id={} | topics={} | text={}",
                post.id,
                [prediction.to_dict() for prediction in predictions],
                text_for_classification[:120],
            )
            return len(predictions)

        analysis_result = self._latest_analysis_result(post.id)

        # Reclassification should replace old topic rows.
        self._delete_existing_post_topics(post.id)

        inserted = 0

        for index, prediction in enumerate(predictions):
            topic = self._get_topic_for_prediction(
                prediction=prediction,
                topic_lookup=topic_lookup,
            )

            if not topic:
                logger.warning(
                    "Topic category not found | post_id={} | prediction={}",
                    post.id,
                    prediction.to_dict(),
                )
                continue

            payload = self._build_post_topic_payload(
                post=post,
                topic=topic,
                analysis_result=analysis_result,
                prediction=prediction,
                is_primary=index == 0,
            )

            self.db.add(PostTopic(**payload))
            inserted += 1

        return inserted

    def classify_posts(
        self,
        platform: Optional[str] = "x",
        limit: int = 100,
        only_unclassified: bool = True,
        dry_run: bool = False,
    ) -> TopicClassificationSummary:
        topic_lookup = self._topic_lookup()

        if not topic_lookup:
            raise ValueError("No topic categories found. Seed topic categories first.")

        query = self.build_post_query(
            platform=platform,
            only_unclassified=only_unclassified,
        )

        total_candidates = query.count()

        posts = (
            query.order_by(SocialPost.collected_at.desc())
            .limit(limit)
            .all()
        )

        processed = 0
        inserted = 0
        skipped = 0
        errors = 0

        for post in posts:
            processed += 1

            try:
                inserted_for_post = self.classify_post(
                    post=post,
                    topic_lookup=topic_lookup,
                    dry_run=dry_run,
                )

                if inserted_for_post:
                    inserted += inserted_for_post
                else:
                    skipped += 1

            except Exception as exc:
                errors += 1
                logger.exception(
                    "Failed to classify topics | post_id={} | error={}",
                    post.id,
                    str(exc),
                )

        if not dry_run:
            self.db.commit()

        summary = TopicClassificationSummary(
            total_candidates=total_candidates,
            processed=processed,
            inserted=inserted,
            skipped=skipped,
            errors=errors,
            dry_run=dry_run,
        )

        logger.info("Topic classification completed | summary={}", summary.to_dict())

        return summary

    def classify_single_post(
        self,
        post_id: UUID,
        dry_run: bool = False,
    ) -> dict:
        topic_lookup = self._topic_lookup()

        post = self.build_post_query(
            platform=None,
            only_unclassified=False,
            post_id=post_id,
        ).first()

        if not post:
            raise ValueError("Post not found or clean_text is missing.")

        predictions = self.classifier.classify(post.clean_text or post.raw_text or "")

        if not dry_run:
            self.classify_post(
                post=post,
                topic_lookup=topic_lookup,
                dry_run=False,
            )
            self.db.commit()

        return {
            "post_id": str(post.id),
            "external_post_id": post.external_post_id,
            "text": post.clean_text or post.raw_text,
            "topics": [prediction.to_dict() for prediction in predictions],
            "dry_run": dry_run,
        }
