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


class AlertReference(BaseModel):
    kind: str  # "ALERT_MATCH" | "KNOWN_TARGET"
    alert_no: str
    date: str | None = None
    product: str
    nrn: str | None = None
    source_url: str | None = None
    known_differences: list[str] = []
    quoted_text: str | None = None
    matched_batch: str | None = None
    fuzzy: bool = False


class CheckResponse(BaseModel):
    extraction: ExtractionResult
    nrn: NrnInfo
    match_outcome: str
    verdict: Verdict
    alert: AlertReference | None = None


class TraceEventModel(BaseModel):
    round: int
    tool: str
    effort: str
    latency_ms: int
    tokens: int
    status: str
    summary: str


class InvestigateResponse(BaseModel):
    outcome: str
    report: dict | None = None
    question: dict | None = None
    trace: list[TraceEventModel] = []
    trace_summary: str
    rounds: int
    fallback_verdict: str | None = None
    fallback_alert: AlertReference | None = None


class RegistryStatus(BaseModel):
    source: str
    snapshot_date: str | None
    record_count: int
