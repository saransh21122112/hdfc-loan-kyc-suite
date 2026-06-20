from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    PAN = "PAN"
    AADHAAR = "AADHAAR"
    BANK_STATEMENT = "BANK_STATEMENT"
    UNKNOWN = "UNKNOWN"


class KYCStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"


# ── Extracted Field Models ────────────────────────────────────────────────────

class ExtractedField(BaseModel):
    value: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # e.g. "regex", "ocr_heuristic", "layoutlm"


class PANFields(BaseModel):
    pan_number: Optional[ExtractedField] = None
    name: Optional[ExtractedField] = None
    father_name: Optional[ExtractedField] = None
    date_of_birth: Optional[ExtractedField] = None


class AadhaarFields(BaseModel):
    aadhaar_number_masked: Optional[ExtractedField] = None  # always masked (XXXX XXXX 1234)
    name: Optional[ExtractedField] = None
    date_of_birth: Optional[ExtractedField] = None
    gender: Optional[ExtractedField] = None
    address: Optional[ExtractedField] = None


class BankStatementFields(BaseModel):
    account_number_masked: Optional[ExtractedField] = None
    account_holder_name: Optional[ExtractedField] = None
    bank_name: Optional[ExtractedField] = None
    ifsc_code: Optional[ExtractedField] = None
    statement_period_from: Optional[ExtractedField] = None
    statement_period_to: Optional[ExtractedField] = None


# ── Document Result ───────────────────────────────────────────────────────────

class DocumentResult(BaseModel):
    document_id: str
    file_name: str
    document_type: DocumentType
    ocr_confidence: float = Field(ge=0.0, le=1.0)
    extracted_fields: Dict[str, Any]  # PANFields | AadhaarFields | BankStatementFields
    raw_text_preview: str = ""  # first 500 chars of OCR text (for audit)


# ── Validation Result ─────────────────────────────────────────────────────────

class ValidationCheck(BaseModel):
    check_name: str
    status: ValidationStatus
    message: str
    documents_compared: List[str] = []


# ── API Request / Response ────────────────────────────────────────────────────

class KYCExtractionResponse(BaseModel):
    request_id: UUID
    applicant_id: str
    status: KYCStatus
    documents_processed: int
    document_results: List[DocumentResult]
    validation_checks: List[ValidationCheck]
    flags: List[str]  # human-readable issues for the RM dashboard
    processing_time_ms: int
    created_at: datetime


class KYCStatusResponse(BaseModel):
    request_id: UUID
    applicant_id: str
    status: KYCStatus
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
