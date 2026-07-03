import re
import unicodedata

from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.competitor import Competitor, CompetitorAlias
from app.models.enums import MonitoringRuleType, MonitoringTargetType, PlatformType, UserRole
from app.models.monitoring import MonitoringRule
from app.models.topic import TopicCategory
from app.models.user import User


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.strip().lower()
    value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    value = value.replace("ى", "ي").replace("ة", "ه").replace("ـ", "")
    value = re.sub(r"\s+", " ", value)
    return value


TOPICS = [
    ("Customer Support", "customer-support", "Customer support and service interactions"),
    ("Digital Banking", "digital-banking", "Digital banking services and online experience"),
    ("Mobile App", "mobile-app", "Mobile application issues, feedback, and usage"),
    ("Payments", "payments", "Payment transactions and payment services"),
    ("Transfers", "transfers", "Local and international transfers"),
    ("Cards", "cards", "Debit, credit, and prepaid cards"),
    ("Accounts", "accounts", "Account opening, account management, and account issues"),
    ("Branches", "branches", "Branch experience and branch service quality"),
    ("ATMs", "atms", "ATM availability, cash withdrawal, and ATM issues"),
    ("Loans", "loans", "Loan products and customer discussions"),
    ("Financing", "financing", "Personal, auto, and real estate financing"),
    ("Campaigns", "campaigns", "Bank campaigns and public campaign response"),
    ("Promotions", "promotions", "Offers, promotions, and customer response"),
    ("Complaints", "complaints", "Customer complaints and dissatisfaction"),
    ("Fraud", "fraud", "Fraud concerns and scam-related discussions"),
    ("Security", "security", "Security, privacy, and account protection"),
    ("Service Quality", "service-quality", "General service quality and customer experience"),
    ("Competitor Discussions", "competitor-discussions", "Mentions and comparisons with competitors"),
    ("General Banking", "general-banking", "General banking discussions"),
    ("Other", "other", "Unclassified or unclear discussions"),
]


COMPETITORS = [
    {
        "name_en": "Al Rajhi Bank",
        "name_ar": "مصرف الراجحي",
        "aliases": ["Al Rajhi", "AlRajhi", "مصرف الراجحي", "بنك الراجحي", "الراجحي"],
    },
    {
        "name_en": "Saudi National Bank",
        "name_ar": "البنك الأهلي السعودي",
        "aliases": ["SNB", "Saudi National Bank", "البنك الأهلي", "الأهلي", "الاهلي", "البنك الأهلي السعودي"],
    },
    {
        "name_en": "Riyad Bank",
        "name_ar": "بنك الرياض",
        "aliases": ["Riyad Bank", "بنك الرياض", "الرياض"],
    },
    {
        "name_en": "Alinma Bank",
        "name_ar": "مصرف الإنماء",
        "aliases": ["Alinma", "Alinma Bank", "مصرف الإنماء", "بنك الإنماء", "الانماء"],
    },
    {
        "name_en": "Saudi Awwal Bank",
        "name_ar": "البنك السعودي الأول",
        "aliases": ["SAB", "Saudi Awwal Bank", "البنك السعودي الأول", "ساب"],
    },
    {
        "name_en": "Arab National Bank",
        "name_ar": "البنك العربي الوطني",
        "aliases": ["ANB", "Arab National Bank", "البنك العربي الوطني", "العربي"],
    },
]


BRAND_RULES = [
    (MonitoringRuleType.KEYWORD.value, "Bank Albilad", "en"),
    (MonitoringRuleType.KEYWORD.value, "Albilad Bank", "en"),
    (MonitoringRuleType.KEYWORD.value, "بنك البلاد", "ar"),
    (MonitoringRuleType.KEYWORD.value, "البلاد", "ar"),
    (MonitoringRuleType.HASHTAG.value, "#بنك_البلاد", "ar"),
    (MonitoringRuleType.HASHTAG.value, "#BankAlbilad", "en"),
    (MonitoringRuleType.MENTION.value, "@bankalbilad", "en"),
]


def seed_admin_user(db: Session) -> User:
    email = "admin@bankalbilad.com"

    user = db.query(User).filter(User.email == email).first()
    if user:
        return user

    user = User(
        email=email,
        full_name="Bank Albilad Admin",
        hashed_password=hash_password("Admin@12345"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_topics(db: Session) -> None:
    for name, slug, description in TOPICS:
        existing = db.query(TopicCategory).filter(TopicCategory.slug == slug).first()
        if existing:
            continue

        db.add(
            TopicCategory(
                name=name,
                slug=slug,
                description=description,
                is_active=True,
            )
        )

    db.commit()


def seed_competitors(db: Session) -> None:
    for item in COMPETITORS:
        normalized_name = normalize_text(item["name_en"])

        competitor = (
            db.query(Competitor)
            .filter(Competitor.normalized_name == normalized_name)
            .first()
        )

        if not competitor:
            competitor = Competitor(
                name_en=item["name_en"],
                name_ar=item["name_ar"],
                normalized_name=normalized_name,
                is_active=True,
            )
            db.add(competitor)
            db.commit()
            db.refresh(competitor)

        seen_aliases = set()

        for alias in item["aliases"]:
            normalized_alias = normalize_text(alias)

            if normalized_alias in seen_aliases:
                continue

            seen_aliases.add(normalized_alias)

            existing_alias = (
                db.query(CompetitorAlias)
                .filter(
                    CompetitorAlias.competitor_id == competitor.id,
                    CompetitorAlias.normalized_alias == normalized_alias,
                )
                .first()
            )

            if existing_alias:
                continue

            db.add(
                CompetitorAlias(
                    competitor_id=competitor.id,
                    alias=alias,
                    normalized_alias=normalized_alias,
                    language="ar" if re.search(r"[\u0600-\u06FF]", alias) else "en",
                    is_active=True,
                )
            )

    db.commit()


def seed_monitoring_rules(db: Session, admin_user: User) -> None:
    for rule_type, value, language in BRAND_RULES:
        normalized_value = normalize_text(value)

        existing = (
            db.query(MonitoringRule)
            .filter(
                MonitoringRule.platform == PlatformType.X.value,
                MonitoringRule.rule_type == rule_type,
                MonitoringRule.target_type == MonitoringTargetType.BRAND.value,
                MonitoringRule.normalized_value == normalized_value,
            )
            .first()
        )

        if existing:
            continue

        db.add(
            MonitoringRule(
                platform=PlatformType.X.value,
                rule_type=rule_type,
                target_type=MonitoringTargetType.BRAND.value,
                value=value,
                normalized_value=normalized_value,
                language=language,
                is_active=True,
                created_by_user_id=admin_user.id,
            )
        )

    aliases = db.query(CompetitorAlias).filter(CompetitorAlias.is_active.is_(True)).all()

    for alias in aliases:
        existing = (
            db.query(MonitoringRule)
            .filter(
                MonitoringRule.platform == PlatformType.X.value,
                MonitoringRule.rule_type == MonitoringRuleType.KEYWORD.value,
                MonitoringRule.target_type == MonitoringTargetType.COMPETITOR.value,
                MonitoringRule.normalized_value == alias.normalized_alias,
            )
            .first()
        )

        if existing:
            continue

        db.add(
            MonitoringRule(
                platform=PlatformType.X.value,
                rule_type=MonitoringRuleType.KEYWORD.value,
                target_type=MonitoringTargetType.COMPETITOR.value,
                value=alias.alias,
                normalized_value=alias.normalized_alias,
                language=alias.language,
                is_active=True,
                created_by_user_id=admin_user.id,
            )
        )

    db.commit()


def main() -> None:
    db = SessionLocal()

    try:
        admin_user = seed_admin_user(db)
        seed_topics(db)
        seed_competitors(db)
        seed_monitoring_rules(db, admin_user)

        print("Seed completed successfully.")
        print("Default admin email: admin@bankalbilad.com")
        print("Default admin password: Admin@12345")
    finally:
        db.close()


if __name__ == "__main__":
    main()
