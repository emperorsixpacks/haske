"""Extraction schemas: the strict output shape the vision model must fill."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FieldConfidence(BaseModel):
    product_name: float = 0.0
    nrn: float = 0.0
    batch: float = 0.0
    manufacture_date: float = 0.0
    expiry_date: float = 0.0
    manufacturer: float = 0.0
    strength: float = 0.0
    category_guess: float = 0.0


# Prefix tokens used in layout_flags entries from the vision model.
# Keep in sync with the prompt schema in vision.py.
LAYOUT_FLAG_PREFIXES = (
    "SPELLING_ERROR:",
    "DATE_IN_FUTURE:",
    "SHELF_LIFE_INCONSISTENT",
    "BATCH_FORMAT_UNUSUAL:",
    "FONT_INCONSISTENCY:",
    "RESTICKERED_AREA:",
    "MISSING_SECURITY_ELEMENT:",
    "LOGO_QUALITY_LOW",
    "TEXT_ALIGNMENT_OFF:",
)


class ExtractionResult(BaseModel):
    product_name: str | None = None
    nrn: str | None = None
    batch: str | None = None
    manufacture_date: str | None = None
    expiry_date: str | None = None
    manufacturer: str | None = None
    strength: str | None = None
    category_guess: str | None = None
    # Stated shelf life in months, if printed on the label.
    shelf_life_months: int | None = None
    confidence: FieldConfidence = Field(default_factory=FieldConfidence)
    legibility_notes: list[str] = Field(default_factory=list)
    # Layout anomaly flags reported by the vision model (see LAYOUT_FLAG_PREFIXES).
    layout_flags: list[str] = Field(default_factory=list)
    # Normalized bounding boxes (0..1) for each localized field, e.g.
    # {"nrn": [x0, y0, x1, y1], "batch": [...]}. Empty when the model cannot localize.
    boxes: dict[str, list[float]] = Field(default_factory=dict)

    def as_label_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "manufacturer": self.manufacturer,
            "strength": self.strength,
        }


# The JSON schema requested from the model. Kept as a string so the prompt and the
# Pydantic model cannot drift silently.
EXTRACTION_SCHEMA = """
{
  "product_name": "string or null",
  "nrn": "string or null (the NAFDAC registration number)",
  "batch": "string or null",
  "manufacture_date": "string or null (YYYY-MM-DD)",
  "expiry_date": "string or null (YYYY-MM-DD)",
  "manufacturer": "string or null",
  "strength": "string or null",
  "category_guess": "string or null (drug, vaccine, device, veterinary, herbal, food, water, cosmetic, soap)",
  "shelf_life_months": "integer or null (the stated shelf life in months, if printed)",
  "confidence": {
    "product_name": 0.0, "nrn": 0.0, "batch": 0.0, "manufacture_date": 0.0,
    "expiry_date": 0.0, "manufacturer": 0.0, "strength": 0.0, "category_guess": 0.0
  },
  "legibility_notes": ["string"],
  "layout_flags": [
    "SPELLING_ERROR:<word>",
    "DATE_IN_FUTURE:<field>",
    "SHELF_LIFE_INCONSISTENT",
    "BATCH_FORMAT_UNUSUAL:<reason>",
    "FONT_INCONSISTENCY:<location>",
    "RESTICKERED_AREA:<location>",
    "MISSING_SECURITY_ELEMENT:<element>",
    "LOGO_QUALITY_LOW",
    "TEXT_ALIGNMENT_OFF:<location>"
  ],
  "boxes": {
    "product_name": [x0, y0, x1, y1],
    "nrn": [x0, y0, x1, y1],
    "batch": [x0, y0, x1, y1],
    "manufacture_date": [x0, y0, x1, y1],
    "expiry_date": [x0, y0, x1, y1]
  }
}
"""
