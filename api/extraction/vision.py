"""Meta Model API vision extraction (OpenAI-compatible).

The LLM only extracts fields; it never decides a verdict. On invalid output we retry once,
then return low-confidence fields marked unreadable.
"""

from __future__ import annotations

import base64
import json
import re
from abc import ABC, abstractmethod

import httpx

from ..app.config import Settings
from .preprocess import preprocess
from .schemas import ExtractionResult, FieldConfidence

_PROMPT = (
    "Read the product label in this image. Extract the fields described by the JSON schema "
    "below and return ONLY valid JSON, no commentary. If a field is not legible, set its "
    "value to null, set its confidence to 0.0, and add a legibility note.\n\nSchema:\n"
)


class Extractor(ABC):
    @abstractmethod
    def extract(self, image_bytes: bytes, filename: str | None = None) -> ExtractionResult:
        raise NotImplementedError


class VisionExtractor(Extractor):
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._transport = transport

    def extract(self, image_bytes: bytes, filename: str | None = None) -> ExtractionResult:
        image_bytes = preprocess(image_bytes, filename)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"

        payload = {
            "model": self.settings.meta_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0,
        }

        headers = {
            "Authorization": f"Bearer {self.settings.meta_api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(2):
            try:
                with httpx.Client(timeout=60, transport=self._transport) as client:
                    resp = client.post(
                        self.settings.meta_api_base_url.rstrip("/") + "/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"]
            except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                if attempt == 0:
                    continue
                return _unreadable(f"model_call_failed: {type(exc).__name__}")

            parsed = _parse_json(content)
            if parsed is None:
                if attempt == 0:
                    continue
                return _unreadable("model_returned_invalid_json")

            try:
                return _validated(parsed)
            except Exception as exc:  # noqa: BLE001 - pydantic validation error
                if attempt == 0:
                    continue
                return _unreadable(f"model_output_failed_validation: {type(exc).__name__}")

        return _unreadable("extraction_failed")


def _parse_json(content: str) -> dict | None:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _validated(parsed: dict) -> ExtractionResult:
    if not isinstance(parsed, dict):
        raise ValueError("expected JSON object")
    confidence = parsed.get("confidence") or {}
    return ExtractionResult(
        product_name=parsed.get("product_name"),
        nrn=parsed.get("nrn"),
        batch=parsed.get("batch"),
        manufacture_date=parsed.get("manufacture_date"),
        expiry_date=parsed.get("expiry_date"),
        manufacturer=parsed.get("manufacturer"),
        strength=parsed.get("strength"),
        category_guess=parsed.get("category_guess"),
        confidence=FieldConfidence(**confidence),
        legibility_notes=list(parsed.get("legibility_notes") or []),
    )


def _unreadable(reason: str) -> ExtractionResult:
    return ExtractionResult(
        confidence=FieldConfidence(),
        legibility_notes=[f"unreadable: {reason}"],
    )
