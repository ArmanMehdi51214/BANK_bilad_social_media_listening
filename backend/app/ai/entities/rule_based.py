from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.ai.preprocessing.arabic_text import (
    extract_hashtags,
    extract_mentions,
    normalize_arabic_text,
    repair_mojibake,
)


TOKEN_CHARS = r"0-9A-Za-z_\u0600-\u06FF"


@dataclass
class EntityDetectionResult:
    entity_type: str
    entity_value: str
    normalized_value: str
    confidence: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class BaselineArabicEntityDetector:
    """
    Baseline Arabic entity detector.

    Business purpose:
    Extracts structured entities needed for executive reporting:
    brand, competitors, products, services, hashtags, mentions, and campaigns.
    """

    BANK_ALBILAD_TERMS = [
        "بنك البلاد",
        "مصرف البلاد",
        "bank albilad",
        "bankalbilad",
        "@bankalbilad",
        "تطبيق البلاد",
        "بطاقة البلاد",
        "تمويل البلاد",
    ]

    SERVICE_RULES = {
        "account": [
            "حساب", "حسابي", "الحساب", "فتح حساب", "تجميد حساب",
            "تم تجميد", "موقوف", "مجمد",
        ],
        "mobile_app": [
            "تطبيق", "التطبيق", "تطبيق البلاد", "الجوال", "app", "mobile app",
        ],
        "transfer": [
            "تحويل", "تحويلات", "حواله", "حوالة", "حوالات",
            "ايبان", "آيبان", "iban", "مستفيد",
        ],
        "card": [
            "بطاقة", "بطاقه", "بطاقتي", "بطاقات", "مدى", "مدي",
            "فيزا", "visa", "تمكين", "سقنتشر", "signature",
        ],
        "financing": [
            "تمويل", "قرض", "قروض", "شراء مديونية", "شراء مديونيه",
            "مديونية", "مديونيه", "تمويل شخصي", "عقاري",
        ],
        "branch": [
            "فرع", "فروع", "الفرع", "موظف", "الموظف", "الموظفين",
        ],
        "atm": [
            "صراف", "الصراف", "atm", "مكينة", "ماكينة", "مكائن",
            "سحب", "ايداع", "إيداع",
        ],
        "payment": [
            "دفع", "مدفوعات", "سداد", "فاتورة", "فاتوره",
            "نقاط البيع", "pos", "عملية شراء", "عمليه شراء",
        ],
        "customer_support": [
            "خدمة العملاء", "الدعم", "الخاص", "تواصلت", "رد",
            "الرد", "خدمتك", "عملاء",
        ],
    }

    CAMPAIGN_TERMS = [
        "مسابقة", "مسابقه", "حملة", "حمله", "عرض", "عروض",
        "نقاط", "برنامج النقاط", "توقع", "دوري", "فزت",
        "جائزة", "جائزه", "كاش باك", "cashback",
    ]

    def __init__(self, competitor_aliases: list[dict[str, Any]] | None = None) -> None:
        self.competitor_aliases = competitor_aliases or []

        self.normalized_brand_terms = [
            normalize_arabic_text(term) for term in self.BANK_ALBILAD_TERMS
        ]

        self.normalized_service_rules = {
            service: [normalize_arabic_text(term) for term in terms]
            for service, terms in self.SERVICE_RULES.items()
        }

        self.normalized_campaign_terms = [
            normalize_arabic_text(term) for term in self.CAMPAIGN_TERMS
        ]

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        if not term:
            return False

        pattern = rf"(?<![{TOKEN_CHARS}]){re.escape(term)}(?![{TOKEN_CHARS}])"
        return re.search(pattern, text) is not None

    def _add_entity(
        self,
        entities: list[EntityDetectionResult],
        entity_type: str,
        entity_value: str,
        confidence: float,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        clean_value = repair_mojibake(entity_value or "").strip()

        if not clean_value:
            return

        entities.append(
            EntityDetectionResult(
                entity_type=entity_type,
                entity_value=clean_value,
                normalized_value=normalize_arabic_text(clean_value),
                confidence=round(confidence, 4),
                source=source,
                metadata=metadata or {},
            )
        )

    @staticmethod
    def _deduplicate(
        entities: list[EntityDetectionResult],
    ) -> list[EntityDetectionResult]:
        best: dict[tuple[str, str], EntityDetectionResult] = {}

        for entity in entities:
            key = (entity.entity_type, entity.normalized_value)

            if key not in best or entity.confidence > best[key].confidence:
                best[key] = entity

        return sorted(
            best.values(),
            key=lambda item: (item.entity_type, -item.confidence, item.entity_value),
        )

    def detect(self, text: str) -> list[EntityDetectionResult]:
        repaired_text = repair_mojibake(text or "")
        normalized_text = normalize_arabic_text(repaired_text)

        entities: list[EntityDetectionResult] = []

        for mention in extract_mentions(repaired_text):
            self._add_entity(
                entities=entities,
                entity_type="social_mention",
                entity_value=mention,
                confidence=0.95,
                source="mention_extraction",
            )

        for hashtag in extract_hashtags(repaired_text):
            self._add_entity(
                entities=entities,
                entity_type="hashtag",
                entity_value=hashtag,
                confidence=0.95,
                source="hashtag_extraction",
            )

        for term in self.normalized_brand_terms:
            if self._contains_term(normalized_text, term):
                self._add_entity(
                    entities=entities,
                    entity_type="brand",
                    entity_value="Bank Albilad",
                    confidence=0.95,
                    source="brand_dictionary",
                    metadata={"matched_term": term},
                )
                break

        for competitor in self.competitor_aliases:
            alias = competitor.get("alias") or ""
            normalized_alias = normalize_arabic_text(alias)

            if not normalized_alias:
                continue

            if self._contains_term(normalized_text, normalized_alias):
                self._add_entity(
                    entities=entities,
                    entity_type="competitor",
                    entity_value=competitor.get("competitor_name") or alias,
                    confidence=0.90,
                    source="competitor_alias",
                    metadata={
                        "competitor_id": competitor.get("competitor_id"),
                        "matched_alias": alias,
                    },
                )

        for service, terms in self.normalized_service_rules.items():
            matched_terms = [
                term for term in terms if self._contains_term(normalized_text, term)
            ]

            if matched_terms:
                self._add_entity(
                    entities=entities,
                    entity_type="service_area",
                    entity_value=service,
                    confidence=min(0.95, 0.65 + len(set(matched_terms)) * 0.10),
                    source="service_dictionary",
                    metadata={"matched_terms": sorted(set(matched_terms))},
                )

        for term in self.normalized_campaign_terms:
            if self._contains_term(normalized_text, term):
                self._add_entity(
                    entities=entities,
                    entity_type="campaign_term",
                    entity_value=term,
                    confidence=0.75,
                    source="campaign_dictionary",
                )

        return self._deduplicate(entities)
