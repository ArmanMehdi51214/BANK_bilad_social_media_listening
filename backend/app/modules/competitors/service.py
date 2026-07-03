import re
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundException, ValidationException
from app.models.competitor import Competitor, CompetitorAlias
from app.models.enums import MonitoringRuleType, MonitoringTargetType, PlatformType
from app.models.monitoring import MonitoringRule
from app.models.user import User
from app.modules.competitors.schemas import (
    CompetitorAliasCreate,
    CompetitorAliasUpdate,
    CompetitorCreate,
    CompetitorUpdate,
)
from app.utils.text_normalization import normalize_text


def detect_language(value: str) -> str:
    return "ar" if re.search(r"[\u0600-\u06FF]", value or "") else "en"


class CompetitorService:
    def __init__(self, db: Session):
        self.db = db

    def list_competitors(
        self,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ):
        query = self.db.query(Competitor).options(selectinload(Competitor.aliases))

        if is_active is not None:
            query = query.filter(Competitor.is_active == is_active)

        if search:
            normalized_search = normalize_text(search)
            query = query.filter(
                Competitor.normalized_name.ilike(f"%{normalized_search}%")
            )

        total = query.count()

        items = (
            query.order_by(Competitor.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return items, total

    def get_competitor(self, competitor_id: UUID) -> Competitor:
        competitor = (
            self.db.query(Competitor)
            .options(selectinload(Competitor.aliases))
            .filter(Competitor.id == competitor_id)
            .first()
        )

        if not competitor:
            raise NotFoundException("Competitor not found")

        return competitor

    def create_competitor(self, payload: CompetitorCreate, current_user: User) -> Competitor:
        normalized_name = normalize_text(payload.name_en)

        competitor = Competitor(
            name_en=payload.name_en.strip(),
            name_ar=payload.name_ar.strip() if payload.name_ar else None,
            normalized_name=normalized_name,
            is_active=payload.is_active,
        )

        self.db.add(competitor)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationException(
                message="Competitor already exists",
                details={"name_en": payload.name_en},
            ) from exc

        self.db.refresh(competitor)

        seen_aliases = set()

        default_aliases = [
            CompetitorAliasCreate(alias=payload.name_en, language="en"),
        ]

        if payload.name_ar:
            default_aliases.append(
                CompetitorAliasCreate(alias=payload.name_ar, language="ar")
            )

        all_aliases = default_aliases + payload.aliases

        for alias_payload in all_aliases:
            normalized_alias = normalize_text(alias_payload.alias)

            if normalized_alias in seen_aliases:
                continue

            seen_aliases.add(normalized_alias)

            self.add_alias(
                competitor_id=competitor.id,
                payload=alias_payload,
                current_user=current_user,
                create_monitoring_rule=payload.create_monitoring_rules,
                commit_each=True,
            )

        return self.get_competitor(competitor.id)

    def update_competitor(self, competitor_id: UUID, payload: CompetitorUpdate) -> Competitor:
        competitor = self.get_competitor(competitor_id)

        if payload.name_en is not None:
            competitor.name_en = payload.name_en.strip()
            competitor.normalized_name = normalize_text(payload.name_en)

        if payload.name_ar is not None:
            competitor.name_ar = payload.name_ar.strip() if payload.name_ar else None

        if payload.is_active is not None:
            competitor.is_active = payload.is_active

        self.db.add(competitor)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationException(
                message="Competitor with this name already exists",
                details={"competitor_id": str(competitor_id)},
            ) from exc

        return self.get_competitor(competitor_id)

    def deactivate_competitor(self, competitor_id: UUID) -> Competitor:
        competitor = self.get_competitor(competitor_id)
        competitor.is_active = False

        for alias in competitor.aliases:
            alias.is_active = False

        self.db.add(competitor)
        self.db.commit()

        return self.get_competitor(competitor_id)

    def add_alias(
        self,
        competitor_id: UUID,
        payload: CompetitorAliasCreate,
        current_user: User,
        create_monitoring_rule: bool = True,
        commit_each: bool = True,
    ) -> CompetitorAlias:
        competitor = self.get_competitor(competitor_id)

        normalized_alias = normalize_text(payload.alias)

        alias = CompetitorAlias(
            competitor_id=competitor.id,
            alias=payload.alias.strip(),
            normalized_alias=normalized_alias,
            language=payload.language or detect_language(payload.alias),
            is_active=payload.is_active,
        )

        self.db.add(alias)

        try:
            if commit_each:
                self.db.commit()
                self.db.refresh(alias)
            else:
                self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationException(
                message="Competitor alias already exists",
                details={
                    "competitor_id": str(competitor_id),
                    "alias": payload.alias,
                },
            ) from exc

        if create_monitoring_rule and alias.is_active:
            self._ensure_competitor_monitoring_rule(alias, current_user)

        return alias

    def update_alias(
        self,
        alias_id: UUID,
        payload: CompetitorAliasUpdate,
        current_user: User,
    ) -> CompetitorAlias:
        alias = self.get_alias(alias_id)

        if payload.alias is not None:
            alias.alias = payload.alias.strip()
            alias.normalized_alias = normalize_text(payload.alias)
            alias.language = payload.language or detect_language(payload.alias)
        elif payload.language is not None:
            alias.language = payload.language

        if payload.is_active is not None:
            alias.is_active = payload.is_active

        self.db.add(alias)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationException(
                message="Competitor alias with this value already exists",
                details={"alias_id": str(alias_id)},
            ) from exc

        self.db.refresh(alias)

        if alias.is_active:
            self._ensure_competitor_monitoring_rule(alias, current_user)

        return alias

    def deactivate_alias(self, alias_id: UUID) -> CompetitorAlias:
        alias = self.get_alias(alias_id)
        alias.is_active = False

        self.db.add(alias)
        self.db.commit()
        self.db.refresh(alias)

        return alias

    def get_alias(self, alias_id: UUID) -> CompetitorAlias:
        alias = (
            self.db.query(CompetitorAlias)
            .filter(CompetitorAlias.id == alias_id)
            .first()
        )

        if not alias:
            raise NotFoundException("Competitor alias not found")

        return alias

    def _ensure_competitor_monitoring_rule(
        self,
        alias: CompetitorAlias,
        current_user: User,
    ) -> None:
        existing = (
            self.db.query(MonitoringRule)
            .filter(
                MonitoringRule.platform == PlatformType.X.value,
                MonitoringRule.rule_type == MonitoringRuleType.KEYWORD.value,
                MonitoringRule.target_type == MonitoringTargetType.COMPETITOR.value,
                MonitoringRule.normalized_value == alias.normalized_alias,
            )
            .first()
        )

        if existing:
            return

        monitoring_rule = MonitoringRule(
            platform=PlatformType.X.value,
            rule_type=MonitoringRuleType.KEYWORD.value,
            target_type=MonitoringTargetType.COMPETITOR.value,
            value=alias.alias,
            normalized_value=alias.normalized_alias,
            language=alias.language,
            is_active=True,
            created_by_user_id=current_user.id,
        )

        self.db.add(monitoring_rule)

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
