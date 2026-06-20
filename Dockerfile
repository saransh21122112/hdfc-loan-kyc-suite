# ── Stage 1: Build React frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# Output: /frontend/dist/

# ── Stage 2: Python backend + static files ────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-mar \
    tesseract-ocr-tam \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY kyc_engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kyc_engine/ ./kyc_engine/

# Copy the built React app — FastAPI will serve it at /
COPY --from=frontend-build /frontend/dist ./static/

EXPOSE 8000

CMD ["uvicorn", "kyc_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
