from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.ai.preprocessing.arabic_text import normalize_arabic_text


@dataclass
class SentimentResult:
    label: str
    score: float
    confidence: float
    explanation: str
    positive_terms: list[str] = field(default_factory=list)
    negative_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class BaselineArabicSentimentAnalyzer:
    """
    Baseline Arabic sentiment analyzer.

    Business purpose:
    Provides an initial management reporting signal before replacing the engine
    with a transformer model such as MARBERT, AraBERT, CAMeLBERT, or XLM-R.

    Labels:
    - positive
    - negative
    - neutral
    - mixed
    """

    POSITIVE_TERMS = [
        "ممتاز",
        "ممتازه",
        "رائع",
        "رائعه",
        "جميل",
        "جميله",
        "جيد",
        "جيده",
        "تمام",
        "حلو",
        "سهل",
        "سهله",
        "سريع",
        "سريعه",
        "شكرا",
        "شكراً",
        "يعطيكم العافيه",
        "ما قصرتوا",
        "افضل",
        "افضل بنك",
        "محترم",
        "متعاون",
        "تم الحل",
        "انحلت",
        "اشكر",
        "نشكر",
    ]

    NEGATIVE_TERMS = [
        "مشكله",
        "مشكلة",
        "مشاكل",
        "سيء",
        "سيئ",
        "سيئه",
        "سيئة",
        "فشل",
        "فاشل",
        "تعطل",
        "متعطل",
        "لا يعمل",
        "ما يعمل",
        "ما يشتغل",
        "مو شغال",
        "تجميد",
        "تجمد",
        "معلق",
        "معلقه",
        "تأخير",
        "تاخير",
        "انتظار",
        "زحمه",
        "زحمة",
        "رفض",
        "مرفوض",
        "خصم",
        "خصمتوا",
        "خطأ",
        "خطا",
        "غلط",
        "غير مقبول",
        "بدون اشعار",
        "بدون إشعار",
        "شكوى",
        "اشتكي",
        "بلاغ",
        "احتيال",
        "نصب",
        "سرقه",
        "سرقة",
        "خساره",
        "خسارة",
        "سيئ جدا",
        "اسوء",
        "أسوء",
        "اسوء بنك",
    ]

    NEGATIVE_ISSUE_TERMS = [
        "تجميد",
        "تعطل",
        "لا يعمل",
        "ما يشتغل",
        "احتيال",
        "سرقه",
        "سرقة",
        "خصم",
        "رفض",
        "مشكله",
        "شكوى",
        "بلاغ",
        "غير مقبول",
    ]

    def __init__(self) -> None:
        self.positive_terms_normalized = [
            normalize_arabic_text(term) for term in self.POSITIVE_TERMS
        ]
        self.negative_terms_normalized = [
            normalize_arabic_text(term) for term in self.NEGATIVE_TERMS
        ]
        self.issue_terms_normalized = [
            normalize_arabic_text(term) for term in self.NEGATIVE_ISSUE_TERMS
        ]

    @staticmethod
    def _matched_terms(text: str, terms: list[str]) -> list[str]:
        return [term for term in terms if term and term in text]

    def analyze(self, text: str) -> SentimentResult:
        text = text or ""
        normalized_text = normalize_arabic_text(text)

        positive_matches = self._matched_terms(
            normalized_text,
            self.positive_terms_normalized,
        )
        negative_matches = self._matched_terms(
            normalized_text,
            self.negative_terms_normalized,
        )
        issue_matches = self._matched_terms(
            normalized_text,
            self.issue_terms_normalized,
        )

        positive_count = len(set(positive_matches))
        negative_count = len(set(negative_matches))

        # Issue terms are more important for executive reporting.
        weighted_negative_count = negative_count + len(set(issue_matches))

        if positive_count == 0 and weighted_negative_count == 0:
            return SentimentResult(
                label="neutral",
                score=0.0,
                confidence=0.55,
                explanation="No clear positive or negative sentiment indicators were detected.",
                positive_terms=[],
                negative_terms=[],
            )

        raw_score = (positive_count - weighted_negative_count) / max(
            positive_count + weighted_negative_count,
            1,
        )

        if positive_count > 0 and weighted_negative_count > 0 and abs(raw_score) <= 0.34:
            label = "mixed"
            confidence = 0.65
            explanation = "Both positive and negative indicators were detected."
        elif raw_score > 0.20:
            label = "positive"
            confidence = min(0.90, 0.60 + abs(raw_score) * 0.30)
            explanation = "Positive sentiment indicators were detected."
        elif raw_score < -0.20:
            label = "negative"
            confidence = min(0.95, 0.65 + abs(raw_score) * 0.30)
            explanation = "Negative sentiment or customer issue indicators were detected."
        else:
            label = "neutral"
            confidence = 0.60
            explanation = "Sentiment indicators were weak or balanced."

        return SentimentResult(
            label=label,
            score=round(raw_score, 4),
            confidence=round(confidence, 4),
            explanation=explanation,
            positive_terms=sorted(set(positive_matches)),
            negative_terms=sorted(set(negative_matches)),
        )
