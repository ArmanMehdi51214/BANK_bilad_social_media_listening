from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.ai.preprocessing.arabic_text import normalize_arabic_text


TOKEN_CHARS = r"0-9A-Za-z_\u0600-\u06FF"


@dataclass
class TopicPrediction:
    slug: str
    label: str
    confidence: float
    matched_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class BaselineArabicTopicClassifier:
    """
    Baseline Arabic topic classifier for Bank Albilad executive reporting.

    Important:
    - Slugs match topic_categories.slug exactly.
    - Matching uses word/phrase boundaries to avoid false matches.
      Example: ساب should not match حسابي.
    """

    TOPIC_RULES = {
        "customer-support": {
            "label": "Customer Support",
            "terms": [
                "خدمة العملاء", "الدعم", "تواصل", "رد", "الرد", "الخاص",
                "خدمتك", "ارسل", "نأمل تزويدنا", "العميل", "عملاء",
            ],
        },
        "digital-banking": {
            "label": "Digital Banking",
            "terms": [
                "اونلاين", "أونلاين", "الرقمي", "رقمي", "انترنت", "online",
                "digital", "الخدمات الالكترونيه", "الخدمات الإلكترونية",
            ],
        },
        "mobile-app": {
            "label": "Mobile App",
            "terms": [
                "التطبيق", "تطبيق", "app", "mobile app", "الجوال",
                "تطبيق البلاد", "ما يفتح", "ما يشتغل", "تحديث التطبيق",
            ],
        },
        "payments": {
            "label": "Payments",
            "terms": [
                "دفع", "مدفوعات", "سداد", "فاتوره", "فاتورة",
                "mada", "pos", "نقاط البيع", "عملية شراء", "عمليه شراء",
            ],
        },
        "transfers": {
            "label": "Transfers",
            "terms": [
                "تحويل", "حواله", "حوالة", "تحويلات", "حوالات",
                "iban", "آيبان", "ايبان", "مستفيد", "مستفيدين",
            ],
        },
        "cards": {
            "label": "Cards",
            "terms": [
                "بطاقه", "بطاقة", "بطاقات", "فيزا", "visa", "مدى",
                "مدي", "ائتمانيه", "ائتمانية", "credit card",
            ],
        },
        "accounts": {
            "label": "Accounts",
            "terms": [
                "حساب", "حسابي", "الحساب", "فتح حساب", "تجميد حساب",
                "تم تجميد", "مجمد", "موقوف", "تفعيل الحساب",
            ],
        },
        "branches": {
            "label": "Branches",
            "terms": [
                "فرع", "فروع", "الفرع", "الموظف", "الموظفين",
                "موظف", "الانتظار", "زحمه", "زحمة",
            ],
        },
        "atms": {
            "label": "ATMs",
            "terms": [
                "صراف", "الصراف", "atm", "مكينة", "ماكينه", "مكائن",
                "سحب", "ايداع", "إيداع", "نقد",
            ],
        },
        "loans": {
            "label": "Loans",
            "terms": [
                "قرض", "قروض", "تمويل شخصي", "شراء مديونيه", "شراء مديونية",
                "مديونيه", "مديونية",
            ],
        },
        "financing": {
            "label": "Financing",
            "terms": [
                "تمويل", "عقاري", "سياره", "سيارة", "ايجار", "إيجار",
                "مرابحه", "مرابحة", "شراء مديونيه", "شراء مديونية",
            ],
        },
        "campaigns": {
            "label": "Campaigns",
            "terms": [
                "حمله", "حملة", "مسابقه", "مسابقة", "توقع", "نقاط",
                "فوز", "فزت", "جائزه", "جائزة", "دوري",
            ],
        },
        "promotions": {
            "label": "Promotions",
            "terms": [
                "عرض", "عروض", "خصم", "كاش باك", "cashback", "مكافاه",
                "مكافأة", "نقاط", "استرداد",
            ],
        },
        "complaints": {
            "label": "Complaints",
            "terms": [
                "مشكله", "مشكلة", "شكوى", "اشتكي", "بلاغ", "غير مقبول",
                "تأخير", "تاخير", "تعطل", "معلق", "تجميد", "بدون اشعار",
                "بدون إشعار", "حل مشكلتي",
            ],
        },
        "fraud": {
            "label": "Fraud",
            "terms": [
                "احتيال", "نصب", "سرقه", "سرقة", "محتال", "احتيالي",
                "عملية مشبوهه", "عملية مشبوهة",
            ],
        },
        "security": {
            "label": "Security",
            "terms": [
                "امن", "أمن", "امان", "أمان", "كلمة المرور", "رمز التحقق",
                "otp", "دخول", "اختراق", "حمايه", "حماية",
            ],
        },
        "service-quality": {
            "label": "Service Quality",
            "terms": [
                "سيء", "سيئ", "ممتاز", "رائع", "جيد", "بطيء", "بطئ",
                "سريع", "تعامل", "خدمة", "جوده", "جودة",
            ],
        },
        "competitor-discussions": {
            "label": "Competitor Discussions",
            "terms": [
                "الراجحي", "مصرف الراجحي", "الأهلي", "الاهلي", "البنك الأهلي",
                "الإنماء", "الانماء", "بنك الرياض", "riyad bank",
            ],
        },
        "general-banking": {
            "label": "General Banking",
            "terms": [
                "بنك", "مصرف", "البنوك", "تمويل", "مصرفي",
                "بنكي", "الخدمات البنكيه", "الخدمات البنكية",
            ],
        },
    }

    DEFAULT_TOPIC = TopicPrediction(
        slug="other",
        label="Other",
        confidence=0.50,
        matched_terms=[],
    )

    def __init__(self) -> None:
        self.normalized_rules = {}

        for slug, config in self.TOPIC_RULES.items():
            self.normalized_rules[slug] = {
                "label": config["label"],
                "terms": [normalize_arabic_text(term) for term in config["terms"]],
            }

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        if not term:
            return False

        pattern = rf"(?<![{TOKEN_CHARS}]){re.escape(term)}(?![{TOKEN_CHARS}])"
        return re.search(pattern, text) is not None

    def _matched_terms(self, text: str, terms: list[str]) -> list[str]:
        return [term for term in terms if self._contains_term(text, term)]

    @staticmethod
    def _suppress_conflicting_topics(
        predictions: list[TopicPrediction],
        normalized_text: str,
    ) -> list[TopicPrediction]:
        """
        Business rule:
        شراء مديونية is financing/loan intent, not a generic payment/card issue.
        """
        debt_purchase_terms = ["شراء مديونيه", "شراء مديونية", "مديونيه", "مديونية"]
        normalized_debt_terms = [normalize_arabic_text(term) for term in debt_purchase_terms]

        is_debt_purchase = any(term in normalized_text for term in normalized_debt_terms)

        if not is_debt_purchase:
            return predictions

        return [
            prediction
            for prediction in predictions
            if prediction.slug not in {"payments", "cards"}
        ]

    def classify(self, text: str, max_topics: int = 3) -> list[TopicPrediction]:
        normalized_text = normalize_arabic_text(text or "")
        predictions: list[TopicPrediction] = []

        for slug, config in self.normalized_rules.items():
            matched = self._matched_terms(normalized_text, config["terms"])

            if not matched:
                continue

            unique_matches = sorted(set(matched))
            confidence = min(0.95, 0.55 + len(unique_matches) * 0.12)

            predictions.append(
                TopicPrediction(
                    slug=slug,
                    label=config["label"],
                    confidence=round(confidence, 4),
                    matched_terms=unique_matches,
                )
            )

        predictions = self._suppress_conflicting_topics(
            predictions=predictions,
            normalized_text=normalized_text,
        )

        if not predictions:
            return [self.DEFAULT_TOPIC]

        priority = {
            "complaints": 0.08,
            "fraud": 0.08,
            "security": 0.06,
            "accounts": 0.03,
            "loans": 0.03,
            "financing": 0.03,
        }

        for prediction in predictions:
            if prediction.slug in priority:
                prediction.confidence = min(
                    0.98,
                    round(prediction.confidence + priority[prediction.slug], 4),
                )

        predictions.sort(key=lambda item: item.confidence, reverse=True)

        return predictions[:max_topics]
