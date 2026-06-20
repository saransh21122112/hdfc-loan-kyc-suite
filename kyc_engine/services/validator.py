"""
Cross-document validation.

Each check returns a ValidationCheck. Flags are human-readable strings
surfaced on the RM dashboard — e.g. "Name mismatch: PAN shows RAHUL SHARMA,
Aadhaar shows RAHUL VERMA."
"""

import re
from typing import List

from rapidfuzz import fuzz

from kyc_engine.models.schemas import DocumentType, ValidationCheck, ValidationStatus


# ── Verhoeff algorithm — Aadhaar checksum (UIDAI spec) ───────────────────────

_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

def _verhoeff_validate(number: str) -> bool:
    digits = [int(d) for d in reversed(number)]
    c = 0
    for i, d in enumerate(digits):
        c = _D[c][_P[i % 8][d]]
    return c == 0


# ── Individual checks ─────────────────────────────────────────────────────────

def check_pan_format(pan_fields: dict) -> ValidationCheck:
    pan_field = pan_fields.get("pan_number") or {}
    pan_value = pan_field.get("value") if pan_field else None

    if not pan_value:
        return ValidationCheck(
            check_name="pan_format",
            status=ValidationStatus.SKIPPED,
            message="PAN number not extracted — cannot validate format.",
        )

    pattern = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    if pattern.match(pan_value):
        return ValidationCheck(
            check_name="pan_format",
            status=ValidationStatus.PASS,
            message=f"PAN format valid: {pan_value}",
        )
    return ValidationCheck(
        check_name="pan_format",
        status=ValidationStatus.FAIL,
        message=f"PAN format invalid: '{pan_value}' does not match [A-Z]{{5}}[0-9]{{4}}[A-Z].",
    )


def check_aadhaar_checksum(aadhaar_fields: dict) -> ValidationCheck:
    masked = (aadhaar_fields.get("aadhaar_number_masked") or {}).get("value")
    if not masked:
        return ValidationCheck(
            check_name="aadhaar_checksum",
            status=ValidationStatus.SKIPPED,
            message="Aadhaar number not extracted — cannot validate checksum.",
        )
    # Checksum requires full 12 digits — masked value has last 4 only,
    # so we flag as SKIPPED (full number is not retained per UIDAI norms)
    return ValidationCheck(
        check_name="aadhaar_checksum",
        status=ValidationStatus.SKIPPED,
        message="Aadhaar stored masked (UIDAI norms). Full checksum not validated.",
    )


def check_name_consistency(
    pan_fields: dict,
    aadhaar_fields: dict,
    threshold: int = 80,
) -> ValidationCheck:
    pan_name = (pan_fields.get("name") or {}).get("value")
    aadhaar_name = (aadhaar_fields.get("name") or {}).get("value")

    if not pan_name or not aadhaar_name:
        return ValidationCheck(
            check_name="name_consistency",
            status=ValidationStatus.SKIPPED,
            message="Name not extracted from one or both documents.",
            documents_compared=["PAN", "AADHAAR"],
        )

    score = fuzz.token_sort_ratio(pan_name.upper(), aadhaar_name.upper())

    if score >= threshold:
        return ValidationCheck(
            check_name="name_consistency",
            status=ValidationStatus.PASS,
            message=f"Names match (similarity {score}%): PAN='{pan_name}', Aadhaar='{aadhaar_name}'",
            documents_compared=["PAN", "AADHAAR"],
        )
    if score >= 60:
        return ValidationCheck(
            check_name="name_consistency",
            status=ValidationStatus.WARNING,
            message=(
                f"Name similarity {score}% — possible mismatch or nickname/abbreviation. "
                f"PAN='{pan_name}', Aadhaar='{aadhaar_name}'. Manual review recommended."
            ),
            documents_compared=["PAN", "AADHAAR"],
        )
    return ValidationCheck(
        check_name="name_consistency",
        status=ValidationStatus.FAIL,
        message=(
            f"Name mismatch (similarity {score}%): PAN shows '{pan_name}', "
            f"Aadhaar shows '{aadhaar_name}'. Possible forgery or document mix-up."
        ),
        documents_compared=["PAN", "AADHAAR"],
    )


def check_dob_consistency(pan_fields: dict, aadhaar_fields: dict) -> ValidationCheck:
    pan_dob = (pan_fields.get("date_of_birth") or {}).get("value")
    aadhaar_dob = (aadhaar_fields.get("date_of_birth") or {}).get("value")

    if not pan_dob or not aadhaar_dob:
        return ValidationCheck(
            check_name="dob_consistency",
            status=ValidationStatus.SKIPPED,
            message="DOB not extracted from one or both documents.",
            documents_compared=["PAN", "AADHAAR"],
        )

    # Normalise separators before comparing
    pan_dob_norm = pan_dob.replace("-", "/")
    aadhaar_dob_norm = aadhaar_dob.replace("-", "/")

    if pan_dob_norm == aadhaar_dob_norm:
        return ValidationCheck(
            check_name="dob_consistency",
            status=ValidationStatus.PASS,
            message=f"Date of birth matches across PAN and Aadhaar: {pan_dob}",
            documents_compared=["PAN", "AADHAAR"],
        )
    return ValidationCheck(
        check_name="dob_consistency",
        status=ValidationStatus.FAIL,
        message=(
            f"Date of birth mismatch: PAN shows '{pan_dob}', Aadhaar shows '{aadhaar_dob}'. "
            "Flag for manual review."
        ),
        documents_compared=["PAN", "AADHAAR"],
    )


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_all_validations(document_results: list) -> tuple[List[ValidationCheck], List[str]]:
    """
    Given a list of DocumentResult dicts, run all applicable checks.
    Returns (validation_checks, flags).
    """
    by_type: dict = {}
    for doc in document_results:
        dt = doc.get("document_type")
        by_type[dt] = doc.get("extracted_fields", {})

    checks: List[ValidationCheck] = []
    flags: List[str] = []

    pan_fields = by_type.get(DocumentType.PAN, {})
    aadhaar_fields = by_type.get(DocumentType.AADHAAR, {})

    if pan_fields:
        checks.append(check_pan_format(pan_fields))

    if aadhaar_fields:
        checks.append(check_aadhaar_checksum(aadhaar_fields))

    if pan_fields and aadhaar_fields:
        checks.append(check_name_consistency(pan_fields, aadhaar_fields))
        checks.append(check_dob_consistency(pan_fields, aadhaar_fields))

    for check in checks:
        if check.status == ValidationStatus.FAIL:
            flags.append(f"[FAIL] {check.message}")
        elif check.status == ValidationStatus.WARNING:
            flags.append(f"[WARNING] {check.message}")

    return checks, flags
