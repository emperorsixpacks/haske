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
from .schemas import EXTRACTION_SCHEMA, ExtractionResult, FieldConfidence

_PROMPT = (
    "Read the product label in this image. Extract every field in the JSON schema below. "
    "Return ONLY valid JSON, no commentary, no markdown fences.\n\n"
    "Rules:\n"
    "1. If a field is not visible or legible, set its value to null and confidence to 0.0, "
    "and add a short note to legibility_notes.\n"
    "2. Dates must use YYYY-MM-DD. If only month and year are shown (e.g. '08/2027'), "
    "use the last day of that month: '2027-08-31'.\n"
    "3. For nrn, copy the NAFDAC number exactly as printed. Do not infer or reconstruct it. "
    "Common patterns: 'A4-100160', 'B2-0451'.\n"
    "4. For batch, copy the batch/lot code exactly as printed.\n"
    "5. For shelf_life_months, extract the stated shelf life in months if printed "
    "(e.g. '24 months' -> 24). Set to null if not printed.\n"
    "6. For layout_flags, inspect the label and list every anomaly you observe using "
    "the token prefixes in the schema. An empty list means no anomalies observed.\n"
    "7. For boxes, return normalized bounding boxes with coordinates between 0 and 1 for "
    "each field you located. Omit a field's box if you cannot localize it.\n\n"
    "Schema:\n"
    + EXTRACTION_SCHEMA
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
    # Sanitise layout_flags: keep only strings that start with a known prefix.
    raw_flags = parsed.get("layout_flags") or []
    from .schemas import LAYOUT_FLAG_PREFIXES
    layout_flags = [
        f for f in raw_flags
        if isinstance(f, str) and any(f.startswith(p) for p in LAYOUT_FLAG_PREFIXES)
    ]
    # shelf_life_months must be a positive integer or null.
    slm = parsed.get("shelf_life_months")
    shelf_life_months: int | None = None
    if isinstance(slm, (int, float)) and slm > 0:
        shelf_life_months = int(slm)
    return ExtractionResult(
        product_name=parsed.get("product_name"),
        nrn=parsed.get("nrn"),
        batch=parsed.get("batch"),
        manufacture_date=parsed.get("manufacture_date"),
        expiry_date=parsed.get("expiry_date"),
        manufacturer=parsed.get("manufacturer"),
        strength=parsed.get("strength"),
        category_guess=parsed.get("category_guess"),
        shelf_life_months=shelf_life_months,
        confidence=FieldConfidence(**confidence),
        legibility_notes=list(parsed.get("legibility_notes") or []),
        layout_flags=layout_flags,
        boxes=_clean_boxes(parsed.get("boxes")),
    )


def _clean_boxes(raw: dict | None) -> dict[str, list[float]]:
    """Keep only well-formed normalized boxes: four numbers in [0, 1]."""
    if not isinstance(raw, dict):
        return {}
    boxes: dict[str, list[float]] = {}
    for key, value in raw.items():
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            continue
        try:
            coords = [float(v) for v in value]
        except (TypeError, ValueError):
            continue
        if all(0.0 <= c <= 1.0 for c in coords) and coords[2] > coords[0] and coords[3] > coords[1]:
            boxes[str(key)] = coords
    return boxes


def _unreadable(reason: str) -> ExtractionResult:
    return ExtractionResult(
        confidence=FieldConfidence(),
        legibility_notes=[f"unreadable: {reason}"],
    )
