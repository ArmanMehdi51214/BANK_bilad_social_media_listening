from __future__ import annotations

import re
import unicodedata


ARABIC_LETTER_RE = re.compile(r"[\u0600-\u06FF]")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"(?<!\w)@[\w_]+", re.UNICODE)
HASHTAG_RE = re.compile(r"#[\w\u0600-\u06FF_]+", re.UNICODE)
DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")
TATWEEL = "\u0640"

MOJIBAKE_MARKERS = ["Ø", "Ù", "Û", "Ð", "ƒ", "†", "œ", "€"]


def has_arabic(value: str) -> bool:
    return bool(value and ARABIC_LETTER_RE.search(value))


def looks_mojibake(value: str) -> bool:
    if not isinstance(value, str):
        return False
    return any(marker in value for marker in MOJIBAKE_MARKERS)


def _repair_token(value: str) -> str:
    if not looks_mojibake(value):
        return value

    for encoding in ("cp1252", "latin1"):
        try:
            fixed = value.encode(encoding).decode("utf-8")
            if has_arabic(fixed):
                return fixed
        except Exception:
            continue

    return value


def repair_mojibake(value: str) -> str:
    """
    Repairs common Arabic mojibake.

    Works for full mojibake strings and mixed strings:
    Ø¨Ù†Ùƒ Ø§Ù„Ø¨Ù„Ø§Ø¯ ممتاز -> بنك البلاد ممتاز
    """
    if not isinstance(value, str) or not value:
        return ""

    if not looks_mojibake(value):
        return value

    # First try whole-string repair.
    for encoding in ("cp1252", "latin1"):
        try:
            fixed = value.encode(encoding).decode("utf-8")
            if has_arabic(fixed):
                return fixed
        except Exception:
            pass

    # Then repair token-by-token for mixed mojibake + real Arabic.
    parts = re.split(r"(\s+)", value)
    repaired_parts = [_repair_token(part) for part in parts]
    return "".join(repaired_parts)


def normalize_unicode(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "")


def remove_diacritics(value: str) -> str:
    return DIACRITICS_RE.sub("", value or "")


def normalize_arabic_letters(value: str) -> str:
    value = value or ""
    value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    value = value.replace("ؤ", "و").replace("ئ", "ي")
    value = value.replace("ى", "ي")
    value = value.replace("ة", "ه")
    value = value.replace(TATWEEL, "")
    return value


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def collapse_repeated_characters(value: str, max_repeats: int = 2) -> str:
    if not value:
        return ""

    pattern = r"(.)\1{" + str(max_repeats) + r",}"
    return re.sub(pattern, lambda match: match.group(1) * max_repeats, value)


def extract_urls(value: str) -> list[str]:
    return URL_RE.findall(value or "")


def extract_mentions(value: str) -> list[str]:
    return MENTION_RE.findall(value or "")


def extract_hashtags(value: str) -> list[str]:
    return HASHTAG_RE.findall(value or "")


def remove_urls(value: str) -> str:
    return URL_RE.sub(" ", value or "")


def remove_mentions(value: str) -> str:
    return MENTION_RE.sub(" ", value or "")


def clean_for_ai(value: str) -> str:
    """
    Produces readable text for Arabic AI models.
    Keeps hashtags because they often contain campaign/topic signals.
    Removes URLs and mentions because they add noise.
    """
    value = repair_mojibake(value)
    value = normalize_unicode(value)
    value = remove_urls(value)
    value = remove_mentions(value)
    value = value.replace("\n", " ")
    value = collapse_repeated_characters(value)
    value = normalize_whitespace(value)
    return value


def normalize_arabic_text(value: str) -> str:
    """
    Produces normalized Arabic text for matching/search/model features.
    """
    value = repair_mojibake(value)
    value = normalize_unicode(value)
    value = remove_diacritics(value)
    value = normalize_arabic_letters(value)
    value = value.lower()
    value = collapse_repeated_characters(value)
    value = normalize_whitespace(value)
    return value
