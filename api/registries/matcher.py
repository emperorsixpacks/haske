"""Fuzzy matching of extracted label fields against registry records.

Outcomes:
- MATCH: the NRN exists and the label agrees with the record.
- MISMATCH: the NRN exists but belongs to a clearly different product.
- AMBIGUOUS: the NRN is shared by several distinct products and we cannot pick one.
- UNVERIFIABLE: the NRN exists but there is not enough label information to compare.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from enum import Enum

from .models import RegistryRecord


class MatchOutcome(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    AMBIGUOUS = "AMBIGUOUS"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass
class FieldComparison:
    field: str
    label_value: str | None
    registry_value: str | None
    similarity: float


@dataclass
class MatchResult:
    outcome: MatchOutcome
    comparisons: list[FieldComparison] = field(default_factory=list)
    matched_record: RegistryRecord | None = None
    detail: str | None = None


def _norm(s: str | None) -> str:
    if s is None:
        return ""
    return " ".join(s.strip().lower().split())


def _similarity(a: str | None, b: str | None) -> float:
    an, bn = _norm(a), _norm(b)
    if not an and not bn:
        return 1.0
    if not an or not bn:
        return 0.0
    return difflib.SequenceMatcher(None, an, bn).ratio()


# Fields compared in priority order. A low similarity on an early, high-weight field
# (product name) is stronger evidence of mismatch than on a low-weight field.
_COMPARED_FIELDS = [
    ("product_name", 1.0),
    ("manufacturer", 0.8),
    ("strength", 0.7),
]


def _best_record(records: list[RegistryRecord], label: dict) -> tuple[RegistryRecord, float]:
    """Return the record that best matches the label and its aggregate score.

    Fields the registry record does not carry (e.g. manufacturer is absent from the
    Greenbook search feed) are skipped rather than scored as a mismatch.
    """
    best: RegistryRecord | None = None
    best_score = -1.0
    for record in records:
        total = 0.0
        weight_sum = 0.0
        for field, weight in _COMPARED_FIELDS:
            registry_value = getattr(record, field, None)
            if not _norm(registry_value):
                continue
            total += weight * _similarity(label.get(field), registry_value)
            weight_sum += weight
        score = total / weight_sum if weight_sum else 0.0
        if score > best_score:
            best, best_score = record, score
    return best, best_score


def _distinct_products(records: list[RegistryRecord]) -> bool:
    names = {_norm(r.product_name) for r in records if _norm(r.product_name)}
    return len(names) > 1


def match(label: dict, records: list[RegistryRecord]) -> MatchResult:
    """Match a label dict against the records returned for an NRN."""
    if not records:
        return MatchResult(outcome=MatchOutcome.UNVERIFIABLE, detail="no records to compare")

    if _distinct_products(records):
        return MatchResult(outcome=MatchOutcome.AMBIGUOUS, detail="nrn shared by multiple products")

    record, score = _best_record(records, label)
    comparisons = [
        FieldComparison(
            field=field,
            label_value=label.get(field),
            registry_value=getattr(record, field, None),
            similarity=_similarity(label.get(field), getattr(record, field, None)),
        )
        for field, _ in _COMPARED_FIELDS
    ]

    # Nothing meaningful to compare: only an NRN with no label fields.
    if not any(_norm(c.label_value) for c in comparisons):
        return MatchResult(
            outcome=MatchOutcome.UNVERIFIABLE,
            comparisons=comparisons,
            matched_record=record,
            detail="no comparable label fields",
        )

    # High-confidence mismatch: the product name is present and clearly different.
    name_cmp = comparisons[0]
    if _norm(name_cmp.label_value) and name_cmp.similarity < 0.35:
        return MatchResult(
            outcome=MatchOutcome.MISMATCH,
            comparisons=comparisons,
            matched_record=record,
            detail="product name does not match the record",
        )

    if score >= 0.5:
        return MatchResult(
            outcome=MatchOutcome.MATCH,
            comparisons=comparisons,
            matched_record=record,
            detail="label agrees with the registry record",
        )

    return MatchResult(
        outcome=MatchOutcome.UNVERIFIABLE,
        comparisons=comparisons,
        matched_record=record,
        detail="label fields do not clearly agree or disagree",
    )
