from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.ai.complaints.rule_based import BaselineArabicComplaintDetector
from app.models.ai_analysis import AIAnalysisResult
from app.models.social import SocialPost


@dataclass
class ComplaintDetectionSummary:
    total_candidates: int
    processed: int
    updated: int
    complaints_detected: int
    skipped: int
    errors: int
    dry_run: bool

    def to_dict(self) -> dict:
        return asdict(self)


class SocialPostComplaintDetectionService:
    """
    Updates ai_analysis_results with complaint detection signals.

    Business purpose:
    Helps executives identify customer issues requiring attention, not just general sentiment.
    """

    PIPELINE_VERSION = "complaint-baseline-ar-v1"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.detector = BaselineArabicComplaintDetector()

    def build_query(
        self,
        platform: Optional[str] = "x",
        only_current: bool = True,
    ):
        query = (
            self.db.query(AIAnalysisResult, SocialPost)
            .join(SocialPost, SocialPost.id == AIAnalysisResult.post_id)
            .filter(SocialPost.clean_text.isnot(None))
        )

        if platform:
            query = query.filter(SocialPost.platform == platform)

        if only_current:
            query = query.filter(AIAnalysisResult.is_current.is_(True))

        return query

    @staticmethod
    def _merge_payload(existing_payload, complaint_payload: dict) -> dict:
        if isinstance(existing_payload, dict):
            payload = dict(existing_payload)
        else:
            payload = {}

        payload["complaint_detection"] = complaint_payload

        return payload

    def detect_for_result(
        self,
        analysis_result: AIAnalysisResult,
        post: SocialPost,
        dry_run: bool = False,
    ) -> bool:
        text_for_detection = post.clean_text or post.raw_text or ""
        detection = self.detector.detect(
            text=text_for_detection,
            sentiment_label=analysis_result.sentiment_label,
        )

        payload = detection.to_dict()
        payload["pipeline_version"] = self.PIPELINE_VERSION

        if dry_run:
            logger.info(
                "Dry run complaint detection | post_id={} | is_complaint={} | confidence={} | category={} | text={}",
                post.id,
                detection.is_complaint,
                detection.confidence,
                detection.category,
                text_for_detection[:120],
            )
            return True

        analysis_result.is_complaint = detection.is_complaint
        analysis_result.complaint_confidence = detection.confidence
        analysis_result.analysis_payload = self._merge_payload(
            existing_payload=analysis_result.analysis_payload,
            complaint_payload=payload,
        )
        flag_modified(analysis_result, "analysis_payload")

        return True

    def detect_complaints(
        self,
        platform: Optional[str] = "x",
        limit: int = 100,
        dry_run: bool = False,
    ) -> ComplaintDetectionSummary:
        query = self.build_query(platform=platform)

        total_candidates = query.count()

        rows = (
            query.order_by(SocialPost.collected_at.desc())
            .limit(limit)
            .all()
        )

        processed = 0
        updated = 0
        complaints_detected = 0
        skipped = 0
        errors = 0

        for analysis_result, post in rows:
            processed += 1

            try:
                changed = self.detect_for_result(
                    analysis_result=analysis_result,
                    post=post,
                    dry_run=dry_run,
                )

                if changed:
                    updated += 1

                    if not dry_run and analysis_result.is_complaint:
                        complaints_detected += 1
                else:
                    skipped += 1

            except Exception as exc:
                errors += 1
                logger.exception(
                    "Failed complaint detection | post_id={} | error={}",
                    post.id,
                    str(exc),
                )

        if not dry_run:
            self.db.commit()

        summary = ComplaintDetectionSummary(
            total_candidates=total_candidates,
            processed=processed,
            updated=updated,
            complaints_detected=complaints_detected,
            skipped=skipped,
            errors=errors,
            dry_run=dry_run,
        )

        logger.info("Complaint detection completed | summary={}", summary.to_dict())

        return summary
