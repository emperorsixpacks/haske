"""Deterministic verdict engine. No LLM involvement in deciding the verdict code."""

from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, Field

from ..registries.matcher import MatchOutcome, MatchResult
from ..registries.models import LookupOutcome, LookupResult, RegistryCategory


class VerdictCode(str, Enum):
    CONSISTENT_WITH_REGISTRY = "CONSISTENT_WITH_REGISTRY"
    REGISTRY_MISMATCH = "REGISTRY_MISMATCH"
    NOT_FOUND_IN_REGISTRY = "NOT_FOUND_IN_REGISTRY"
    EXPIRED_OR_INACTIVE = "EXPIRED_OR_INACTIVE"
    ALERT_MATCH = "ALERT_MATCH"  # reserved for milestone 2
    CANNOT_CONFIRM = "CANNOT_CONFIRM"


# Statuses that make a found registration expired/inactive.
_INACTIVE_STATUSES = {"expired", "cancelled", "revoked", "suspended", "inactive", "withdrawn"}


class Evidence(BaseModel):
    source: str
    source_url: str | None = None
    retrieved_at: dt.datetime | None = None
    fields_compared: list[dict] = Field(default_factory=list)
    note: str | None = None


class Verdict(BaseModel):
    code: VerdictCode
    title: str
    message: str
    footer: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    abstained: bool = False


def _expired_or_inactive(record) -> bool:
    status = (record.status or "").lower()
    if any(s in status for s in _INACTIVE_STATUSES):
        return True
    expiry = record.expiry_date
    if expiry:
        try:
            date = dt.date.fromisoformat(expiry[:10])
            if date < dt.date.today():
                return True
        except ValueError:
            pass
    return False


def decide(
    lookup: LookupResult,
    match: MatchResult,
    category: RegistryCategory,
    retrieved_at: dt.datetime | None = None,
) -> Verdict:
    """Decide a verdict deterministically from lookup + match outcomes."""
    if lookup.outcome == LookupOutcome.CHECK_INCOMPLETE:
        return Verdict(
            code=VerdictCode.CANNOT_CONFIRM,
            title="Cannot confirm",
            message="There is not enough evidence to confirm this product. The register could not be checked: "
            + (lookup.reason or "source unavailable"),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at),
            abstained=True,
        )

    if lookup.outcome == LookupOutcome.SEARCHED_NOT_FOUND:
        return Verdict(
            code=VerdictCode.NOT_FOUND_IN_REGISTRY,
            title="Not found in the registry",
            message="The registration number was not found in the registry. It may be invalid or the product is not listed in the sources we can check.",
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at),
        )

    # FOUND
    if match.outcome == MatchOutcome.MISMATCH:
        return Verdict(
            code=VerdictCode.REGISTRY_MISMATCH,
            title="Registry mismatch",
            message="Indicators found: the registration number exists, but the register shows it belongs to a different product.",
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at),
        )

    if match.outcome == MatchOutcome.AMBIGUOUS:
        return Verdict(
            code=VerdictCode.CANNOT_CONFIRM,
            title="Cannot confirm",
            message="The registration number is shared by more than one product, so we cannot confirm which one the label refers to.",
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at),
            abstained=True,
        )

    if match.outcome == MatchOutcome.UNVERIFIABLE:
        return Verdict(
            code=VerdictCode.CANNOT_CONFIRM,
            title="Cannot confirm",
            message="The number exists but there is not enough label information to confirm the product.",
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at),
            abstained=True,
        )

    # MATCH
    record = match.matched_record or (lookup.records[0] if lookup.records else None)
    if record is not None and _expired_or_inactive(record):
        return Verdict(
            code=VerdictCode.EXPIRED_OR_INACTIVE,
            title="Registration expired or inactive",
            message="The register shows this registration is expired or inactive.",
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at),
        )

    return Verdict(
        code=VerdictCode.CONSISTENT_WITH_REGISTRY,
        title="Consistent with the registry",
        message="The label is consistent with the registry, which does not prove authenticity.",
        footer=_footer_for(category),
        evidence=_lookup_evidence(lookup, match, category, retrieved_at),
    )


def _footer_for(category: RegistryCategory) -> str | None:
    from .messages import MEDICINES_FOOTER

    if category in (
        RegistryCategory.DRUG,
        RegistryCategory.VACCINE,
        RegistryCategory.HERBAL,
        RegistryCategory.DEVICE,
        RegistryCategory.VETERINARY,
    ):
        return MEDICINES_FOOTER
    return None


def _lookup_evidence(
    lookup: LookupResult,
    match: MatchResult,
    category: RegistryCategory,
    retrieved_at: dt.datetime | None,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    if lookup.records:
        for record in lookup.records:
            evidence.append(
                Evidence(
                    source=record.source or lookup.source or "registry",
                    source_url=record.source_url or lookup.source_url,
                    retrieved_at=record.retrieved_at or retrieved_at,
                    fields_compared=[_cmp_to_dict(c) for c in match.comparisons],
                    note=f"nrn={record.nrn} product={record.product_name}",
                )
            )
        return evidence

    # No records: describe the search itself so the verdict still carries evidence.
    note = lookup.reason if lookup.outcome == LookupOutcome.CHECK_INCOMPLETE else "searched, no matching record"
    evidence.append(
        Evidence(
            source=lookup.source or "registry",
            source_url=lookup.source_url,
            retrieved_at=retrieved_at,
            fields_compared=[_cmp_to_dict(c) for c in match.comparisons],
            note=f"nrn={lookup.nrn} {note}",
        )
    )
    return evidence


def _cmp_to_dict(cmp) -> dict:
    return {
        "field": cmp.field,
        "label_value": cmp.label_value,
        "registry_value": cmp.registry_value,
        "similarity": round(cmp.similarity, 3),
    }
