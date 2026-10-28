#!/usr/bin/env python3
"""Eval harness for Haske.

Reads eval/labels.csv and eval/photos/<image>.json fixtures (predicted extractions) and
reports field exact-match for NRN, batch and expiry, verdict agreement, false-accusation
rate and abstention rate.

Real photos will replace the .json fixtures later; the harness reads fixtures so it runs
without the vision model and without real registry data (it seeds a demo registry).
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

from api.app.config import Settings
from api.app.service import CheckService
from api.registries.demo import seed_demo
from api.registries.fake import BlockedNapamsClient
from api.registries.greenbook import GreenbookClient
from api.registries.nrn import normalise_nrn
from api.registries.router import RegistryRouter
from api.registries.store import Store
from api.verdict.engine import VerdictCode

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "eval" / "labels.csv"
PHOTOS = ROOT / "eval" / "photos"

_GENUINE = {VerdictCode.CONSISTENT_WITH_REGISTRY}
_ACCUSATIONS = {
    VerdictCode.REGISTRY_MISMATCH,
    VerdictCode.NOT_FOUND_IN_REGISTRY,
    VerdictCode.EXPIRED_OR_INACTIVE,
    VerdictCode.ALERT_MATCH,
}


def _build_service() -> tuple[CheckService, Store]:
    with tempfile.TemporaryDirectory() as td:
        settings = Settings(data_dir=Path(td))
        store = Store(settings.db_path)
        seed_demo(store)
        router = RegistryRouter(greenbook=GreenbookClient(store), napams=BlockedNapamsClient())
        # MockExtractor is unused here: the harness evaluates check_fields against fixtures.
        from api.extraction.mock import MockExtractor

        return CheckService(settings, store, MockExtractor(settings), router), store


def main() -> int:
    if not LABELS.exists():
        print(f"missing {LABELS}", file=sys.stderr)
        return 1

    service, store = _build_service()
    rows = list(csv.DictReader(LABELS.open()))

    n_total = len(rows)
    n_nrn_ok = n_batch_ok = n_expiry_ok = 0
    n_verdict_ok = 0
    n_false_accusation = 0
    n_abstain = 0
    n_genuine = 0
    failures = []

    for row in rows:
        image = row["image"]
        fixture_path = PHOTOS / f"{image}.json"
        if not fixture_path.exists():
            failures.append(f"{image}: missing fixture {fixture_path.name}")
            continue
        predicted = json.loads(fixture_path.read_text())

        true_nrn = normalise_nrn(row["true_nrn"]).canonical
        pred_nrn = normalise_nrn(predicted.get("nrn")).canonical
        if true_nrn is not None and pred_nrn == true_nrn:
            n_nrn_ok += 1
        if (predicted.get("batch") or "").strip() == (row["true_batch"] or "").strip():
            n_batch_ok += 1
        if (predicted.get("expiry_date") or "").strip() == (row["true_expiry"] or "").strip():
            n_expiry_ok += 1

        resp = service.check_fields(predicted)
        code = resp.verdict.code
        expected = VerdictCode(row["expected_verdict"])

        if code == expected:
            n_verdict_ok += 1
        if code == VerdictCode.CANNOT_CONFIRM:
            n_abstain += 1
        if expected in _GENUINE:
            n_genuine += 1
            if code in _ACCUSATIONS:
                n_false_accusation += 1
        print(f"{image}: expected={expected.value} got={code.value}")

    store.close()
    print("\n===== Haske eval report =====")
    print(f"rows: {n_total}")
    print(f"NRN exact-match:    {n_nrn_ok}/{n_total} ({_pct(n_nrn_ok, n_total)})")
    print(f"batch exact-match:  {n_batch_ok}/{n_total} ({_pct(n_batch_ok, n_total)})")
    print(f"expiry exact-match: {n_expiry_ok}/{n_total} ({_pct(n_expiry_ok, n_total)})")
    print(f"verdict agreement:  {n_verdict_ok}/{n_total} ({_pct(n_verdict_ok, n_total)})")
    print(f"false-accusation:   {n_false_accusation}/{max(n_genuine, 1)} ({_pct(n_false_accusation, max(n_genuine, 1))})")
    print(f"abstention:         {n_abstain}/{n_total} ({_pct(n_abstain, n_total)})")
    if failures:
        print("\nfailures:")
        for f in failures:
            print(f"  - {f}")
        return 1
    return 0


def _pct(num: int, den: int) -> str:
    return f"{100.0 * num / den:.1f}%" if den else "n/a"


if __name__ == "__main__":
    raise SystemExit(main())
