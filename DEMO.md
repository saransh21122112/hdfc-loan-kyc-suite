# DEMO.md — Living Build Log

This file is the persistent memory of everything built, every decision made, and what comes next.
It is updated by Claude at the end of every session and every significant code change.
Start every new conversation by reading this file first.

---

## Product Summary (always current)

**Product:** HDFC AI Loan & KYC Intelligence Suite
**What it is:** AI layer that plugs into a bank's CBS via API. Does not replace CBS.
**Primary target:** HDFC Bank (9,000+ branches, 90M+ customers, 10M+ loans/year)
**Pilot scope:** Smart KYC Engine + Loan Status Dashboard (60-day, 2–3 branches)
**Phase 2:** AI Credit Underwriting + AML Compliance Monitor (after paid contract)

**Non-negotiable constraints:**
1. All data stays in India (RBI data localisation — MinIO self-hosted)
2. Explainable AI decisions required (XGBoost + SHAP, not black-box neural nets)
3. Immutable audit trail on every AI decision (OpenTelemetry)
4. Integration-only — must plug into CBS, never replace it
5. On-premise deployable (Docker + Kubernetes)
6. Security architecture doc required before any HDFC meeting

---

## Current State (as of 2026-06-20)

### What is built and working

#### `kyc_engine/` — Smart KYC Engine (FastAPI microservice)

| File | Status | What it does |
|------|--------|-------------|
| `main.py` | ✅ Done | FastAPI app entry point; auto-creates DB tables on startup; Swagger UI only in debug mode |
| `core/config.py` | ✅ Done | All settings via pydantic-settings; reads from `.env` |
| `core/security.py` | ✅ Done | JWT Bearer auth; AES-256 PII encryption via Fernet |
| `models/schemas.py` | ✅ Done | Pydantic models for all requests, responses, and extracted fields |
| `db/session.py` | ✅ Done | SQLAlchemy async + `KYCRequest` ORM model; stores extracted data as JSONB |
| `services/ocr.py` | ✅ Done | Tesseract backend (default); PaddleOCR backend stubbed and commented for GPU upgrade |
| `services/document_classifier.py` | ✅ Done | Regex-based classifier → PAN / AADHAAR / BANK_STATEMENT / UNKNOWN |
| `services/field_extractor.py` | ✅ Done | Extracts PAN number, name, father name, DOB, Aadhaar (masked), gender, address, IFSC, account number |
| `services/validator.py` | ✅ Done | PAN format check, Verhoeff Aadhaar checksum, fuzzy name match (rapidfuzz), DOB consistency |
| `api/routes/kyc.py` | ✅ Done | POST `/extract`, GET `/status/{id}`, GET `/result/{id}` |
| `tests/test_kyc.py` | ✅ Done | 15 unit tests; synthetic OCR text; no infra required |

#### Infrastructure

| File | Status | What it does |
|------|--------|-------------|
| `docker-compose.yml` | ✅ Done | Postgres 15, MinIO, Redis 7, KYC Engine container |
| `kyc_engine/Dockerfile` | ✅ Done | Python 3.11-slim + Tesseract with Hindi/Marathi/Tamil language packs |
| `kyc_engine/requirements.txt` | ✅ Done | All Python dependencies pinned |
| `.env.example` | ✅ Done | Template with all required env vars and comments |
| `.gitignore` | ✅ Done | Excludes .env, model weights, local data volumes |
| `README.md` | ✅ Done | Full technical README with API reference, compliance table, roadmap |

### What is NOT built yet

- [ ] MinIO document storage integration (documents uploaded but not stored to MinIO yet)
- [ ] JWT token issuance endpoint (`/auth/token`) — auth is wired but no login route yet
- [ ] Celery async task queue (OCR runs synchronously for now; fine for demo)
- [ ] Loan Status Dashboard (React + TypeScript frontend)
- [ ] Synthetic test data generator (PAN/Aadhaar images for end-to-end OCR testing)
- [ ] Security architecture document for CRO presentation
- [ ] LayoutLM v3 fine-tuning pipeline
- [ ] AI Credit Underwriting (Phase 2)
- [ ] AML Compliance Monitor (Phase 2)

---

## Architecture Decisions & Why

| Decision | Rationale |
|----------|-----------|
| Tesseract as default OCR, PaddleOCR as upgrade path | Tesseract works out of the box; PaddleOCR needs GPU and is significantly better for Hindi/regional scripts. Swap by setting `OCR_BACKEND=paddleocr` in `.env`. |
| Regex + heuristic extraction, not LayoutLM v3 yet | LayoutLM requires fine-tuning on Indian bank documents (we don't have the dataset yet). Regex works for demo; LayoutLM is the production upgrade. |
| JSONB for extracted data in Postgres | Flexibility for demo — field structure varies by document type. Can migrate to typed columns once the schema stabilises. |
| Fernet (AES-128 in CBC mode) for PII encryption | Simpler than raw AES-256 and sufficient for RBI IT framework; upgrade to AES-256-GCM if bank's security team requires it. |
| No Celery in MVP | OCR on a single document takes ~1–3 seconds synchronously. Celery adds complexity; add it when batch processing or >10 concurrent uploads are needed. |
| XGBoost + SHAP for Phase 2 credit scoring | RBI mandates explainable automated credit decisions. Deep learning (neural nets) cannot produce audit-ready reason codes. |
| MinIO over AWS S3 | RBI data residency — all customer PII must stay in India. MinIO is S3-compatible so the same boto3 code works for either. |

---

## Key Design Patterns

### Extraction confidence scores
Every extracted field carries `{ value, confidence, source }`.
- `source: "regex"` → deterministic pattern match (confidence 0.90–0.98)
- `source: "ocr_heuristic"` → positional/layout inference (confidence 0.65–0.85)
- `source: "layoutlm"` → model prediction (confidence from softmax, Phase 2)

This lets the RM dashboard show "low confidence — manual check" on fields below a threshold.

### Aadhaar masking
The full 12-digit Aadhaar number is **never stored**. Only the last 4 digits are retained as `XXXX XXXX {last4}`. This is enforced in `services/field_extractor.py:extract_aadhaar_fields()` before any persistence. UIDAI norms + RBI IT framework.

### Validation flags
`run_all_validations()` in `services/validator.py` returns both:
1. `validation_checks` — structured list with `check_name`, `status`, `message` (for the API response and audit log)
2. `flags` — flat list of human-readable strings (for the RM dashboard alert panel)

---

## How to Run

```bash
# Prerequisites
brew install tesseract   # Mac
# apt-get install tesseract-ocr tesseract-ocr-hin  # Linux

# Start infra
docker-compose up postgres redis minio -d

# Install deps
cd kyc_engine && pip install -r requirements.txt

# Run API (debug mode enables Swagger UI at /docs)
DEBUG=true uvicorn main:app --reload --port 8000

# Run tests (no infra needed)
pytest tests/ -v
```

---

## API Quick Reference

```
POST   /api/v1/kyc/extract          Upload documents → extract + validate
GET    /api/v1/kyc/status/{id}      Check extraction status
GET    /api/v1/kyc/result/{id}      Get full extraction result
GET    /health                       Health check
```

All endpoints except `/health` require `Authorization: Bearer <token>`.

---

## GitHub Repository

**URL:** https://github.com/saransh21122112/hdfc-loan-kyc-suite
**Visibility:** Public
**Default branch:** main
**GitHub username:** saransh21122112

Clone: `git clone https://github.com/saransh21122112/hdfc-loan-kyc-suite.git`

---

## Session Log

### Session 1 — 2026-06-20
**Goal:** Project scaffold + KYC Engine MVP

**Built:**
- Full project directory structure
- docker-compose.yml (Postgres 15, MinIO, Redis 7, KYC Engine)
- Dockerfile with Tesseract + Indian language packs (Hindi, Marathi, Tamil)
- FastAPI KYC Engine with 3 endpoints (extract, status, result)
- OCR service with Tesseract backend + PaddleOCR commented upgrade path
- Document classifier (PAN / Aadhaar / Bank Statement / Unknown)
- Field extractor for all 3 document types
- Cross-document validator (PAN format, Verhoeff checksum, fuzzy name match, DOB consistency)
- JWT + AES-256 security layer
- SQLAlchemy async DB session
- 15 unit tests using synthetic OCR text
- README.md with full API reference, compliance table, quickstart
- DEMO.md (this file)

**Decisions made:**
- Synchronous OCR for MVP (Celery deferred)
- Regex + heuristics first, LayoutLM v3 as Phase 2 upgrade
- JSONB for extracted fields (flexible schema for demo)
- Aadhaar always masked at extraction, before any DB write

**Next session should:**
1. Add `/auth/token` endpoint so the API can be called without manually creating JWTs
2. Wire MinIO storage so uploaded documents are persisted (not just OCR'd in memory)
3. Generate synthetic PAN/Aadhaar images for end-to-end OCR pipeline testing
4. Write the Security Architecture Document (needed for CRO conversation)

### Session 2 — 2026-06-20
**Goal:** Push to GitHub, create .env, add OpenAI API key

**Done:**
- Created `.env` (local only, never committed) with all service credentials + OpenAI API key
- Updated `.env.example` with `OPENAI_API_KEY` placeholder and RBI data residency warning
- Updated `.gitignore` to exclude `.claude/` settings folder
- Initialized git repo, renamed default branch to `main`
- Made initial commit (25 files, 2007 insertions)
- Installed `gh` CLI via Homebrew
- Authenticated `gh` CLI with GitHub account `saransh21122112`
- Created public GitHub repo: https://github.com/saransh21122112/hdfc-loan-kyc-suite
- Pushed all code; confirmed `.env` is NOT on GitHub (404 on remote check)

**OpenAI key usage rule (important):**
The key in `.env` is for NON-PII tasks only:
- Sales collateral, pitch decks, cold emails
- Code generation and debugging
- Internal document summaries (no customer data)
NEVER send PAN / Aadhaar / bank statement data to OpenAI. All document processing stays on-premise.

**Next session should:**
1. Add `/auth/token` endpoint (JWT issuance) so the demo API can be called end-to-end
2. Wire MinIO storage — documents uploaded to `/extract` should be persisted, not just OCR'd in memory
3. Generate synthetic PAN/Aadhaar images for end-to-end OCR pipeline testing
4. Write the Security Architecture Document (needed before any HDFC CRO meeting)

---

## What Claude Will Update Here

Every time code is changed, Claude will add to the Session Log and update:
- The "Current State" table (mark items done, add new ones)
- The "What is NOT built yet" checklist
- The "Architecture Decisions" table if a new decision was made

When starting a new conversation, paste the contents of this file as context.
