"""Deterministic verdict engine. No LLM involvement in deciding the verdict code."""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ..registries.matcher import MatchOutcome, MatchResult
from ..registries.models import LookupOutcome, LookupResult, RegistryCategory

if TYPE_CHECKING:
    from ..registries.alerts import AlertFinding


class VerdictCode(str, Enum):
    CONSISTENT_WITH_REGISTRY = "CONSISTENT_WITH_REGISTRY"
    REGISTRY_MISMATCH = "REGISTRY_MISMATCH"
    NOT_FOUND_IN_REGISTRY = "NOT_FOUND_IN_REGISTRY"
    EXPIRED_OR_INACTIVE = "EXPIRED_OR_INACTIVE"
    ALERT_MATCH = "ALERT_MATCH"
    KNOWN_TARGET = "KNOWN_TARGET"
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
    alert_finding: "AlertFinding | None" = None,
) -> Verdict:
    """Decide a verdict deterministically from lookup + match outcomes.

    consistency_flags: output of api/extraction/consistency.check_consistency()
    batch_conflict_note: output of api/observations/store.ConflictResult.to_note()
    alert_finding: output of api/registries/alerts.AlertRegistry.lookup().
    Signals never change the verdict code. Alert findings are the only inputs that
    produce ALERT_MATCH or KNOWN_TARGET, and they come from code, never a model.
    """
    consistency_flags = consistency_flags or []
    signals = _build_signals_note(consistency_flags, batch_conflict_note)

    # An official alert matching NRN + batch is the strongest signal and takes
    # priority over the registry, because a falsified NRN may not be registered at all.
    if alert_finding is not None and alert_finding.kind == "ALERT_MATCH":
        return _alert_match_verdict(alert_finding, category, signals)

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

    # The label matches the registry. If the NRN is the target of a known alert but
    # this batch is not one of the flagged counterfeit batches, warn rather than pass.
    if alert_finding is not None and alert_finding.kind == "KNOWN_TARGET":
        return _known_target_verdict(alert_finding, category, signals)

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


def _alert_evidence(finding: "AlertFinding", kind: str) -> Evidence:
    alert = finding.alert
    parts = [f"alert_no={alert.alert_no}"]
    if alert.date:
        parts.append(f"date={alert.date}")
    if finding.matched:
        parts.append(f"batch={finding.matched.batch}")
    if alert.quoted_text:
        parts.append(f"quote={alert.quoted_text}")
    note = "; ".join(parts)
    return Evidence(
        source=f"NAFDAC Public Alert ({kind})",
        source_url=alert.source_url,
        fields_compared=[],
        note=note,
    )


def _alert_match_verdict(finding: "AlertFinding", category: RegistryCategory, signals: str | None) -> Verdict:
    alert = finding.alert
    message = (
        f"NAFDAC Public Alert No. {alert.alert_no} matches this product"
        + (f" (batch {finding.matched.batch})" if finding.matched else "")
        + ". "
        + (alert.quoted_text or "See the linked alert for details.")
    )
    if finding.fuzzy:
        message += " The batch match was fuzzy, so please confirm the batch code carefully."
    return Verdict(
        code=VerdictCode.ALERT_MATCH,
        title="Matches an official alert",
        message=message,
        footer=_footer_for(category),
        evidence=[_alert_evidence(finding, "ALERT_MATCH")],
        abstained=False,
    )


def _known_target_verdict(finding: "AlertFinding", category: RegistryCategory, signals: str | None) -> Verdict:
    alert = finding.alert
    return Verdict(
        code=VerdictCode.KNOWN_TARGET,
        title="Known target of a NAFDAC alert",
        message=(
            "This product has been counterfeited before. "
            "Your batch is not in the alert. Take the extra steps below."
        ),
        footer=_footer_for(category),
        evidence=[_alert_evidence(finding, "KNOWN_TARGET")],
        abstained=False,
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
