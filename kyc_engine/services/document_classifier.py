"""
Classifies OCR text into document types using keyword patterns.
LayoutLM v3 fine-tuned on Indian docs is the production upgrade path;
this regex classifier works well enough for the demo.
"""

import re
from kyc_engine.models.schemas import DocumentType


_PAN_SIGNALS = [
    r"income\s+tax\s+department",
    r"permanent\s+account\s+number",
    r"\bPAN\b",
    r"govt\.?\s+of\s+india",
    r"[A-Z]{5}[0-9]{4}[A-Z]",   # PAN number pattern
]

_AADHAAR_SIGNALS = [
    r"unique\s+identification",
    r"\bUIDAI\b",
    r"government\s+of\s+india",
    r"\d{4}\s\d{4}\s\d{4}",      # Aadhaar number format
    r"aadhaar|आधार",
    r"enrolment\s+no",
]

_BANK_STATEMENT_SIGNALS = [
    r"\bIFSC\b",
    r"account\s+(no|number|no\.)",
    r"statement\s+of\s+account",
    r"opening\s+balance",
    r"closing\s+balance",
    r"transaction\s+(date|id)",
    r"\bdebit\b.{0,30}\bcredit\b",
]


def classify_document(ocr_text: str) -> DocumentType:
    text_lower = ocr_text.lower()

    pan_score = _score(ocr_text, text_lower, _PAN_SIGNALS)
    aadhaar_score = _score(ocr_text, text_lower, _AADHAAR_SIGNALS)
    bank_score = _score(ocr_text, text_lower, _BANK_STATEMENT_SIGNALS)

    best_score = max(pan_score, aadhaar_score, bank_score)
    if best_score == 0:
        return DocumentType.UNKNOWN

    if best_score == pan_score:
        return DocumentType.PAN
    if best_score == aadhaar_score:
        return DocumentType.AADHAAR
    return DocumentType.BANK_STATEMENT


def _score(original: str, lower: str, patterns: list) -> int:
    score = 0
    for pattern in patterns:
        if re.search(pattern, original, re.IGNORECASE):
            score += 1
    return score
