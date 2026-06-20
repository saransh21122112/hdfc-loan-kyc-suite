"""
OCR service with swappable backends.

Current backend: pytesseract (works out of the box, brew install tesseract)
Upgrade path:    PaddleOCR — better accuracy for Hindi/Marathi/Tamil scripts.
                 To switch, set OCR_BACKEND=paddleocr in .env and uncomment
                 the PaddleOCR backend class below.
"""

import io
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image

from kyc_engine.core.config import settings


@dataclass
class OCRResult:
    text: str
    confidence: float  # 0.0–1.0 mean word confidence


# ── Abstract interface ────────────────────────────────────────────────────────

class BaseOCRBackend(ABC):
    @abstractmethod
    def extract(self, image: Image.Image) -> OCRResult:
        ...


# ── Tesseract backend ─────────────────────────────────────────────────────────

class TesseractBackend(BaseOCRBackend):
    def extract(self, image: Image.Image) -> OCRResult:
        import pytesseract

        # Preprocess: grayscale → Otsu threshold (skip denoising — too slow on CPU)
        img_array = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed = Image.fromarray(thresh)

        # Single Tesseract call — image_to_data gives both text and confidence
        config = "--oem 3 --psm 6 -l eng+hin"
        data = pytesseract.image_to_data(
            processed, config=config, output_type=pytesseract.Output.DICT
        )

        words, confidences = [], []
        for text, conf in zip(data["text"], data["conf"]):
            if text.strip():
                words.append(text)
                if conf != -1:
                    confidences.append(conf / 100.0)

        full_text = " ".join(words)
        mean_conf = float(np.mean(confidences)) if confidences else 0.0

        return OCRResult(text=full_text.strip(), confidence=round(mean_conf, 3))


# ── PaddleOCR backend (uncomment when GPU available) ─────────────────────────
# class PaddleOCRBackend(BaseOCRBackend):
#     def __init__(self):
#         from paddleocr import PaddleOCR
#         self._ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=True)
#
#     def extract(self, image: Image.Image) -> OCRResult:
#         img_array = np.array(image.convert("RGB"))
#         result = self._ocr.ocr(img_array, cls=True)
#         lines, scores = [], []
#         for line in result[0] or []:
#             text, score = line[1]
#             lines.append(text)
#             scores.append(score)
#         return OCRResult(
#             text="\n".join(lines),
#             confidence=round(float(np.mean(scores)) if scores else 0.0, 3),
#         )


# ── Factory ───────────────────────────────────────────────────────────────────

def _build_backend() -> BaseOCRBackend:
    if settings.ocr_backend == "paddleocr":
        raise NotImplementedError(
            "PaddleOCR backend requires GPU. "
            "Uncomment PaddleOCRBackend in services/ocr.py and set OCR_BACKEND=paddleocr."
        )
    return TesseractBackend()


_backend: Optional[BaseOCRBackend] = None


def get_backend() -> BaseOCRBackend:
    global _backend
    if _backend is None:
        _backend = _build_backend()
    return _backend


# ── Public API ────────────────────────────────────────────────────────────────

def ocr_from_bytes(file_bytes: bytes, filename: str) -> OCRResult:
    """Accept image or PDF bytes, return OCR text + confidence."""
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        images = _pdf_to_images(file_bytes)
        # OCR all pages, concat text, average confidence
        results = [get_backend().extract(img) for img in images]
        combined_text = "\n\n".join(r.text for r in results)
        mean_conf = float(np.mean([r.confidence for r in results])) if results else 0.0
        return OCRResult(text=combined_text, confidence=round(mean_conf, 3))

    image = Image.open(io.BytesIO(file_bytes))
    return get_backend().extract(image)


def _pdf_to_images(pdf_bytes: bytes) -> List[Image.Image]:
    try:
        from pdf2image import convert_from_bytes
        return convert_from_bytes(pdf_bytes, dpi=300)
    except ImportError:
        raise RuntimeError("pdf2image is not installed. Run: pip install pdf2image")
