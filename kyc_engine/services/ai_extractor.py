"""
GPT-4o Vision extractor — primary extraction path when OPENAI_API_KEY is set.
Sends the document image directly to GPT-4o; returns structured fields + doc type.

COMPLIANCE NOTE: This path is for demo purposes only.
In production deployment at HDFC Bank, replace with a self-hosted vision model
(e.g., Qwen-VL, InternVL2) running on-premise to satisfy RBI data residency rules.
Customer PAN/Aadhaar data must never leave Indian data centres.
"""

import base64
import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a KYC document extraction engine for an Indian bank.
You will receive an image of an Indian identity or financial document.

Extract all visible fields and return ONLY a JSON object with this exact structure:

{
  "document_type": "PAN" | "AADHAAR" | "BANK_STATEMENT" | "UNKNOWN",
  "confidence": <float 0.0-1.0>,
  "fields": {
    <field_name>: { "value": <string or null>, "confidence": <float> }
  }
}

For PAN cards, fields must include:
  pan_number, name, father_name, date_of_birth

For Aadhaar cards, fields must include:
  aadhaar_number_masked (format: "XXXX XXXX NNNN" — NEVER store full number),
  name, date_of_birth, gender, address

For bank statements, fields must include:
  account_number_masked (last 4 digits only, prefix with X),
  account_holder_name, bank_name, ifsc_code,
  statement_period_from, statement_period_to

Rules:
- Return ONLY the JSON. No markdown, no explanation.
- If a field is not visible or legible, set value to null.
- For Aadhaar: ALWAYS mask to "XXXX XXXX NNNN" — never return the full 12-digit number.
- For account numbers: ALWAYS mask all but last 4 digits.
- confidence is your certainty that the extracted value is correct (0.0–1.0).
"""


@dataclass
class AIExtractionResult:
    document_type: str
    confidence: float
    fields: dict
    raw_response: str


def extract_with_gpt4o(image_bytes: bytes, filename: str) -> Optional[AIExtractionResult]:
    """
    Returns AIExtractionResult or None if OpenAI is unavailable/key not set.
    Caller falls back to Tesseract on None.
    """
    try:
        from openai import OpenAI
        from kyc_engine.core.config import settings

        if not settings.openai_api_key:
            return None

        client = OpenAI(api_key=settings.openai_api_key)

        # Encode image to base64
        b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Detect MIME type from extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpeg"
        mime = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "tiff": "image/tiff", "webp": "image/webp",
        }.get(ext, "image/jpeg")

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
                        },
                        {"type": "text", "text": "Extract all KYC fields from this document."},
                    ],
                },
            ],
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if GPT wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)

        return AIExtractionResult(
            document_type=parsed.get("document_type", "UNKNOWN"),
            confidence=float(parsed.get("confidence", 0.0)),
            fields=parsed.get("fields", {}),
            raw_response=raw,
        )

    except Exception as e:
        logger.warning(f"GPT-4o extraction failed for {filename}: {e}")
        return None
