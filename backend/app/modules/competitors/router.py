from math import ceil
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.modules.auth.dependencies import get_current_user, require_admin_or_analyst
from app.modules.competitors.schemas import (
    CompetitorAliasCreate,
    CompetitorAliasResponse,
    CompetitorAliasUpdate,
    CompetitorCreate,
    CompetitorListResponse,
    CompetitorResponse,
    CompetitorUpdate,
)
from app.modules.competitors.service import CompetitorService

router = APIRouter(prefix="/monitoring/competitors", tags=["Competitor Management"])


@router.get("", response_model=CompetitorListResponse)
def list_competitors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CompetitorService(db)
    items, total = service.list_competitors(
        page=page,
        page_size=page_size,
        is_active=is_active,
        search=search,
    )

    return CompetitorListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=CompetitorResponse)
def create_competitor(
    payload: CompetitorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_analyst()),
):
    service = CompetitorService(db)
    return service.create_competitor(payload, current_user)


@router.get("/{competitor_id}", response_model=CompetitorResponse)
def get_competitor(
    competitor_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CompetitorService(db)
    return service.get_competitor(competitor_id)


@router.put("/{competitor_id}", response_model=CompetitorResponse)
def update_competitor(
    competitor_id: UUID,
    payload: CompetitorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_analyst()),
):
    service = CompetitorService(db)
    return service.update_competitor(competitor_id, payload)


@router.delete("/{competitor_id}", response_model=CompetitorResponse)
def deactivate_competitor(
    competitor_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_analyst()),
):
    service = CompetitorService(db)
    return service.deactivate_competitor(competitor_id)


@router.post("/{competitor_id}/aliases", response_model=CompetitorAliasResponse)
def add_competitor_alias(
    competitor_id: UUID,
    payload: CompetitorAliasCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_analyst()),
):
    service = CompetitorService(db)
    return service.add_alias(
        competitor_id=competitor_id,
        payload=payload,
        current_user=current_user,
        create_monitoring_rule=True,
    )


@router.put("/aliases/{alias_id}", response_model=CompetitorAliasResponse)
def update_competitor_alias(
    alias_id: UUID,
    payload: CompetitorAliasUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_analyst()),
):
    service = CompetitorService(db)
    return service.update_alias(alias_id, payload, current_user)


@router.delete("/aliases/{alias_id}", response_model=CompetitorAliasResponse)
def deactivate_competitor_alias(
    alias_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_analyst()),
):
    service = CompetitorService(db)
    return service.deactivate_alias(alias_id)
