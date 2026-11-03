"""Two-pass reading: read the whole pack, then re-read cropped critical fields.

Pass 1 reads the full image and returns fields plus normalized boxes. Pass 2 crops each
critical field (NRN, batch, manufacture date, expiry date) and re-reads it at higher
resolution in a separate call. Code computes per-field agreement; disagreement is a signal
(CROSS_PASS_MISMATCH), never a verdict.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from .crop import crop_to_box
from .schemas import ExtractionResult

CRITICAL_FIELDS = ("nrn", "batch", "manufacture_date", "expiry_date")
AGREEMENT_THRESHOLD = 0.6


def normalize(value: str | None) -> str:
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def field_agreement(a: str | None, b: str | None) -> tuple[float, str]:
    """Return (agreement 0..1, status). Exact match is 1.0."""
    an, bn = normalize(a), normalize(b)
    if not an and not bn:
        return 1.0, "both_empty"
    if not an or not bn:
        return 0.0, "one_empty"
    if an == bn:
        return 1.0, "exact"
    return round(difflib.SequenceMatcher(None, an, bn).ratio(), 3), "fuzzy"


@dataclass
class TwoPassResult:
    pass1: dict = field(default_factory=dict)
    pass2: dict = field(default_factory=dict)  # field -> {"value", "confidence"}
    agreements: dict = field(default_factory=dict)  # field -> {"agreement", "status"}
    disagreements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pass1": self.pass1,
            "pass2": self.pass2,
            "agreements": self.agreements,
            "disagreements": self.disagreements,
        }


def two_pass_read(
    extractor,
    image_bytes: bytes,
    fields: tuple[str, ...] = CRITICAL_FIELDS,
    filename: str | None = None,
) -> TwoPassResult:
    pass1_ext: ExtractionResult = extractor.extract(image_bytes, filename)
    pass1 = _fields_dict(pass1_ext)
    boxes = getattr(pass1_ext, "boxes", {}) or {}

    result = TwoPassResult(pass1=pass1)

    for field_name in fields:
        box = boxes.get(field_name)
        if not box:
            result.agreements[field_name] = {"agreement": None, "status": "no_box"}
            continue
        crop_bytes = crop_to_box(image_bytes, box)
        re_ext: ExtractionResult = extractor.extract(crop_bytes, filename=f"{field_name}_crop")
        re_value = getattr(re_ext, field_name, None)
        conf = getattr(re_ext.confidence, field_name, 0.0)
        result.pass2[field_name] = {"value": re_value, "confidence": round(conf, 3)}

        agreement, status = field_agreement(pass1.get(field_name), re_value)
        result.agreements[field_name] = {"agreement": agreement, "status": status}
        if agreement < AGREEMENT_THRESHOLD and normalize(pass1.get(field_name)) and normalize(re_value):
            result.disagreements.append(field_name)

    return result


def _fields_dict(ext: ExtractionResult) -> dict:
    return {
        "product_name": ext.product_name,
        "nrn": ext.nrn,
        "batch": ext.batch,
        "manufacture_date": ext.manufacture_date,
        "expiry_date": ext.expiry_date,
        "manufacturer": ext.manufacturer,
        "strength": ext.strength,
    }
