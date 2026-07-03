from math import ceil
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.modules.auth.dependencies import get_current_user, require_admin_or_analyst
from app.modules.monitoring.schemas import (
    MonitoringRuleCreate,
    MonitoringRuleListResponse,
    MonitoringRuleResponse,
    MonitoringRuleUpdate,
)
from app.modules.monitoring.service import MonitoringRuleService

router = APIRouter(prefix="/monitoring", tags=["Monitoring Configuration"])


@router.get("/rules", response_model=MonitoringRuleListResponse)
def list_monitoring_rules(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    platform: Optional[str] = None,
    rule_type: Optional[str] = None,
    target_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MonitoringRuleService(db)

    items, total = service.list_rules(
        page=page,
        page_size=page_size,
        platform=platform,
        rule_type=rule_type,
        target_type=target_type,
        is_active=is_active,
        search=search,
    )

    return MonitoringRuleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.post("/rules", response_model=MonitoringRuleResponse)
def create_monitoring_rule(
    payload: MonitoringRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_analyst()),
):
    service = MonitoringRuleService(db)
    return service.create_rule(payload, current_user)




@router.get("/keywords", response_model=MonitoringRuleListResponse)
def list_keywords(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    platform: Optional[str] = None,
    target_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MonitoringRuleService(db)

    items, total = service.list_rules_by_type(
        rule_type="keyword",
        page=page,
        page_size=page_size,
        platform=platform,
        target_type=target_type,
        is_active=is_active,
        search=search,
    )

    return MonitoringRuleListResponse(
        message="Keyword monitoring rules loaded successfully",
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/hashtags", response_model=MonitoringRuleListResponse)
def list_hashtags(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    platform: Optional[str] = None,
    target_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MonitoringRuleService(db)

    items, total = service.list_rules_by_type(
        rule_type="hashtag",
        page=page,
        page_size=page_size,
        platform=platform,
        target_type=target_type,
        is_active=is_active,
        search=search,
    )

    return MonitoringRuleListResponse(
        message="Hashtag monitoring rules loaded successfully",
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/mentions", response_model=MonitoringRuleListResponse)
def list_mentions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    platform: Optional[str] = None,
    target_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MonitoringRuleService(db)

    items, total = service.list_rules_by_type(
        rule_type="mention",
        page=page,
        page_size=page_size,
        platform=platform,
        target_type=target_type,
        is_active=is_active,
        search=search,
    )

    return MonitoringRuleListResponse(
        message="Mention monitoring rules loaded successfully",
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/active-rules")
def list_active_rules_for_collection(
    platform: Optional[str] = None,
    target_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MonitoringRuleService(db)
    rules = service.list_active_rules(platform=platform, target_type=target_type)

    grouped_counts = {}

    for rule in rules:
        grouped_counts.setdefault(rule.rule_type, 0)
        grouped_counts[rule.rule_type] += 1

    return {
        "success": True,
        "message": "Active monitoring rules loaded successfully",
        "data": {
            "total": len(rules),
            "grouped_counts": grouped_counts,
            "rules": [
                MonitoringRuleResponse.model_validate(rule).model_dump(mode="json")
                for rule in rules
            ],
        },
    }



@router.get("/summary")
def get_monitoring_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MonitoringRuleService(db)
    summary = service.get_monitoring_summary()

    return {
        "success": True,
        "message": "Monitoring configuration summary loaded successfully",
        "data": summary,
    }

@router.get("/rules/{rule_id}", response_model=MonitoringRuleResponse)
def get_monitoring_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MonitoringRuleService(db)
    return service.get_rule(rule_id)


@router.put("/rules/{rule_id}", response_model=MonitoringRuleResponse)
def update_monitoring_rule(
    rule_id: UUID,
    payload: MonitoringRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_analyst()),
):
    service = MonitoringRuleService(db)
    return service.update_rule(rule_id, payload)


@router.delete("/rules/{rule_id}", response_model=MonitoringRuleResponse)
def deactivate_monitoring_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_analyst()),
):
    service = MonitoringRuleService(db)
    return service.deactivate_rule(rule_id)
