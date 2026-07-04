from __future__ import annotations

import re


ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
LATIN_RE = re.compile(r"[A-Za-z]")


def detect_language(value: str) -> str:
    """
    Lightweight language detection for routing/preprocessing.
    Later we can replace this with fastText or a transformer language detector.
    """
    value = value or ""

    arabic_count = len(ARABIC_RE.findall(value))
    latin_count = len(LATIN_RE.findall(value))

    if arabic_count == 0 and latin_count == 0:
        return "unknown"

    if arabic_count > 0 and latin_count == 0:
        return "ar"

    if latin_count > 0 and arabic_count == 0:
        return "en"

    if arabic_count >= latin_count:
        return "ar"

    return "mixed"
