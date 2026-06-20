FROM python:3.11-slim

# Tesseract OCR + poppler (PDF conversion) + OpenCV deps
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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source into kyc_engine/ so package imports resolve correctly
COPY . ./kyc_engine/

EXPOSE 8000

CMD ["uvicorn", "kyc_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
