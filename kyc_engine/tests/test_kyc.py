"""
Unit tests for field extraction and validation logic.
No OCR or DB required — these test the pure extraction/validation functions
using synthetic text that mimics Tesseract output from real Indian documents.
"""

import pytest
from kyc_engine.services.document_classifier import classify_document
from kyc_engine.services.field_extractor import (
    extract_aadhaar_fields,
    extract_bank_statement_fields,
    extract_pan_fields,
)
from kyc_engine.services.validator import (
    check_dob_consistency,
    check_name_consistency,
    check_pan_format,
    run_all_validations,
)
from kyc_engine.models.schemas import DocumentType, ValidationStatus


# ── Synthetic OCR text ────────────────────────────────────────────────────────

SYNTHETIC_PAN_TEXT = """
INCOME TAX DEPARTMENT
GOVT. OF INDIA

RAHUL SHARMA
Father's Name
SURESH SHARMA
Date of Birth
15/08/1990

ABCDE1234F
Permanent Account Number Card
"""

SYNTHETIC_AADHAAR_TEXT = """
Government of India
RAHUL SHARMA
Male  DOB: 15/08/1990
1234 5678 9012
Address: 42, MG Road, Bengaluru, Karnataka - 560001
"""

SYNTHETIC_AADHAAR_NAME_MISMATCH = """
Government of India
RAHUL VERMA
Male  DOB: 15/08/1990
1234 5678 9012
"""

SYNTHETIC_BANK_TEXT = """
HDFC Bank
Account Statement
Account No.: XXXX XXXX 4567
Account Holder: Rahul Sharma
IFSC Code: HDFC0001234
Statement Period: 01/04/2024 to 31/03/2025
Opening Balance: 12,500.00
"""


# ── Document classifier ───────────────────────────────────────────────────────

class TestDocumentClassifier:
    def test_classifies_pan(self):
        assert classify_document(SYNTHETIC_PAN_TEXT) == DocumentType.PAN

    def test_classifies_aadhaar(self):
        assert classify_document(SYNTHETIC_AADHAAR_TEXT) == DocumentType.AADHAAR

    def test_classifies_bank_statement(self):
        assert classify_document(SYNTHETIC_BANK_TEXT) == DocumentType.BANK_STATEMENT

    def test_unknown_document(self):
        assert classify_document("Random unrecognised document text") == DocumentType.UNKNOWN


# ── PAN field extraction ──────────────────────────────────────────────────────

class TestPANExtraction:
    def setup_method(self):
        self.fields = extract_pan_fields(SYNTHETIC_PAN_TEXT)

    def test_extracts_pan_number(self):
        assert self.fields.pan_number is not None
        assert self.fields.pan_number.value == "ABCDE1234F"

    def test_extracts_name(self):
        assert self.fields.name is not None
        assert "Rahul" in self.fields.name.value

    def test_extracts_father_name(self):
        assert self.fields.father_name is not None
        assert "Suresh" in self.fields.father_name.value

    def test_extracts_dob(self):
        assert self.fields.date_of_birth is not None
        assert self.fields.date_of_birth.value == "15/08/1990"

    def test_pan_confidence_high(self):
        assert self.fields.pan_number.confidence >= 0.95


# ── Aadhaar field extraction ──────────────────────────────────────────────────

class TestAadhaarExtraction:
    def setup_method(self):
        self.fields = extract_aadhaar_fields(SYNTHETIC_AADHAAR_TEXT)

    def test_extracts_masked_aadhaar(self):
        assert self.fields.aadhaar_number_masked is not None
        assert self.fields.aadhaar_number_masked.value == "XXXX XXXX 9012"

    def test_aadhaar_number_always_masked(self):
        # Full 12-digit number must never appear in the extracted value
        value = self.fields.aadhaar_number_masked.value
        assert "1234" not in value  # first 4 digits must be masked
        assert "5678" not in value  # middle 4 digits must be masked

    def test_extracts_gender(self):
        assert self.fields.gender is not None
        assert self.fields.gender.value == "Male"

    def test_extracts_dob(self):
        assert self.fields.date_of_birth is not None
        assert "1990" in self.fields.date_of_birth.value


# ── Bank statement extraction ─────────────────────────────────────────────────

class TestBankStatementExtraction:
    def setup_method(self):
        self.fields = extract_bank_statement_fields(SYNTHETIC_BANK_TEXT)

    def test_extracts_ifsc(self):
        assert self.fields.ifsc_code is not None
        assert self.fields.ifsc_code.value == "HDFC0001234"

    def test_extracts_bank_name(self):
        assert self.fields.bank_name is not None
        assert "HDFC" in self.fields.bank_name.value


# ── Validation checks ─────────────────────────────────────────────────────────

class TestValidation:
    def test_valid_pan_format(self):
        pan_fields = {"pan_number": {"value": "ABCDE1234F", "confidence": 0.98, "source": "regex"}}
        result = check_pan_format(pan_fields)
        assert result.status == ValidationStatus.PASS

    def test_invalid_pan_format(self):
        pan_fields = {"pan_number": {"value": "12345ABCDE", "confidence": 0.5, "source": "regex"}}
        result = check_pan_format(pan_fields)
        assert result.status == ValidationStatus.FAIL

    def test_missing_pan_skipped(self):
        result = check_pan_format({})
        assert result.status == ValidationStatus.SKIPPED

    def test_name_consistency_pass(self):
        pan = {"name": {"value": "RAHUL SHARMA", "confidence": 0.8, "source": "ocr_heuristic"}}
        aadhaar = {"name": {"value": "Rahul Sharma", "confidence": 0.7, "source": "ocr_heuristic"}}
        result = check_name_consistency(pan, aadhaar)
        assert result.status == ValidationStatus.PASS

    def test_name_consistency_fail(self):
        pan = {"name": {"value": "RAHUL SHARMA", "confidence": 0.8, "source": "ocr_heuristic"}}
        aadhaar = {"name": {"value": "PRIYA PATEL", "confidence": 0.7, "source": "ocr_heuristic"}}
        result = check_name_consistency(pan, aadhaar)
        assert result.status == ValidationStatus.FAIL

    def test_dob_consistency_pass(self):
        pan = {"date_of_birth": {"value": "15/08/1990", "confidence": 0.95, "source": "regex"}}
        aadhaar = {"date_of_birth": {"value": "15/08/1990", "confidence": 0.90, "source": "regex"}}
        result = check_dob_consistency(pan, aadhaar)
        assert result.status == ValidationStatus.PASS

    def test_dob_consistency_fail(self):
        pan = {"date_of_birth": {"value": "15/08/1990", "confidence": 0.95, "source": "regex"}}
        aadhaar = {"date_of_birth": {"value": "20/09/1991", "confidence": 0.90, "source": "regex"}}
        result = check_dob_consistency(pan, aadhaar)
        assert result.status == ValidationStatus.FAIL

    def test_flags_populated_on_mismatch(self):
        pan_fields = extract_pan_fields(SYNTHETIC_PAN_TEXT).model_dump()
        aadhaar_fields = extract_aadhaar_fields(SYNTHETIC_AADHAAR_NAME_MISMATCH).model_dump()
        docs = [
            {"document_type": DocumentType.PAN, "extracted_fields": pan_fields},
            {"document_type": DocumentType.AADHAAR, "extracted_fields": aadhaar_fields},
        ]
        _, flags = run_all_validations(docs)
        assert any("mismatch" in f.lower() or "fail" in f.lower() for f in flags)
