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


class ExtractionResult(BaseModel):
    product_name: str | None = None
    nrn: str | None = None
    batch: str | None = None
    manufacture_date: str | None = None
    expiry_date: str | None = None
    manufacturer: str | None = None
    strength: str | None = None
    category_guess: str | None = None
    confidence: FieldConfidence = Field(default_factory=FieldConfidence)
    legibility_notes: list[str] = Field(default_factory=list)

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
  "confidence": {
    "product_name": 0.0, "nrn": 0.0, "batch": 0.0, "manufacture_date": 0.0,
    "expiry_date": 0.0, "manufacturer": 0.0, "strength": 0.0, "category_guess": 0.0
  },
  "legibility_notes": ["string"]
}
"""
