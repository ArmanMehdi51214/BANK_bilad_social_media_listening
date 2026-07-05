from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modules.ai_analysis.preprocessing_service import SocialPostPreprocessingService
from app.modules.ai_analysis.sentiment_service import SocialPostSentimentAnalysisService
from app.modules.ai_analysis.topic_service import SocialPostTopicClassificationService
from app.modules.ai_analysis.complaint_service import SocialPostComplaintDetectionService
from app.modules.ai_analysis.entity_service import SocialPostEntityDetectionService


def run_ai_pipeline_for_unprocessed(
    db: Session,
    platform: str = "x",
    limit: int = 500,
    dry_run: bool = False,
) -> dict[str, Any]:
    return {
        "preprocessing": SocialPostPreprocessingService(db).preprocess_posts(
            platform=platform,
            limit=limit,
            only_unprocessed=True,
            dry_run=dry_run,
        ).to_dict(),
        "sentiment": SocialPostSentimentAnalysisService(db).analyze_posts(
            platform=platform,
            limit=limit,
            only_unanalyzed=True,
            dry_run=dry_run,
        ).to_dict(),
        "topics": SocialPostTopicClassificationService(db).classify_posts(
            platform=platform,
            limit=limit,
            only_unclassified=True,
            dry_run=dry_run,
        ).to_dict(),
        "complaints": SocialPostComplaintDetectionService(db).detect_complaints(
            platform=platform,
            limit=limit,
            dry_run=dry_run,
        ).to_dict(),
        "entities": SocialPostEntityDetectionService(db).detect_entities(
            platform=platform,
            limit=limit,
            only_without_entities=True,
            dry_run=dry_run,
        ).to_dict(),
    }
