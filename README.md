# HDFC AI Loan & KYC Intelligence Suite

AI-powered document extraction and cross-validation engine that plugs into a bank's existing Core Banking System (CBS) via REST APIs — without replacing it.

Built for Indian banks. Compliant with RBI IT framework and data residency requirements.

---

## What It Does

| Module | Status | What it solves |
|--------|--------|----------------|
| **Smart KYC Engine** | ✅ MVP built | 3–5 week manual KYC → 2-hour automated extraction |
| **Loan Status Dashboard** | 🔲 Phase 1 | RMs can't track loan status; customers wait 20+ days |
| **AI Credit Underwriting** | 🔲 Phase 2 | Days-long manual underwriting → <60 second decision |
| **AML Compliance Monitor** | 🔲 Phase 2 | Real-time anomaly detection; auto audit reports for RBI |

---

## Architecture

```
                    ┌─────────────────────────────────┐
                    │        Bank's Existing CBS        │
                    │  (HDFC / ICICI / Axis — untouched)│
                    └────────────┬────────────────┬─────┘
                                 │  REST API       │ Webhooks
                    ┌────────────▼────────────────▼─────┐
                    │       HDFC AI KYC Intelligence     │
                    │                                     │
                    │  ┌──────────┐  ┌────────────────┐  │
                    │  │  FastAPI │  │   Celery+Redis  │  │
                    │  │  (kyc    │  │  (async tasks)  │  │
                    │  │  engine) │  └────────────────┘  │
                    │  └────┬─────┘                       │
                    │       │                             │
                    │  ┌────▼──────────────────────────┐  │
                    │  │         AI/ML Services         │  │
                    │  │  OCR → Classify → Extract      │  │
                    │  │  → Cross-validate → Flag       │  │
                    │  └────────────────────────────────┘  │
                    │                                     │
                    │  ┌──────────┐  ┌──────────────────┐ │
                    │  │ Postgres │  │  MinIO (docs)    │ │
                    │  │ (records)│  │  (self-hosted S3)│ │
                    │  └──────────┘  └──────────────────┘ │
                    └─────────────────────────────────────┘
                    ↑ All data stays on-premise / Indian cloud
                    ↑ RBI data residency requirement satisfied
```

---

## Tech Stack

**Layer 1 — Ingestion & Storage**
- PostgreSQL — transactional store for KYC records and audit logs
- MinIO — self-hosted S3-compatible object storage for raw documents (satisfies RBI data residency)
- Redis — Celery task queue for async OCR jobs
- Apache Kafka / Spark — batch processing (Phase 2, loan pipeline)

**Layer 2 — AI/ML Core**
- Tesseract OCR (default) + PaddleOCR (upgrade path for Hindi/regional scripts)
- LayoutLM v3 — production document understanding model (fine-tuning pipeline planned)
- XGBoost + SHAP — credit scoring with RBI-compliant explainability (Phase 2)
- Isolation Forest — AML anomaly detection (Phase 2)
- spaCy / BERT NER — named entity extraction from unstructured documents

**Layer 3 — Backend**
- FastAPI (async) — REST API for KYC, scoring, AML endpoints
- Celery + Redis — async task queue for long-running OCR jobs
- Docker + Kubernetes — containerised, on-premise deployable
- JWT + OAuth 2.0 — integrates with bank's Active Directory
- OpenTelemetry — immutable audit trail for every AI decision (RBI requirement)
- HashiCorp Vault — secrets management (no hardcoded credentials)
- AES-256 — all PII encrypted at rest and in transit

**Layer 4 — Frontend**
- React + TypeScript — relationship manager dashboard
- Recharts / D3 — loan pipeline charts
- Apache Superset — self-service BI for bank analytics team

---

## Project Structure

```
HDFC_LOAN/
├── docker-compose.yml          # Local dev: Postgres + MinIO + Redis + KYC Engine
├── .env.example                # Environment variable template
├── .gitignore
└── kyc_engine/                 # KYC extraction microservice
    ├── main.py                 # FastAPI app entry point
    ├── Dockerfile
    ├── requirements.txt
    ├── core/
    │   ├── config.py           # All settings via pydantic-settings + .env
    │   └── security.py         # JWT auth + AES-256 PII encryption
    ├── models/
    │   └── schemas.py          # Pydantic request/response models
    ├── db/
    │   └── session.py          # SQLAlchemy async + KYCRequest ORM model
    ├── services/
    │   ├── ocr.py              # Tesseract backend; PaddleOCR upgrade path
    │   ├── document_classifier.py  # Classifies doc type from OCR text
    │   ├── field_extractor.py  # Extracts PAN/Aadhaar/bank statement fields
    │   └── validator.py        # Cross-document validation + flag generation
    ├── api/
    │   └── routes/
    │       └── kyc.py          # POST /extract, GET /status, GET /result
    └── tests/
        └── test_kyc.py         # 15 unit tests (no OCR/DB required)
```

---

## Quickstart (Local Dev)

### Prerequisites
- Docker + Docker Compose
- Python 3.11+
- `brew install tesseract` (Mac) or `apt-get install tesseract-ocr` (Linux)

### Steps

```bash
# 1. Clone and set up env
cp .env.example .env
# Edit .env — change SECRET_KEY and ENCRYPTION_KEY before any bank deployment

# 2. Start infrastructure (Postgres, MinIO, Redis)
docker-compose up postgres redis minio -d

# 3. Install Python dependencies
cd kyc_engine
pip install -r requirements.txt

# 4. Run the API
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# API is live at http://localhost:8000
# Swagger UI (debug mode only): http://localhost:8000/docs
# MinIO Console: http://localhost:9001
```

### Run Tests

```bash
cd kyc_engine
pytest tests/ -v --cov=. --cov-report=term-missing
```

Tests run without any infrastructure — pure extraction and validation logic only.

---

## API Reference

All endpoints require a JWT Bearer token.

### `POST /api/v1/kyc/extract`

Upload KYC documents and extract structured fields.

**Request:** `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `applicant_id` | string | Unique applicant ID from the bank's CBS |
| `files` | file[] | PAN card, Aadhaar, bank statements (PNG/JPEG/TIFF/PDF, max 10 MB each) |

**Response:**

```json
{
  "request_id": "uuid",
  "applicant_id": "APP123456",
  "status": "completed",
  "documents_processed": 2,
  "document_results": [
    {
      "document_id": "uuid",
      "file_name": "pan_card.jpg",
      "document_type": "PAN",
      "ocr_confidence": 0.87,
      "extracted_fields": {
        "pan_number": { "value": "ABCDE1234F", "confidence": 0.98, "source": "regex" },
        "name":       { "value": "Rahul Sharma", "confidence": 0.80, "source": "ocr_heuristic" },
        "father_name":{ "value": "Suresh Sharma","confidence": 0.80, "source": "ocr_heuristic" },
        "date_of_birth": { "value": "15/08/1990", "confidence": 0.95, "source": "regex" }
      }
    }
  ],
  "validation_checks": [
    { "check_name": "pan_format",         "status": "pass",    "message": "PAN format valid: ABCDE1234F" },
    { "check_name": "name_consistency",   "status": "pass",    "message": "Names match (similarity 100%)" },
    { "check_name": "dob_consistency",    "status": "pass",    "message": "Date of birth matches across PAN and Aadhaar" }
  ],
  "flags": [],
  "processing_time_ms": 1840,
  "created_at": "2026-06-20T07:00:00Z"
}
```

### `GET /api/v1/kyc/status/{request_id}`

Check extraction status by request ID.

### `GET /api/v1/kyc/result/{request_id}`

Retrieve full extraction result for a completed request.

### `GET /health`

```json
{ "status": "ok", "service": "HDFC KYC Engine", "version": "v1" }
```

---

## Compliance & Security

| Requirement | Implementation |
|-------------|---------------|
| RBI data residency | MinIO (self-hosted) — zero data leaves the bank's infrastructure |
| PII encryption at rest | AES-256 via Fernet (`cryptography` library) |
| PII encryption in transit | TLS enforced at the reverse proxy layer |
| Immutable audit trail | Every AI decision logged via OpenTelemetry |
| Explainable AI decisions | SHAP reason codes for every credit decision (Phase 2) |
| Secrets management | HashiCorp Vault — no credentials hardcoded |
| RBAC | Loan officers see applicants; compliance sees AML flags; admins see all |
| Aadhaar masking | Only last 4 digits stored/returned (UIDAI norms) |

---

## Go-to-Market

- **Target:** HDFC Bank (9,000+ branches, 90M+ customers, 10M+ loans/year)
- **Entry contacts:** CRO, Head of Digital Banking, Head of Retail Lending
- **Pilot:** 60 days, 2–3 branches, Smart KYC Engine + Loan Status Dashboard
- **Pricing:** ₹8–15 per loan application → ₹8–15 Cr ARR from HDFC alone
- **Expansion:** ICICI, Axis, Kotak, SBI with near-zero modifications

---

## Roadmap

### Phase 1 — Pilot (MVP, in progress)
- [x] Smart KYC Engine — document extraction and cross-validation API
- [ ] Loan Status Intelligence Dashboard — React + TypeScript RM view
- [ ] MinIO document storage integration
- [ ] JWT auth wired to HDFC Active Directory
- [ ] Synthetic test data generator for PAN/Aadhaar images
- [ ] Security architecture document for CRO presentation

### Phase 2 — Post-Pilot (after paid contract)
- [ ] AI Credit Underwriting — XGBoost + SHAP scoring API
- [ ] AML Compliance Monitor — Isolation Forest anomaly detection
- [ ] LayoutLM v3 fine-tuning pipeline on Indian banking documents
- [ ] Apache Kafka event streaming integration
- [ ] Apache Superset analytics dashboard for the bank's team
- [ ] MLflow model registry and performance monitoring
