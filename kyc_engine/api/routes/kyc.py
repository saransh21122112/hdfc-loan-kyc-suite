import time
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from kyc_engine.core.security import get_current_user
from kyc_engine.db.session import KYCRequest, get_db
from kyc_engine.models.schemas import (
    DocumentResult,
    DocumentType,
    KYCExtractionResponse,
    KYCStatus,
    KYCStatusResponse,
)
from kyc_engine.services.ai_extractor import extract_with_gpt4o
from kyc_engine.services.document_classifier import classify_document
from kyc_engine.services.field_extractor import extract_fields
from kyc_engine.services.ocr import ocr_from_bytes
from kyc_engine.services.validator import run_all_validations

router = APIRouter()

_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/tiff", "application/pdf"}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per document


@router.post(
    "/extract",
    response_model=KYCExtractionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload KYC documents and extract structured fields",
)
async def extract_kyc(
    applicant_id: str = Form(..., description="Unique applicant identifier from the bank's CBS"),
    files: List[UploadFile] = File(..., description="PAN card, Aadhaar, bank statements (image or PDF)"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one document is required.")

    start_ms = time.time()
    request_id = uuid.uuid4()
    document_results = []

    for upload in files:
        if upload.content_type not in _ALLOWED_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type '{upload.content_type}' for '{upload.filename}'. "
                       f"Accepted: PNG, JPEG, TIFF, PDF.",
            )

        file_bytes = await upload.read()
        if len(file_bytes) > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"'{upload.filename}' exceeds 10 MB limit.",
            )

        # ── Primary: GPT-4o Vision (accurate on real-world photos) ──────────
        ai_result = None
        if not upload.filename.lower().endswith(".pdf"):
            ai_result = extract_with_gpt4o(file_bytes, upload.filename or "")

        if ai_result:
            doc_type_str = ai_result.document_type
            try:
                doc_type = DocumentType(doc_type_str)
            except ValueError:
                doc_type = DocumentType.UNKNOWN

            # Normalise GPT-4o field format → internal ExtractedField schema
            fields = {
                k: {"value": v.get("value"), "confidence": v.get("confidence", 0.9), "source": "gpt4o_vision"}
                if isinstance(v, dict) else {"value": v, "confidence": 0.9, "source": "gpt4o_vision"}
                for k, v in ai_result.fields.items()
            }
            ocr_confidence = ai_result.confidence

        else:
            # ── Fallback: Tesseract OCR + regex ──────────────────────────────
            ocr_result = ocr_from_bytes(file_bytes, upload.filename)
            doc_type = classify_document(ocr_result.text, filename=upload.filename or "")
            fields = extract_fields(doc_type, ocr_result.text)
            ocr_confidence = ocr_result.confidence

        document_results.append(
            DocumentResult(
                document_id=str(uuid.uuid4()),
                file_name=upload.filename,
                document_type=doc_type,
                ocr_confidence=ocr_confidence,
                extracted_fields=fields,
                raw_text_preview=ai_result.raw_response[:500] if ai_result else "",
            ).model_dump()
        )

    validation_checks, flags = run_all_validations(document_results)
    processing_ms = int((time.time() - start_ms) * 1000)

    kyc_record = KYCRequest(
        id=request_id,
        applicant_id=applicant_id,
        status=KYCStatus.COMPLETED,
        documents=[{"file_name": d["file_name"], "document_type": d["document_type"]} for d in document_results],
        extracted_data={d["document_id"]: d["extracted_fields"] for d in document_results},
        validation_results=[v.model_dump() for v in validation_checks],
        flags=flags,
        processing_time_ms=processing_ms,
    )
    db.add(kyc_record)
    await db.flush()

    return KYCExtractionResponse(
        request_id=request_id,
        applicant_id=applicant_id,
        status=KYCStatus.COMPLETED,
        documents_processed=len(document_results),
        document_results=[DocumentResult(**d) for d in document_results],
        validation_checks=validation_checks,
        flags=flags,
        processing_time_ms=processing_ms,
        created_at=kyc_record.created_at,
    )


@router.get(
    "/status/{request_id}",
    response_model=KYCStatusResponse,
    summary="Check KYC extraction status by request ID",
)
async def get_kyc_status(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    result = await db.execute(
        select(KYCRequest).where(KYCRequest.id == uuid.UUID(request_id))
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")

    return KYCStatusResponse(
        request_id=record.id,
        applicant_id=record.applicant_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/result/{request_id}",
    response_model=KYCExtractionResponse,
    summary="Retrieve full extraction result",
)
async def get_kyc_result(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    result = await db.execute(
        select(KYCRequest).where(KYCRequest.id == uuid.UUID(request_id))
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")

    from kyc_engine.models.schemas import ValidationCheck
    return KYCExtractionResponse(
        request_id=record.id,
        applicant_id=record.applicant_id,
        status=record.status,
        documents_processed=len(record.documents or []),
        document_results=[
            DocumentResult(**{**d, "extracted_fields": record.extracted_data.get(d.get("document_id", ""), {})})
            for d in (record.documents or [])
        ],
        validation_checks=[ValidationCheck(**v) for v in (record.validation_results or [])],
        flags=record.flags or [],
        processing_time_ms=record.processing_time_ms,
        created_at=record.created_at,
    )
