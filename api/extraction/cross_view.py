"""Cross-view consistency check.

When a product is photographed from several sides (front, back, batch panel), the same field
may be read from more than one view. Code compares per-field values across views; any
disagreement is a CROSS_VIEW_MISMATCH signal, never a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .two_pass import normalize

COMPARED_FIELDS = ("product_name", "nrn", "manufacturer", "strength")


@dataclass
class CrossViewResult:
    mismatches: list[str] = field(default_factory=list)
    per_field: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"mismatches": self.mismatches, "per_field": self.per_field}


def cross_view_check(views: list[dict], fields: tuple[str, ...] = COMPARED_FIELDS) -> CrossViewResult:
    """Compare field values across views. views is a list of per-view field dicts."""
    result = CrossViewResult()
    for field_name in fields:
        values = [normalize(v.get(field_name)) for v in views if normalize(v.get(field_name))]
        unique = sorted(set(values))
        result.per_field[field_name] = {"views_with_value": len(values), "unique_values": unique}
        if len(unique) > 1:
            result.mismatches.append(field_name)
    return result
