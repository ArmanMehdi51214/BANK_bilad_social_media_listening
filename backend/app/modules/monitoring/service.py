from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException, ValidationException
from app.models.monitoring import MonitoringRule
from app.models.user import User
from app.modules.monitoring.schemas import MonitoringRuleCreate, MonitoringRuleUpdate
from app.utils.text_normalization import normalize_text


class MonitoringRuleService:
    def __init__(self, db: Session):
        self.db = db

    def list_rules(
        self,
        page: int = 1,
        page_size: int = 20,
        platform: Optional[str] = None,
        rule_type: Optional[str] = None,
        target_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ):
        query = self.db.query(MonitoringRule)

        if platform:
            query = query.filter(MonitoringRule.platform == platform)

        if rule_type:
            query = query.filter(MonitoringRule.rule_type == rule_type)

        if target_type:
            query = query.filter(MonitoringRule.target_type == target_type)

        if is_active is not None:
            query = query.filter(MonitoringRule.is_active == is_active)

        if search:
            normalized_search = normalize_text(search)
            query = query.filter(MonitoringRule.normalized_value.ilike(f"%{normalized_search}%"))

        total = query.count()

        items = (
            query.order_by(MonitoringRule.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return items, total


    def list_rules_by_type(
        self,
        rule_type: str,
        page: int = 1,
        page_size: int = 20,
        platform: Optional[str] = None,
        target_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ):
        return self.list_rules(
            page=page,
            page_size=page_size,
            platform=platform,
            rule_type=rule_type,
            target_type=target_type,
            is_active=is_active,
            search=search,
        )

    def list_active_rules(
        self,
        platform: Optional[str] = None,
        target_type: Optional[str] = None,
    ) -> list[MonitoringRule]:
        query = self.db.query(MonitoringRule).filter(MonitoringRule.is_active.is_(True))

        if platform:
            query = query.filter(MonitoringRule.platform == platform)

        if target_type:
            query = query.filter(MonitoringRule.target_type == target_type)

        return (
            query.order_by(
                MonitoringRule.platform.asc(),
                MonitoringRule.target_type.asc(),
                MonitoringRule.rule_type.asc(),
                MonitoringRule.value.asc(),
            )
            .all()
        )


    def get_monitoring_summary(self) -> dict:
        total_rules = self.db.query(func.count(MonitoringRule.id)).scalar() or 0

        active_rules = (
            self.db.query(func.count(MonitoringRule.id))
            .filter(MonitoringRule.is_active.is_(True))
            .scalar()
            or 0
        )

        inactive_rules = (
            self.db.query(func.count(MonitoringRule.id))
            .filter(MonitoringRule.is_active.is_(False))
            .scalar()
            or 0
        )

        def group_count(column):
            rows = (
                self.db.query(column, func.count(MonitoringRule.id))
                .group_by(column)
                .order_by(column)
                .all()
            )
            return {str(key): count for key, count in rows}

        def active_group_count(column):
            rows = (
                self.db.query(column, func.count(MonitoringRule.id))
                .filter(MonitoringRule.is_active.is_(True))
                .group_by(column)
                .order_by(column)
                .all()
            )
            return {str(key): count for key, count in rows}

        x_active_rules = (
            self.db.query(func.count(MonitoringRule.id))
            .filter(
                MonitoringRule.platform == "x",
                MonitoringRule.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        return {
            "total_rules": total_rules,
            "active_rules": active_rules,
            "inactive_rules": inactive_rules,
            "x_active_rules": x_active_rules,
            "by_platform": group_count(MonitoringRule.platform),
            "by_rule_type": group_count(MonitoringRule.rule_type),
            "by_target_type": group_count(MonitoringRule.target_type),
            "active_by_rule_type": active_group_count(MonitoringRule.rule_type),
            "active_by_target_type": active_group_count(MonitoringRule.target_type),
        }

    def get_rule(self, rule_id: UUID) -> MonitoringRule:
        rule = self.db.query(MonitoringRule).filter(MonitoringRule.id == rule_id).first()

        if not rule:
            raise NotFoundException("Monitoring rule not found")

        return rule

    def create_rule(self, payload: MonitoringRuleCreate, current_user: User) -> MonitoringRule:
        normalized_value = normalize_text(payload.value)

        rule = MonitoringRule(
            platform=payload.platform.value,
            rule_type=payload.rule_type.value,
            target_type=payload.target_type.value,
            value=payload.value.strip(),
            normalized_value=normalized_value,
            language=payload.language,
            is_active=payload.is_active,
            created_by_user_id=current_user.id,
        )

        self.db.add(rule)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationException(
                message="Monitoring rule already exists",
                details={
                    "platform": payload.platform.value,
                    "rule_type": payload.rule_type.value,
                    "target_type": payload.target_type.value,
                    "value": payload.value,
                },
            ) from exc

        self.db.refresh(rule)
        return rule

    def update_rule(self, rule_id: UUID, payload: MonitoringRuleUpdate) -> MonitoringRule:
        rule = self.get_rule(rule_id)

        if payload.platform is not None:
            rule.platform = payload.platform.value

        if payload.rule_type is not None:
            rule.rule_type = payload.rule_type.value

        if payload.target_type is not None:
            rule.target_type = payload.target_type.value

        if payload.value is not None:
            rule.value = payload.value.strip()
            rule.normalized_value = normalize_text(payload.value)

        if payload.language is not None:
            rule.language = payload.language

        if payload.is_active is not None:
            rule.is_active = payload.is_active

        self.db.add(rule)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValidationException(
                message="Monitoring rule with this value already exists",
                details={"rule_id": str(rule_id)},
            ) from exc

        self.db.refresh(rule)
        return rule

    def deactivate_rule(self, rule_id: UUID) -> MonitoringRule:
        rule = self.get_rule(rule_id)
        rule.is_active = False

        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        return rule
