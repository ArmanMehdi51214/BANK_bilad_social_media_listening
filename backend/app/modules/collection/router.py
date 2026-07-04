from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.modules.collection.dependencies import require_collection_operator
from app.modules.collection.history_service import CollectionHistoryService
from app.modules.collection.post_service import CollectedPostService
from app.modules.collection.schemas import (
    CollectedPostAuthor,
    CollectedPostDetailResponse,
    CollectedPostListItem,
    CollectedPostListResponse,
    CollectedPostMatch,
    CollectionJobDetailResponse,
    CollectionJobListItem,
    CollectionJobListResponse,
    CollectionJobLogItem,
    CollectionJobLogsResponse,
    XManualCollectionRequest,
    XManualCollectionResponse,
)
from app.modules.collection.service import XCollectionService

router = APIRouter()


def serialize_job_list_item(job) -> CollectionJobListItem:
    return CollectionJobListItem(
        id=str(job.id),
        platform=job.platform,
        job_type=job.job_type,
        status=job.status,
        query_value=job.query_value,
        started_at=job.started_at,
        finished_at=job.finished_at,
        total_fetched=job.total_fetched or 0,
        total_inserted=job.total_inserted or 0,
        total_duplicates=job.total_duplicates or 0,
        total_errors=job.total_errors or 0,
        error_message=job.error_message,
    )


def serialize_job_detail(job) -> CollectionJobDetailResponse:
    base = serialize_job_list_item(job)

    return CollectionJobDetailResponse(
        **base.model_dump(),
        monitoring_rule_id=str(job.monitoring_rule_id) if job.monitoring_rule_id else None,
        cursor_before=job.cursor_before,
        cursor_after=job.cursor_after,
        job_payload=job.job_payload,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def serialize_job_log(log) -> CollectionJobLogItem:
    return CollectionJobLogItem(
        id=str(log.id),
        collection_job_id=str(log.collection_job_id),
        level=log.level,
        event_type=log.event_type,
        message=log.message,
        payload=log.payload,
        occurred_at=log.occurred_at,
    )


def serialize_post_author(author) -> Optional[CollectedPostAuthor]:
    if not author:
        return None

    return CollectedPostAuthor(
        id=str(author.id),
        username=author.username,
        display_name=author.display_name,
        profile_url=author.profile_url,
    )


def serialize_post_list_item(
    post,
    service: CollectedPostService,
) -> CollectedPostListItem:
    author = service.get_author(post.author_id)

    return CollectedPostListItem(
        id=str(post.id),
        platform=post.platform,
        external_post_id=post.external_post_id,
        raw_text=post.raw_text,
        language=post.language,
        source_url=post.source_url,
        published_at=post.published_at,
        collected_at=post.collected_at,
        like_count=post.like_count or 0,
        reply_count=post.reply_count or 0,
        repost_count=post.repost_count or 0,
        quote_count=post.quote_count or 0,
        view_count=post.view_count or 0,
        author=serialize_post_author(author),
        matches_count=service.count_matches(post.id),
    )


def serialize_post_match(match) -> CollectedPostMatch:
    return CollectedPostMatch(
        id=str(match.id),
        monitoring_rule_id=str(match.monitoring_rule_id),
        matched_value=match.matched_value,
        matched_text=match.matched_text,
    )


def serialize_post_detail(
    post,
    service: CollectedPostService,
) -> CollectedPostDetailResponse:
    base = serialize_post_list_item(post, service)
    matches = service.get_matches(post.id)

    return CollectedPostDetailResponse(
        **base.model_dump(),
        clean_text=post.clean_text,
        conversation_id=post.conversation_id,
        parent_external_post_id=post.parent_external_post_id,
        collection_job_id=str(post.collection_job_id) if post.collection_job_id else None,
        raw_payload=post.raw_payload,
        matches=[serialize_post_match(match) for match in matches],
    )


@router.post(
    "/x/run",
    response_model=XManualCollectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Run manual X collection",
    description=(
        "Triggers a manual X/Twitter collection run using active monitoring rules, "
        "saves fetched posts into PostgreSQL, and returns the collection job summary. "
        "Only admin and analyst users are allowed to run this endpoint."
    ),
)
async def run_manual_x_collection(
    request: XManualCollectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_collection_operator),
) -> XManualCollectionResponse:
    try:
        service = XCollectionService(db)

        summary = await service.collect_active_rules(
            max_items=request.max_items,
            sort=request.sort,
            target_types=request.target_types,
            rule_ids=[str(rule_id) for rule_id in request.rule_ids] if request.rule_ids else None,
        )

        logger.info(
            "Manual X collection triggered by user={} | summary={}",
            current_user.email,
            summary,
        )

        return XManualCollectionResponse(**summary)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("Manual X collection API failed")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual X collection failed: {str(exc)}",
        ) from exc


@router.get(
    "/posts",
    response_model=CollectedPostListResponse,
    summary="List collected posts",
    description="Returns collected social posts for dashboard live feed and archive search.",
)
def list_collected_posts(
    platform: Optional[str] = Query(default=None, description="Filter by platform, for example x."),
    language: Optional[str] = Query(default=None, description="Filter by language, for example ar."),
    search: Optional[str] = Query(default=None, description="Search inside post text."),
    collection_job_id: Optional[UUID] = Query(default=None, description="Filter by collection job ID."),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_collection_operator),
) -> CollectedPostListResponse:
    service = CollectedPostService(db)

    total, posts = service.list_posts(
        platform=platform,
        language=language,
        search=search,
        collection_job_id=collection_job_id,
        limit=limit,
        offset=offset,
    )

    return CollectedPostListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[serialize_post_list_item(post, service) for post in posts],
    )


@router.get(
    "/posts/{post_id}",
    response_model=CollectedPostDetailResponse,
    summary="Get collected post detail",
    description="Returns one collected post with author, raw payload, and monitoring matches.",
)
def get_collected_post(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_collection_operator),
) -> CollectedPostDetailResponse:
    service = CollectedPostService(db)
    post = service.get_post(post_id)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collected post not found.",
        )

    return serialize_post_detail(post, service)


@router.get(
    "/jobs",
    response_model=CollectionJobListResponse,
    summary="List collection jobs",
    description="Returns paginated collection job history for operational monitoring.",
)
def list_collection_jobs(
    platform: Optional[str] = Query(default=None, description="Filter by platform, for example x."),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by job status."),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_collection_operator),
) -> CollectionJobListResponse:
    service = CollectionHistoryService(db)

    total, jobs = service.list_jobs(
        platform=platform,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    return CollectionJobListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[serialize_job_list_item(job) for job in jobs],
    )


@router.get(
    "/jobs/{job_id}",
    response_model=CollectionJobDetailResponse,
    summary="Get collection job detail",
    description="Returns full details for a specific collection job.",
)
def get_collection_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_collection_operator),
) -> CollectionJobDetailResponse:
    service = CollectionHistoryService(db)
    job = service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection job not found.",
        )

    return serialize_job_detail(job)


@router.get(
    "/jobs/{job_id}/logs",
    response_model=CollectionJobLogsResponse,
    summary="Get collection job logs",
    description="Returns event logs for a specific collection job.",
)
def get_collection_job_logs(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_collection_operator),
) -> CollectionJobLogsResponse:
    service = CollectionHistoryService(db)
    job = service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection job not found.",
        )

    logs = service.get_job_logs(job_id)

    return CollectionJobLogsResponse(
        job_id=str(job_id),
        total=len(logs),
        items=[serialize_job_log(log) for log in logs],
    )
