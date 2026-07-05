from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ai_analysis import AIAnalysisResult, PostEntity, PostTopic
from app.models.social import SocialPost
from app.models.topic import TopicCategory
from app.modules.ai_analysis.complaint_service import SocialPostComplaintDetectionService
from app.modules.ai_analysis.entity_service import SocialPostEntityDetectionService
from app.modules.ai_analysis.preprocessing_service import SocialPostPreprocessingService
from app.modules.ai_analysis.sentiment_service import SocialPostSentimentAnalysisService
from app.modules.ai_analysis.topic_service import SocialPostTopicClassificationService
from app.modules.collection.dependencies import require_collection_operator


router = APIRouter()


def _safe_datetime(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value else None


def _get_attr(obj: Any, candidates: list[str], default: Any = None) -> Any:
    for attr in candidates:
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if value is not None:
                return value
    return default


def _latest_analysis_result(
    db: Session,
    post_id: UUID,
) -> Optional[AIAnalysisResult]:
    current = (
        db.query(AIAnalysisResult)
        .filter(
            AIAnalysisResult.post_id == post_id,
            AIAnalysisResult.is_current.is_(True),
        )
        .order_by(AIAnalysisResult.analyzed_at.desc())
        .first()
    )

    if current:
        return current

    return (
        db.query(AIAnalysisResult)
        .filter(AIAnalysisResult.post_id == post_id)
        .order_by(AIAnalysisResult.analyzed_at.desc())
        .first()
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    return value


def _serialize_post(post: SocialPost) -> dict:
    external_post_id = _get_attr(post, ["external_post_id"])
    url = _get_attr(post, ["url", "post_url", "permalink"])
    source_url = url or (
        f"https://x.com/i/web/status/{external_post_id}"
        if external_post_id
        else None
    )

    return {
        "id": str(post.id),
        "platform": _get_attr(post, ["platform"]),
        "external_post_id": external_post_id,
        "url": url,
        "source_url": source_url,
        "language": _get_attr(post, ["language", "lang"]),
        "raw_text": _get_attr(post, ["raw_text", "text"]),
        "clean_text": _get_attr(post, ["clean_text"]),
        "published_at": _safe_datetime(_get_attr(post, ["published_at", "created_at_platform"])),
        "collected_at": _safe_datetime(_get_attr(post, ["collected_at", "created_at"])),
    }


def _serialize_analysis_result(result: AIAnalysisResult) -> dict:
    return {
        "id": str(result.id),
        "post_id": str(result.post_id),
        "status": result.status,
        "sentiment_label": result.sentiment_label,
        "sentiment_score": result.sentiment_score,
        "sentiment_confidence": result.sentiment_confidence,
        "is_complaint": result.is_complaint,
        "complaint_confidence": result.complaint_confidence,
        "model_name": result.model_name,
        "model_version": result.model_version,
        "pipeline_version": result.pipeline_version,
        "is_current": result.is_current,
        "error_message": result.error_message,
        "analysis_payload": _json_safe(result.analysis_payload),
        "analyzed_at": _safe_datetime(result.analyzed_at),
        "created_at": _safe_datetime(result.created_at),
        "updated_at": _safe_datetime(result.updated_at),
    }


def _serialize_topics(db: Session, post_id: UUID) -> list[dict]:
    rows = (
        db.query(PostTopic, TopicCategory)
        .join(TopicCategory, TopicCategory.id == PostTopic.topic_id)
        .filter(PostTopic.post_id == post_id)
        .order_by(PostTopic.is_primary.desc(), PostTopic.confidence.desc())
        .all()
    )

    return [
        {
            "id": str(post_topic.id),
            "topic_id": str(topic.id),
            "slug": topic.slug,
            "name": topic.name,
            "confidence": post_topic.confidence,
            "is_primary": post_topic.is_primary,
            "analysis_result_id": str(post_topic.analysis_result_id),
        }
        for post_topic, topic in rows
    ]


def _serialize_entities(db: Session, post_id: UUID) -> list[dict]:
    rows = (
        db.query(PostEntity)
        .filter(PostEntity.post_id == post_id)
        .order_by(PostEntity.entity_type.asc(), PostEntity.confidence.desc())
        .all()
    )

    items: list[dict] = []

    for entity in rows:
        items.append(
            {
                "id": str(entity.id),
                "analysis_result_id": str(entity.analysis_result_id),
                "post_id": str(entity.post_id),
                "entity_type": entity.entity_type,
                "value": _get_attr(
                    entity,
                    ["value", "entity_value", "entity_text", "entity_name", "name"],
                ),
                "normalized_value": _get_attr(
                    entity,
                    ["normalized_value", "normalized_text", "normalized_name"],
                ),
                "competitor_id": str(_get_attr(entity, ["competitor_id"])) if _get_attr(entity, ["competitor_id"]) else None,
                "confidence": entity.confidence,
                "start_char": getattr(entity, "start_char", None),
                "end_char": getattr(entity, "end_char", None),
            }
        )

    return items


def _serialize_full_post_analysis(db: Session, post: SocialPost) -> dict:
    analysis_result = _latest_analysis_result(db, post.id)

    return {
        "post": _serialize_post(post),
        "analysis": _serialize_analysis_result(analysis_result) if analysis_result else None,
        "topics": _serialize_topics(db, post.id),
        "entities": _serialize_entities(db, post.id),
    }


@router.get("/summary")
def get_ai_summary(
    platform: Optional[str] = Query(default="x"),
    db: Session = Depends(get_db),
    _current_user=Depends(require_collection_operator),
):
    """
    Dashboard summary for the AI intelligence layer.
    """

    posts_query = db.query(SocialPost)

    if platform:
        posts_query = posts_query.filter(SocialPost.platform == platform)

    total_posts = posts_query.count()
    posts_with_clean_text = posts_query.filter(SocialPost.clean_text.isnot(None)).count()

    analysis_query = (
        db.query(AIAnalysisResult)
        .join(SocialPost, SocialPost.id == AIAnalysisResult.post_id)
        .filter(AIAnalysisResult.is_current.is_(True))
    )

    if platform:
        analysis_query = analysis_query.filter(SocialPost.platform == platform)

    analyzed_posts = analysis_query.count()
    complaint_count = analysis_query.filter(AIAnalysisResult.is_complaint.is_(True)).count()

    sentiment_rows = (
        analysis_query.with_entities(
            AIAnalysisResult.sentiment_label,
            func.count(AIAnalysisResult.id),
        )
        .group_by(AIAnalysisResult.sentiment_label)
        .order_by(func.count(AIAnalysisResult.id).desc())
        .all()
    )

    topic_query = (
        db.query(TopicCategory.slug, TopicCategory.name, func.count(PostTopic.id))
        .join(PostTopic, PostTopic.topic_id == TopicCategory.id)
        .join(SocialPost, SocialPost.id == PostTopic.post_id)
    )

    if platform:
        topic_query = topic_query.filter(SocialPost.platform == platform)

    topic_rows = (
        topic_query.group_by(TopicCategory.slug, TopicCategory.name)
        .order_by(func.count(PostTopic.id).desc())
        .all()
    )

    entity_query = (
        db.query(PostEntity.entity_type, func.count(PostEntity.id))
        .join(SocialPost, SocialPost.id == PostEntity.post_id)
    )

    if platform:
        entity_query = entity_query.filter(SocialPost.platform == platform)

    entity_rows = (
        entity_query.group_by(PostEntity.entity_type)
        .order_by(func.count(PostEntity.id).desc())
        .all()
    )

    latest_analysis = (
        analysis_query.order_by(AIAnalysisResult.analyzed_at.desc()).first()
    )

    return {
        "platform": platform,
        "total_posts": total_posts,
        "posts_with_clean_text": posts_with_clean_text,
        "analyzed_posts": analyzed_posts,
        "complaint_count": complaint_count,
        "complaint_rate": round(complaint_count / analyzed_posts, 4) if analyzed_posts else 0.0,
        "sentiment_distribution": [
            {"sentiment_label": label, "count": count}
            for label, count in sentiment_rows
        ],
        "topic_distribution": [
            {"slug": slug, "name": name, "count": count}
            for slug, name, count in topic_rows
        ],
        "entity_distribution": [
            {"entity_type": entity_type, "count": count}
            for entity_type, count in entity_rows
        ],
        "latest_analysis_at": _safe_datetime(latest_analysis.analyzed_at) if latest_analysis else None,
    }


@router.get("/results")
def list_ai_results(
    platform: Optional[str] = Query(default="x"),
    sentiment_label: Optional[str] = Query(default=None),
    is_complaint: Optional[bool] = Query(default=None),
    brand_related: bool = Query(default=False),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _current_user=Depends(require_collection_operator),
):
    """
    List analyzed posts for dashboard tables and search screens.
    """

    query = (
        db.query(AIAnalysisResult, SocialPost)
        .join(SocialPost, SocialPost.id == AIAnalysisResult.post_id)
        .filter(AIAnalysisResult.is_current.is_(True))
    )

    if platform:
        query = query.filter(SocialPost.platform == platform)

    if sentiment_label:
        query = query.filter(AIAnalysisResult.sentiment_label == sentiment_label)

    if is_complaint is not None:
        query = query.filter(AIAnalysisResult.is_complaint.is_(is_complaint))

    if brand_related:
        brand_patterns = [
            "%@BankAlbilad%",
            "%bankalbilad%",
            "%Bank Albilad%",
            "%Albilad Bank%",
            "%بنك البلاد%",
            "%مصرف البلاد%",
            "%تطبيق البلاد%",
            "%بطاقة البلاد%",
            "%تمويل البلاد%",
        ]

        conditions = []

        for pattern in brand_patterns:
            conditions.append(SocialPost.raw_text.ilike(pattern))
            conditions.append(SocialPost.clean_text.ilike(pattern))

        query = query.filter(or_(*conditions))

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                SocialPost.clean_text.ilike(pattern),
                SocialPost.raw_text.ilike(pattern),
                SocialPost.external_post_id.ilike(pattern),
            )
        )

    total = query.count()

    rows = (
        query.order_by(AIAnalysisResult.analyzed_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []

    for analysis_result, post in rows:
        items.append(
            {
                "post": _serialize_post(post),
                "analysis": _serialize_analysis_result(analysis_result),
                "topics": _serialize_topics(db, post.id),
                "entities": _serialize_entities(db, post.id),
            }
        )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/posts/{post_id}/analysis")
def get_post_analysis(
    post_id: UUID,
    db: Session = Depends(get_db),
    _current_user=Depends(require_collection_operator),
):
    """
    Full AI analysis for one post.
    """

    post = db.query(SocialPost).filter(SocialPost.id == post_id).first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    return _serialize_full_post_analysis(db, post)


@router.post("/analyze/unprocessed")
def analyze_unprocessed_posts(
    platform: Optional[str] = Query(default="x"),
    limit: int = Query(default=100, ge=1, le=1000),
    dry_run: bool = Query(default=False),
    run_preprocessing: bool = Query(default=True),
    run_sentiment: bool = Query(default=True),
    run_topics: bool = Query(default=True),
    run_complaints: bool = Query(default=True),
    run_entities: bool = Query(default=True),
    db: Session = Depends(get_db),
    _current_user=Depends(require_collection_operator),
):
    """
    Runs the full AI pipeline for unprocessed posts.

    Pipeline:
    preprocessing -> sentiment -> topics -> complaints -> entities
    """

    response: dict[str, Any] = {
        "platform": platform,
        "limit": limit,
        "dry_run": dry_run,
        "steps": {},
    }

    if run_preprocessing:
        preprocessing_summary = SocialPostPreprocessingService(db).preprocess_posts(
            platform=platform,
            limit=limit,
            only_unprocessed=True,
            dry_run=dry_run,
        )
        response["steps"]["preprocessing"] = preprocessing_summary.to_dict()

    if run_sentiment:
        sentiment_summary = SocialPostSentimentAnalysisService(db).analyze_posts(
            platform=platform,
            limit=limit,
            only_unanalyzed=True,
            dry_run=dry_run,
        )
        response["steps"]["sentiment"] = sentiment_summary.to_dict()

    if run_topics:
        topic_summary = SocialPostTopicClassificationService(db).classify_posts(
            platform=platform,
            limit=limit,
            only_unclassified=True,
            dry_run=dry_run,
        )
        response["steps"]["topics"] = topic_summary.to_dict()

    if run_complaints:
        complaint_summary = SocialPostComplaintDetectionService(db).detect_complaints(
            platform=platform,
            limit=limit,
            dry_run=dry_run,
        )
        response["steps"]["complaints"] = complaint_summary.to_dict()

    if run_entities:
        entity_summary = SocialPostEntityDetectionService(db).detect_entities(
            platform=platform,
            limit=limit,
            only_without_entities=True,
            dry_run=dry_run,
        )
        response["steps"]["entities"] = entity_summary.to_dict()

    return response


@router.post("/analyze/post/{post_id}")
def analyze_single_post(
    post_id: UUID,
    dry_run: bool = Query(default=False),
    db: Session = Depends(get_db),
    _current_user=Depends(require_collection_operator),
):
    """
    Runs the full AI pipeline for a single post.
    """

    post = db.query(SocialPost).filter(SocialPost.id == post_id).first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    response: dict[str, Any] = {
        "post_id": str(post_id),
        "dry_run": dry_run,
        "steps": {},
    }

    preprocessing_result = SocialPostPreprocessingService(db).preprocess_single_post(
        post_id=post_id,
        dry_run=dry_run,
    )
    response["steps"]["preprocessing"] = preprocessing_result

    sentiment_result = SocialPostSentimentAnalysisService(db).analyze_single_post(
        post_id=post_id,
        dry_run=dry_run,
    )
    response["steps"]["sentiment"] = sentiment_result

    topic_result = SocialPostTopicClassificationService(db).classify_single_post(
        post_id=post_id,
        dry_run=dry_run,
    )
    response["steps"]["topics"] = topic_result

    if not dry_run:
        db.refresh(post)

    analysis_result = _latest_analysis_result(db, post.id)

    if analysis_result:
        complaint_service = SocialPostComplaintDetectionService(db)
        complaint_service.detect_for_result(
            analysis_result=analysis_result,
            post=post,
            dry_run=dry_run,
        )

        entity_service = SocialPostEntityDetectionService(db)
        inserted_entities = entity_service.detect_for_post(
            post=post,
            dry_run=dry_run,
        )

        if not dry_run:
            db.commit()

        response["steps"]["complaints"] = {
            "processed": 1,
            "dry_run": dry_run,
        }
        response["steps"]["entities"] = {
            "processed": 1,
            "inserted": inserted_entities,
            "dry_run": dry_run,
        }

    response["result"] = _serialize_full_post_analysis(db, post)

    return response
