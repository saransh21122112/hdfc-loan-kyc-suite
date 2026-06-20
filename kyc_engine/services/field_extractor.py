"""
Extracts structured fields from OCR text per document type.

Regex patterns are the demo baseline. The upgrade path is LayoutLM v3
fine-tuned on Indian banking documents — it handles degraded scans and
non-standard layouts that trip up pure regex.
"""

import re
from typing import Optional

from kyc_engine.models.schemas import (
    AadhaarFields,
    BankStatementFields,
    DocumentType,
    ExtractedField,
    PANFields,
)


# ── PAN Card ──────────────────────────────────────────────────────────────────

_PAN_REGEX = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
_DOB_REGEX = re.compile(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b")
_DOB_LABELED = re.compile(
    r"(?:date\s+of\s+birth|dob|DOB)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})", re.IGNORECASE
)


def extract_pan_fields(text: str) -> PANFields:
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    pan_match = _PAN_REGEX.search(text)
    pan_field = (
        ExtractedField(value=pan_match.group(1), confidence=0.98, source="regex")
        if pan_match else None
    )

    dob_field = _extract_dob(text)
    name_field, father_field = _extract_pan_names(lines)

    return PANFields(
        pan_number=pan_field,
        name=name_field,
        father_name=father_field,
        date_of_birth=dob_field,
    )


def _extract_dob(text: str) -> Optional[ExtractedField]:
    labeled = _DOB_LABELED.search(text)
    if labeled:
        return ExtractedField(value=labeled.group(1), confidence=0.95, source="regex")
    plain = _DOB_REGEX.search(text)
    if plain:
        return ExtractedField(value=plain.group(1), confidence=0.75, source="regex")
    return None


def _extract_pan_names(lines: list) -> tuple:
    """
    PAN card layout:
      ...
      [Applicant Name]
      Father's Name
      [Father Name]
      Date of Birth
      [DD/MM/YYYY]
    """
    name_field = father_field = None

    for i, line in enumerate(lines):
        if re.search(r"father'?s?\s+name", line, re.IGNORECASE):
            # Line before this is the applicant's name; line after is father's name
            if i > 0 and _is_name_line(lines[i - 1]):
                name_field = ExtractedField(
                    value=lines[i - 1].title(), confidence=0.80, source="ocr_heuristic"
                )
            if i + 1 < len(lines) and _is_name_line(lines[i + 1]):
                father_field = ExtractedField(
                    value=lines[i + 1].title(), confidence=0.80, source="ocr_heuristic"
                )
            break

    return name_field, father_field


def _is_name_line(line: str) -> bool:
    """True if line looks like a person's name (letters and spaces, 2–50 chars)."""
    return bool(re.match(r"^[A-Za-z\s]{2,50}$", line.strip()))


# ── Aadhaar Card ──────────────────────────────────────────────────────────────

_AADHAAR_REGEX = re.compile(r"\b(\d{4})\s(\d{4})\s(\d{4})\b")
_GENDER_REGEX = re.compile(r"\b(male|female|transgender)\b", re.IGNORECASE)
_AADHAAR_DOB = re.compile(r"(?:dob|year\s+of\s+birth)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4}|\d{4})", re.IGNORECASE)


def extract_aadhaar_fields(text: str) -> AadhaarFields:
    aadhaar_match = _AADHAAR_REGEX.search(text)
    if aadhaar_match:
        # Always mask — store only last 4 digits visible (RBI/UIDAI norm)
        last4 = aadhaar_match.group(3)
        masked = f"XXXX XXXX {last4}"
        aadhaar_field = ExtractedField(value=masked, confidence=0.98, source="regex")
    else:
        aadhaar_field = None

    dob_field = _extract_aadhaar_dob(text)
    gender_field = _extract_gender(text)
    name_field = _extract_aadhaar_name(text)
    address_field = _extract_address(text)

    return AadhaarFields(
        aadhaar_number_masked=aadhaar_field,
        name=name_field,
        date_of_birth=dob_field,
        gender=gender_field,
        address=address_field,
    )


def _extract_aadhaar_dob(text: str) -> Optional[ExtractedField]:
    m = _AADHAAR_DOB.search(text)
    if m:
        return ExtractedField(value=m.group(1), confidence=0.90, source="regex")
    return _extract_dob(text)  # fallback to generic DOB regex


def _extract_gender(text: str) -> Optional[ExtractedField]:
    m = _GENDER_REGEX.search(text)
    if m:
        return ExtractedField(value=m.group(1).capitalize(), confidence=0.95, source="regex")
    return None


def _extract_aadhaar_name(text: str) -> Optional[ExtractedField]:
    """
    Aadhaar layout typically has the name on the line before DOB/gender.
    Heuristic: find the gender/dob line and take the preceding non-empty line.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if _GENDER_REGEX.search(line) or _AADHAAR_DOB.search(line):
            # Look backwards for a plausible name line
            for j in range(i - 1, max(i - 4, -1), -1):
                if _is_name_line(lines[j]) and len(lines[j]) > 3:
                    return ExtractedField(
                        value=lines[j].title(), confidence=0.72, source="ocr_heuristic"
                    )
    return None


def _extract_address(text: str) -> Optional[ExtractedField]:
    """
    Aadhaar address block follows the S/O or C/O or W/O prefix, or the
    word 'Address:'. Captures up to 5 lines as address.
    """
    addr_match = re.search(
        r"(?:address|s/o|c/o|w/o|house|flat|plot|village|district)[:\s]+(.*)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if addr_match:
        # Take first 300 chars; strip the Aadhaar number if it crept in
        raw = addr_match.group(1)[:300].strip()
        cleaned = _AADHAAR_REGEX.sub("", raw).strip()
        return ExtractedField(value=cleaned, confidence=0.65, source="ocr_heuristic")
    return None


# ── Bank Statement ─────────────────────────────────────────────────────────────

_IFSC_REGEX = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
_ACCOUNT_REGEX = re.compile(r"(?:a/c|account)\s*(?:no\.?|number)[:\s]+(\d[\d\s]{6,20}\d)", re.IGNORECASE)
_BANK_NAME_KEYWORDS = [
    "HDFC", "ICICI", "State Bank", "SBI", "Axis Bank", "Kotak",
    "Punjab National", "PNB", "Bank of Baroda", "Canara",
]


def extract_bank_statement_fields(text: str) -> BankStatementFields:
    ifsc_match = _IFSC_REGEX.search(text)
    ifsc_field = (
        ExtractedField(value=ifsc_match.group(1), confidence=0.97, source="regex")
        if ifsc_match else None
    )

    account_match = _ACCOUNT_REGEX.search(text)
    if account_match:
        raw_acc = re.sub(r"\s", "", account_match.group(1))
        masked_acc = "X" * (len(raw_acc) - 4) + raw_acc[-4:]
        account_field = ExtractedField(value=masked_acc, confidence=0.88, source="regex")
    else:
        account_field = None

    bank_name = _extract_bank_name(text)
    holder_name = _extract_account_holder(text)
    period_from, period_to = _extract_statement_period(text)

    return BankStatementFields(
        account_number_masked=account_field,
        account_holder_name=holder_name,
        bank_name=bank_name,
        ifsc_code=ifsc_field,
        statement_period_from=period_from,
        statement_period_to=period_to,
    )


def _extract_bank_name(text: str) -> Optional[ExtractedField]:
    for name in _BANK_NAME_KEYWORDS:
        if name.lower() in text.lower():
            return ExtractedField(value=name, confidence=0.90, source="keyword")
    return None


def _extract_account_holder(text: str) -> Optional[ExtractedField]:
    m = re.search(
        r"(?:account\s+holder|name|customer)[:\s]+([A-Za-z\s]{3,50})", text, re.IGNORECASE
    )
    if m and _is_name_line(m.group(1)):
        return ExtractedField(value=m.group(1).strip().title(), confidence=0.70, source="ocr_heuristic")
    return None


def _extract_statement_period(text: str) -> tuple:
    dates = _DOB_REGEX.findall(text)
    if len(dates) >= 2:
        return (
            ExtractedField(value=dates[0], confidence=0.70, source="regex"),
            ExtractedField(value=dates[-1], confidence=0.70, source="regex"),
        )
    return None, None


# ── Dispatcher ────────────────────────────────────────────────────────────────

def extract_fields(doc_type: DocumentType, ocr_text: str) -> dict:
    if doc_type == DocumentType.PAN:
        return extract_pan_fields(ocr_text).model_dump()
    if doc_type == DocumentType.AADHAAR:
        return extract_aadhaar_fields(ocr_text).model_dump()
    if doc_type == DocumentType.BANK_STATEMENT:
        return extract_bank_statement_fields(ocr_text).model_dump()
    return {}
