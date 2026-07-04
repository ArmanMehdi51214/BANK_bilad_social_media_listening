from __future__ import annotations

import re
from dataclasses import dataclass, field


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SAUDI_MOBILE_RE = re.compile(r"(?<!\d)(?:\+?966|00966|0)?5\d{8}(?!\d)")
IBAN_RE = re.compile(r"\bSA\d{22}\b", re.IGNORECASE)


@dataclass
class PIIResult:
    original_text: str
    masked_text: str
    contains_pii: bool
    detected_types: list[str] = field(default_factory=list)


def mask_pii(value: str) -> PIIResult:
    text = value or ""
    detected: list[str] = []

    if EMAIL_RE.search(text):
        detected.append("email")
        text = EMAIL_RE.sub("[EMAIL]", text)

    if SAUDI_MOBILE_RE.search(text):
        detected.append("saudi_mobile")
        text = SAUDI_MOBILE_RE.sub("[PHONE]", text)

    if IBAN_RE.search(text):
        detected.append("iban")
        text = IBAN_RE.sub("[IBAN]", text)

    return PIIResult(
        original_text=value or "",
        masked_text=text,
        contains_pii=bool(detected),
        detected_types=detected,
    )
