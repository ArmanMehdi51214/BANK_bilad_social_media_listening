from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.ai.sentiment.rule_based import BaselineArabicSentimentAnalyzer
from app.models.ai_analysis import AIAnalysisResult
from app.models.social import SocialPost


@dataclass
class SentimentAnalysisSummary:
    total_candidates: int
    processed: int
    inserted: int
    skipped: int
    errors: int
    dry_run: bool

    def to_dict(self) -> dict:
        return asdict(self)


class SocialPostSentimentAnalysisService:
    """
    Runs baseline sentiment analysis on collected social posts and saves results.

    Business purpose:
    Converts cleaned customer conversations into management reporting signals.
    This baseline engine is model-independent and can later be replaced with
    MARBERT/AraBERT without changing API/database contracts.
    """

    PIPELINE_VERSION = "sentiment-baseline-ar-v1"
    MODEL_NAME = "rule_based_arabic_sentiment"
    MODEL_VERSION = "1.0.0"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.analyzer = BaselineArabicSentimentAnalyzer()
        self.analysis_columns = {
            column.name for column in inspect(AIAnalysisResult).columns
        }

    def _success_status(self) -> str:
        try:
            from app.models.enums import AIAnalysisStatus

            for name in ("SUCCESS", "COMPLETED", "DONE"):
                if hasattr(AIAnalysisStatus, name):
                    return getattr(AIAnalysisStatus, name).value
        except Exception:
            pass

        return "success"

    def build_post_query(
        self,
        platform: Optional[str] = "x",
        only_unanalyzed: bool = True,
        post_id: Optional[UUID] = None,
    ):
        query = self.db.query(SocialPost)

        if platform:
            query = query.filter(SocialPost.platform == platform)

        if post_id:
            query = query.filter(SocialPost.id == post_id)

        query = query.filter(SocialPost.clean_text.isnot(None))

        if only_unanalyzed:
            analyzed_post_ids_query = self.db.query(AIAnalysisResult.post_id)

            if "is_current" in self.analysis_columns:
                analyzed_post_ids_query = analyzed_post_ids_query.filter(
                    AIAnalysisResult.is_current.is_(True)
                )

            if "sentiment_label" in self.analysis_columns:
                analyzed_post_ids_query = analyzed_post_ids_query.filter(
                    AIAnalysisResult.sentiment_label.isnot(None)
                )

            query = query.filter(~SocialPost.id.in_(analyzed_post_ids_query))

        return query

    def _mark_previous_not_current(self, post_id) -> None:
        if "is_current" not in self.analysis_columns:
            return

        (
            self.db.query(AIAnalysisResult)
            .filter(
                AIAnalysisResult.post_id == post_id,
                AIAnalysisResult.is_current.is_(True),
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    def _filtered_payload(self, payload: dict) -> dict:
        return {
            key: value
            for key, value in payload.items()
            if key in self.analysis_columns
        }

    def _build_analysis_payload(self, post: SocialPost, sentiment_result) -> dict:
        now = datetime.now(timezone.utc)
        raw_output = sentiment_result.to_dict()

        candidate_payload = {
            "post_id": post.id,
            "status": self._success_status(),
            "pipeline_version": self.PIPELINE_VERSION,
            "model_name": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,
            "sentiment_label": sentiment_result.label,
            "sentiment_score": sentiment_result.score,
            "sentiment_confidence": sentiment_result.confidence,
            "confidence": sentiment_result.confidence,
            "confidence_score": sentiment_result.confidence,
            "sentiment_reason": sentiment_result.explanation,
            "sentiment_explanation": sentiment_result.explanation,
            "explanation": sentiment_result.explanation,
            "is_current": True,
            "is_complaint": False,
            "complaint_confidence": 0.0,
            "analyzed_at": now,
            "raw_output": raw_output,
            "raw_model_output": raw_output,
            "analysis_payload": raw_output,
            "metadata": raw_output,
            "extra_data": raw_output,
        }

        return self._filtered_payload(candidate_payload)

    def analyze_post(
        self,
        post: SocialPost,
        dry_run: bool = False,
    ) -> bool:
        text_for_analysis = post.clean_text or post.raw_text or ""
        sentiment_result = self.analyzer.analyze(text_for_analysis)

        if dry_run:
            logger.info(
                "Dry run sentiment | post_id={} | label={} | confidence={} | text={}",
                post.id,
                sentiment_result.label,
                sentiment_result.confidence,
                text_for_analysis[:120],
            )
            return True

        self._mark_previous_not_current(post.id)

        payload = self._build_analysis_payload(
            post=post,
            sentiment_result=sentiment_result,
        )

        analysis_result = AIAnalysisResult(**payload)

        self.db.add(analysis_result)

        return True

    def analyze_posts(
        self,
        platform: Optional[str] = "x",
        limit: int = 100,
        only_unanalyzed: bool = True,
        dry_run: bool = False,
    ) -> SentimentAnalysisSummary:
        query = self.build_post_query(
            platform=platform,
            only_unanalyzed=only_unanalyzed,
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
                changed = self.analyze_post(post, dry_run=dry_run)

                if changed:
                    inserted += 1
                else:
                    skipped += 1

            except Exception as exc:
                errors += 1
                logger.exception(
                    "Failed to analyze sentiment | post_id={} | error={}",
                    post.id,
                    str(exc),
                )

        if not dry_run:
            self.db.commit()

        summary = SentimentAnalysisSummary(
            total_candidates=total_candidates,
            processed=processed,
            inserted=inserted,
            skipped=skipped,
            errors=errors,
            dry_run=dry_run,
        )

        logger.info("Sentiment analysis completed | summary={}", summary.to_dict())

        return summary

    def analyze_single_post(
        self,
        post_id: UUID,
        dry_run: bool = False,
    ) -> dict:
        post = self.build_post_query(
            platform=None,
            only_unanalyzed=False,
            post_id=post_id,
        ).first()

        if not post:
            raise ValueError("Post not found or clean_text is missing.")

        text_for_analysis = post.clean_text or post.raw_text or ""
        sentiment_result = self.analyzer.analyze(text_for_analysis)

        if not dry_run:
            self._mark_previous_not_current(post.id)

            payload = self._build_analysis_payload(
                post=post,
                sentiment_result=sentiment_result,
            )

            self.db.add(AIAnalysisResult(**payload))
            self.db.commit()

        return {
            "post_id": str(post.id),
            "external_post_id": post.external_post_id,
            "text": text_for_analysis,
            "sentiment": sentiment_result.to_dict(),
            "dry_run": dry_run,
        }
