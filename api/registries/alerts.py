"""NAFDAC public-alert registry (Evidence-First).

Alerts are curated from nafdac.gov.ng public-alert pages into alert_seed.json. Every entry
carries its source_url and date; never invent an entry. If a field is not stated in the
source, leave it empty.

Matching is deterministic code only. Normalization uppercases and strips spaces and
hyphens, and O/0 plus I/1 are treated as confusable. A batch matches a counterfeit example
exactly or within Levenshtein edit distance 1 (flagged as a fuzzy, OCR-confidence match).

Outcomes:
- ALERT_MATCH: the NRN matches an alert AND the batch matches a counterfeit example.
- KNOWN_TARGET: the NRN matches an alert but the batch is not one of the listed counterfeit
  batches. The product has been counterfeited before; we never claim this batch is genuine.
- None: the NRN is not in any alert, or the batch matches a genuine example (the alert does
  not apply to the genuine reference).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_SEED_PATH = Path(__file__).resolve().parent / "alert_seed.json"


@dataclass(frozen=True)
class BatchExample:
    batch: str
    mfg: str | None = None
    exp: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class AlertRecord:
    id: str
    alert_no: str
    date: str | None
    product: str
    nrn: str | None
    genuine_examples: tuple[BatchExample, ...] = ()
    counterfeit_examples: tuple[BatchExample, ...] = ()
    known_differences: tuple[str, ...] = ()
    quoted_text: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class AlertFinding:
    kind: str  # "ALERT_MATCH" | "KNOWN_TARGET"
    alert: AlertRecord
    matched: BatchExample | None = None
    fuzzy: bool = False


def normalize(value: str | None) -> str:
    """Uppercase and strip everything non-alphanumeric (spaces, hyphens, underscores)."""
    if not value:
        return ""
    return "".join(ch for ch in value.upper() if ch.isalnum())


def confusable(value: str) -> str:
    """Map O->0 and I->1 so visually ambiguous characters compare equal."""
    return value.replace("O", "0").replace("I", "1")


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance between two strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


class AlertRegistry:
    def __init__(self, records: list[AlertRecord] | None = None):
        self._records: list[AlertRecord] = records or []

    def add(self, record: AlertRecord) -> None:
        self._records.append(record)

    def __len__(self) -> int:
        return len(self._records)

    def lookup(self, nrn: str | None, batch: str | None = None) -> AlertFinding | None:
        if not nrn:
            return None
        nrn_norm = normalize(nrn)
        nrn_conf = confusable(nrn_norm)
        batch_norm = normalize(batch)
        batch_conf = confusable(batch_norm)

        for alert in self._records:
            finding = _match_alert(alert, nrn_norm, nrn_conf, batch_norm, batch_conf)
            if finding is not None:
                return finding
        return None

    def verify_alert(self, alert_id: str, nrn: str | None, batch: str | None) -> AlertFinding | None:
        """Verify a model-proposed candidate alert id against the label's NRN and batch.

        Returns the finding only if the alert's NRN and (counterfeit) batch rules actually
        match. Unverified proposals return None and are discarded by the caller.
        """
        alert = next((a for a in self._records if a.id == alert_id), None)
        if alert is None:
            return None
        return _match_alert(alert, normalize(nrn), confusable(normalize(nrn)), normalize(batch), confusable(normalize(batch)))


def _match_alert(alert: AlertRecord, nrn_norm: str, nrn_conf: str, batch_norm: str, batch_conf: str) -> AlertFinding | None:
    """Match one alert against normalized NRN and batch. None means not a counterfeit match."""
    if not alert.nrn:
        return None
    alert_norm = normalize(alert.nrn)
    if alert_norm != nrn_norm and confusable(alert_norm) != nrn_conf:
        return None

    if not batch_norm:
        return AlertFinding(kind="KNOWN_TARGET", alert=alert)

    for ex in alert.counterfeit_examples:
        ex_norm = normalize(ex.batch)
        if ex_norm == batch_norm:
            return AlertFinding(kind="ALERT_MATCH", alert=alert, matched=ex, fuzzy=False)
        if confusable(ex_norm) == batch_conf:
            return AlertFinding(kind="ALERT_MATCH", alert=alert, matched=ex, fuzzy=True)
        if edit_distance(confusable(ex_norm), batch_conf) <= 1:
            return AlertFinding(kind="ALERT_MATCH", alert=alert, matched=ex, fuzzy=True)

    for ex in alert.genuine_examples:
        ex_norm = normalize(ex.batch)
        if ex_norm == batch_norm or confusable(ex_norm) == batch_conf:
            return None

    return AlertFinding(kind="KNOWN_TARGET", alert=alert)


def alert_corpus_text(registry: "AlertRegistry") -> str:
    """Compact text of all stored alerts for the model's long-context system prompt.

    The model may propose candidate alert ids from this corpus; code verifies with exact
    and fuzzy NRN and batch rules before anything is shown.
    """
    lines = ["NAFDAC public alerts. Propose a candidate alert_id only from this list:"]
    for a in registry._records:
        genuine = ", ".join(e.batch for e in a.genuine_examples) or "none listed"
        counterfeit = ", ".join(((e.label + " ") if e.label else "") + e.batch for e in a.counterfeit_examples) or "none listed"
        diffs = " | ".join(a.known_differences)
        lines.append(
            f"- id={a.id} alert_no={a.alert_no} product={a.product} nrn={a.nrn} "
            f"genuine_batches={genuine} counterfeit_batches={counterfeit} differences={diffs}"
        )
    return "\n".join(lines)


def _load_seed() -> list[AlertRecord]:
    records: list[AlertRecord] = []
    if not _SEED_PATH.exists():
        return records
    data = json.loads(_SEED_PATH.read_text())
    for item in data.get("alerts", []):
        records.append(
            AlertRecord(
                id=item["id"],
                alert_no=item["alert_no"],
                date=item.get("date"),
                product=item["product"],
                nrn=item.get("nrn"),
                genuine_examples=tuple(
                    BatchExample(**ex) for ex in item.get("genuine_examples", [])
                ),
                counterfeit_examples=tuple(
                    BatchExample(**ex) for ex in item.get("counterfeit_examples", [])
                ),
                known_differences=tuple(item.get("known_differences", [])),
                quoted_text=item.get("quoted_text"),
                source_url=item.get("source_url"),
            )
        )
    return records


_registry: AlertRegistry | None = None


def get_alert_registry() -> AlertRegistry:
    """Return the shared alert registry, lazily loaded from the curated seed."""
    global _registry
    if _registry is None:
        _registry = AlertRegistry(_load_seed())
    return _registry
