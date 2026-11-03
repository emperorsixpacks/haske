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
    explanation: str | None = None  # LLM-generated plain-language expansion (optional)
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
    consistency_flags: list[str] | None = None,
    batch_conflict_note: str | None = None,
) -> Verdict:
    """Decide a verdict deterministically from lookup + match outcomes.

    consistency_flags: output of api/extraction/consistency.check_consistency()
    batch_conflict_note: output of api/observations/store.ConflictResult.to_note()
    Both are evidence signals only. They never change the verdict code.
    """
    consistency_flags = consistency_flags or []
    signals = _build_signals_note(consistency_flags, batch_conflict_note)

    if lookup.outcome == LookupOutcome.CHECK_INCOMPLETE:
        return Verdict(
            code=VerdictCode.CANNOT_CONFIRM,
            title="Cannot confirm",
            message="There is not enough evidence to confirm this product. The register could not be checked: "
            + (lookup.reason or "source unavailable"),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at, signals),
            abstained=True,
        )

    if lookup.outcome == LookupOutcome.SEARCHED_NOT_FOUND:
        return Verdict(
            code=VerdictCode.NOT_FOUND_IN_REGISTRY,
            title="Not found in the registry",
            message="The registration number was not found in the registry. It may be invalid or the product is not listed in the sources we can check.",
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at, signals),
        )

    # FOUND
    if match.outcome == MatchOutcome.MISMATCH:
        return Verdict(
            code=VerdictCode.REGISTRY_MISMATCH,
            title="Registry mismatch",
            message="Indicators found: the registration number exists, but the register shows it belongs to a different product.",
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at, signals),
        )

    if match.outcome == MatchOutcome.AMBIGUOUS:
        return Verdict(
            code=VerdictCode.CANNOT_CONFIRM,
            title="Cannot confirm",
            message="The registration number is shared by more than one product, so we cannot confirm which one the label refers to.",
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at, signals),
            abstained=True,
        )

    if match.outcome == MatchOutcome.UNVERIFIABLE:
        return Verdict(
            code=VerdictCode.CANNOT_CONFIRM,
            title="Cannot confirm",
            message="The number exists but there is not enough label information to confirm the product.",
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at, signals),
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
            evidence=_lookup_evidence(lookup, match, category, retrieved_at, signals),
        )

    # Milestone 2: check public alerts before declaring consistent.
    # The alert registry is empty in milestone 1, so this is always a no-op.
    from ..registries.alerts import get_alert_registry
    alert = get_alert_registry().lookup(lookup.nrn or "", None)
    if alert is not None:
        return Verdict(
            code=VerdictCode.ALERT_MATCH,
            title="Matches an official alert",
            message=(
                "This product matches a cited official NAFDAC alert. "
                "The register shows indicators found: see the evidence for the source."
            ),
            footer=_footer_for(category),
            evidence=_lookup_evidence(lookup, match, category, retrieved_at, signals),
        )

    return Verdict(
        code=VerdictCode.CONSISTENT_WITH_REGISTRY,
        title="Consistent with the registry",
        message="The label is consistent with the registry, which does not prove authenticity.",
        footer=_footer_for(category),
        evidence=_lookup_evidence(lookup, match, category, retrieved_at, signals),
    )


def _build_signals_note(
    consistency_flags: list[str],
    batch_conflict_note: str | None,
) -> str | None:
    """Combine consistency flags and batch conflict into a single evidence note string."""
    parts: list[str] = []
    if consistency_flags:
        parts.append("signals=" + ",".join(consistency_flags))
    if batch_conflict_note:
        parts.append(batch_conflict_note)
    return "; ".join(parts) if parts else None


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
    signals_note: str | None = None,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    if lookup.records:
        for record in lookup.records:
            base_note = f"nrn={record.nrn} product={record.product_name}"
            note = f"{base_note}; {signals_note}" if signals_note else base_note
            evidence.append(
                Evidence(
                    source=record.source or lookup.source or "registry",
                    source_url=record.source_url or lookup.source_url,
                    retrieved_at=record.retrieved_at or retrieved_at,
                    fields_compared=[_cmp_to_dict(c) for c in match.comparisons],
                    note=note,
                )
            )
        return evidence

    # No records: describe the search itself so the verdict still carries evidence.
    base_note = lookup.reason if lookup.outcome == LookupOutcome.CHECK_INCOMPLETE else "searched, no matching record"
    full_note = f"nrn={lookup.nrn} {base_note}"
    if signals_note:
        full_note = f"{full_note}; {signals_note}"
    evidence.append(
        Evidence(
            source=lookup.source or "registry",
            source_url=lookup.source_url,
            retrieved_at=retrieved_at,
            fields_compared=[_cmp_to_dict(c) for c in match.comparisons],
            note=full_note,
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
