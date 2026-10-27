"""API request and response models."""

from __future__ import annotations

from pydantic import BaseModel

from ..extraction.schemas import ExtractionResult
from ..verdict.engine import Verdict


class CheckFieldsRequest(BaseModel):
    product_name: str | None = None
    nrn: str | None = None
    batch: str | None = None
    manufacture_date: str | None = None
    expiry_date: str | None = None
    manufacturer: str | None = None
    strength: str | None = None
    category_guess: str | None = None


class NrnInfo(BaseModel):
    raw: str | None = None
    canonical: str | None = None
    is_barcode: bool = False
    ambiguous_o_zero: bool = False
    error: str | None = None
    valid: bool = False


class CheckResponse(BaseModel):
    extraction: ExtractionResult
    nrn: NrnInfo
    match_outcome: str
    verdict: Verdict


class RegistryStatus(BaseModel):
    source: str
    snapshot_date: str | None
    record_count: int
