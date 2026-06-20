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

# Pre-built React app (built locally, committed to repo)
# FastAPI serves it at / via StaticFiles mount in main.py
COPY frontend/dist/ ./static/

EXPOSE 8000

CMD ["uvicorn", "kyc_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
