from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.ai.preprocessing.arabic_text import (
    clean_for_ai,
    extract_hashtags,
    extract_mentions,
    extract_urls,
    normalize_arabic_text,
    repair_mojibake,
)
from app.ai.preprocessing.language import detect_language
from app.ai.preprocessing.pii import mask_pii


@dataclass
class ArabicPreprocessingResult:
    raw_text: str
    repaired_text: str
    clean_text: str
    normalized_text: str
    detected_language: str
    hashtags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    contains_pii: bool = False
    pii_types: list[str] = field(default_factory=list)
    pii_masked_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ArabicPreprocessingPipeline:
    """
    First production preprocessing layer for Arabic social media text.

    Business purpose:
    Prepare collected posts for sentiment, topic classification, complaint detection,
    competitor detection, and executive reporting.
    """

    def process(self, raw_text: str) -> ArabicPreprocessingResult:
        raw_text = raw_text or ""

        repaired_text = repair_mojibake(raw_text)

        hashtags = extract_hashtags(repaired_text)
        mentions = extract_mentions(repaired_text)
        urls = extract_urls(repaired_text)

        pii_result = mask_pii(repaired_text)

        clean_text = clean_for_ai(pii_result.masked_text)
        normalized_text = normalize_arabic_text(clean_text)
        detected_language = detect_language(repaired_text)

        return ArabicPreprocessingResult(
            raw_text=raw_text,
            repaired_text=repaired_text,
            clean_text=clean_text,
            normalized_text=normalized_text,
            detected_language=detected_language,
            hashtags=hashtags,
            mentions=mentions,
            urls=urls,
            contains_pii=pii_result.contains_pii,
            pii_types=pii_result.detected_types,
            pii_masked_text=pii_result.masked_text,
        )
