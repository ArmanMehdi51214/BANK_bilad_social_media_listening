from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.ai.preprocessing.arabic_text import normalize_arabic_text


TOKEN_CHARS = r"0-9A-Za-z_\u0600-\u06FF"


@dataclass
class ComplaintDetectionResult:
    is_complaint: bool
    confidence: float
    severity: str
    category: str
    matched_terms: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class BaselineArabicComplaintDetector:
    """
    Baseline Arabic complaint detector.

    Principle:
    A post is not a complaint just because it mentions a card, branch, ATM,
    account, product, or service. It must contain an issue/actionable pain signal.
    """

    ISSUE_RULES = {
        "account_access": [
            "تجميد حساب", "تم تجميد", "حسابي موقوف", "الحساب موقوف",
            "حسابي مجمد", "مجمد", "موقوف", "تعطيل حساب", "تعطيل حسابي",
            "تعطيل جميع عملياتي",
        ],
        "transaction_issue": [
            "لم تصل", "ما وصلت", "ما وصل", "انخصم", "خصمتوا",
            "خصم المبلغ", "تم خصم", "فشل التحويل", "فشلت العملية",
            "عملية مرفوضة", "عمليه مرفوضه", "مبلغ مخصوم", "مخصوم من حسابي",
        ],
        "digital_app_issue": [
            "التطبيق لا يعمل", "التطبيق ما يشتغل", "ما يشتغل",
            "ما يفتح", "لا يعمل", "تطبيق معلق", "التطبيق معلق",
            "تعطل التطبيق", "تطبيق البلاد لا يعمل",
        ],
        "fraud_security": [
            "احتيال", "نصب", "سرقه", "سرقة", "اختراق", "محتال",
            "عملية مشبوهه", "عملية مشبوهة", "رمز تحقق بدون طلب",
        ],
        "support_service": [
            "مشكله", "مشكلة", "شكوى", "اشتكي", "بلاغ", "حل مشكلتي",
            "غير مقبول", "لم يتم الرد", "ما رديتوا", "تأخير", "تاخير",
        ],
        "branch_atm": [
            "الصراف لا يعمل", "الصراف معطل", "مكينة معطله", "مكينة معطلة",
            "لم يخرج المبلغ", "سحب ولم يصل", "ايداع ولم يصل", "إيداع ولم يصل",
            "زحمه شديده", "زحمة شديدة",
        ],
        "card_payment_issue": [
            "البطاقه لا تعمل", "البطاقة لا تعمل", "بطاقتي لا تعمل",
            "الدفع مرفوض", "عملية الدفع مرفوضة", "مدى لا تعمل", "مدي لا تعمل",
            "خصم من البطاقة", "انخصم من البطاقة",
        ],
    }

    BANKING_CONTEXT_TERMS = [
        "بنك", "البلاد", "حساب", "حسابي", "تطبيق", "تحويل", "حواله",
        "حوالة", "بطاقه", "بطاقة", "صراف", "فرع", "تمويل",
        "خدمة العملاء", "bankalbilad",
    ]

    HIGH_SEVERITY_TERMS = [
        "تجميد حساب", "تم تجميد", "تعطيل جميع عملياتي", "احتيال",
        "نصب", "سرقه", "سرقة", "اختراق", "مخصوم من حسابي",
        "خصم المبلغ", "سفر",
    ]

    NON_COMPLAINT_INTENT_TERMS = [
        "عندكم", "هل يوجد", "هل عندكم", "استفسار", "احتاج اعرف",
        "مايحتاج", "ما يحتاج", "تحسبلي", "برنامج النقاط",
        "شراء مديونيه", "شراء مديونية", "اقتراح", "لو تحطون",
        "مبروك", "شكرا", "شكراً",
    ]

    def __init__(self) -> None:
        self.normalized_issue_rules = {
            category: [normalize_arabic_text(term) for term in terms]
            for category, terms in self.ISSUE_RULES.items()
        }
        self.normalized_context_terms = [
            normalize_arabic_text(term) for term in self.BANKING_CONTEXT_TERMS
        ]
        self.normalized_high_severity_terms = [
            normalize_arabic_text(term) for term in self.HIGH_SEVERITY_TERMS
        ]
        self.normalized_non_complaint_terms = [
            normalize_arabic_text(term) for term in self.NON_COMPLAINT_INTENT_TERMS
        ]

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        if not term:
            return False

        pattern = rf"(?<![{TOKEN_CHARS}]){re.escape(term)}(?![{TOKEN_CHARS}])"
        return re.search(pattern, text) is not None

    def _matched_terms(self, text: str, terms: list[str]) -> list[str]:
        return [term for term in terms if self._contains_term(text, term)]

    def detect(self, text: str, sentiment_label: str | None = None) -> ComplaintDetectionResult:
        normalized_text = normalize_arabic_text(text or "")
        sentiment_label = sentiment_label or "neutral"

        non_complaint_matches = self._matched_terms(
            normalized_text,
            self.normalized_non_complaint_terms,
        )

        category_matches: dict[str, list[str]] = {}

        for category, terms in self.normalized_issue_rules.items():
            matches = self._matched_terms(normalized_text, terms)
            if matches:
                category_matches[category] = sorted(set(matches))

        context_matches = self._matched_terms(
            normalized_text,
            self.normalized_context_terms,
        )

        high_severity_matches = self._matched_terms(
            normalized_text,
            self.normalized_high_severity_terms,
        )

        all_issue_terms = sorted(
            set(term for matches in category_matches.values() for term in matches)
        )

        has_direct_issue = bool(category_matches)
        has_context = bool(context_matches)
        has_high_severity = bool(high_severity_matches)

        # Product inquiries, suggestions, and campaign questions are not complaints
        # unless they also include a clear issue phrase.
        if non_complaint_matches and not has_high_severity and not has_direct_issue:
            return ComplaintDetectionResult(
                is_complaint=False,
                confidence=0.10,
                severity="none",
                category="none",
                matched_terms=non_complaint_matches,
                explanation="Non-complaint intent detected, such as inquiry, suggestion, or product question.",
            )

        is_complaint = has_direct_issue and (has_context or sentiment_label == "negative" or has_high_severity)

        if not is_complaint:
            return ComplaintDetectionResult(
                is_complaint=False,
                confidence=0.15,
                severity="none",
                category="none",
                matched_terms=non_complaint_matches,
                explanation="No actionable customer complaint indicators were detected.",
            )

        category_scores = {
            category: len(matches)
            for category, matches in category_matches.items()
        }

        primary_category = max(category_scores, key=category_scores.get)

        confidence = 0.50
        confidence += min(0.25, len(all_issue_terms) * 0.08)
        confidence += 0.10 if has_context else 0.0
        confidence += 0.10 if sentiment_label == "negative" else 0.0
        confidence += 0.05 if has_high_severity else 0.0

        if non_complaint_matches and not has_high_severity:
            confidence -= 0.15

        confidence = max(0.0, min(0.98, round(confidence, 4)))

        if has_high_severity or primary_category in {"fraud_security", "account_access"}:
            severity = "high"
        elif primary_category in {"transaction_issue", "digital_app_issue", "card_payment_issue"}:
            severity = "medium"
        else:
            severity = "low"

        matched_terms = sorted(
            set(all_issue_terms + high_severity_matches)
        )

        explanation = (
            f"Actionable complaint indicators detected in category "
            f"'{primary_category}' with severity '{severity}'."
        )

        return ComplaintDetectionResult(
            is_complaint=confidence >= 0.55,
            confidence=confidence,
            severity=severity,
            category=primary_category,
            matched_terms=matched_terms,
            explanation=explanation,
        )


# Added for M1 client-facing relevance refinement.
EXTRA_CLIENT_COMPLAINT_TERMS = [
    "الشكوى لديكم",
    "الشكوى لها أسبوع",
    "لم تحل",
    "لم يتم حلها",
    "عدم حلها",
    "دون حلول",
    "رفعت شكوى",
    "رفع شكوى",
    "تقديم شكوى",
    "البنك المركزي",
    "عدم الثقة",
    "لا ارغب بفضحكم",
    "راح يتم نشرها",
    "تدليس",
    "تكذبون",
    "غير مقبول",
    "تعطيل جميع عملياتي",
    "أطالب بحل المشكلة",
]


def contains_client_complaint_signal(text: str) -> bool:
    normalized = text or ""
    return any(term in normalized for term in EXTRA_CLIENT_COMPLAINT_TERMS)
