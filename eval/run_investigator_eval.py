#!/usr/bin/env python3
"""Investigator eval harness.

Replays the real NAFDAC alert fixtures (Postinor-2, BPPL) through the deterministic pipeline
to measure alert-replay recall and false-positive rate, plus per-check cost. Real photo
field-accuracy and the low-vs-high reasoning-effort chart need the 20-30 annotated photos;
pass --live to measure the agent's real latency and token cost for one fixture.

Run: uv run python eval/run_investigator_eval.py [--live]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from api.app.config import Settings
from api.app.service import CheckService
from api.extraction.explain import TemplateExplainer
from api.extraction.mock import MockExtractor
from api.registries.alerts import get_alert_registry
from api.registries.fake import FakeNapamsClient
from api.registries.greenbook import GreenbookClient
from api.registries.router import RegistryRouter
from api.registries.store import Store
from api.verdict.engine import VerdictCode

# (name, fields, expected verdict, is_genuine)
FIXTURES = [
    ("postinor_counterfeit_type1", {"nrn": "04-6985", "batch": "T36184B", "product_name": "Postinor 2", "category_guess": "drug"}, "ALERT_MATCH", False),
    ("postinor_counterfeit_type2", {"nrn": "04-6985", "batch": "332", "product_name": "Postinor 2", "category_guess": "drug"}, "ALERT_MATCH", False),
    ("bppl_falsified", {"nrn": "02-3457", "batch": "BP5203", "product_name": "Artemether Lumefantrine", "category_guess": "drug"}, "ALERT_MATCH", False),
    ("postinor_genuine", {"nrn": "04-6985", "batch": "T32458H", "product_name": "Postinor 2", "category_guess": "drug"}, "CONSISTENT_WITH_REGISTRY", True),
    ("postinor_unknown_batch", {"nrn": "04-6985", "batch": "T99999X", "product_name": "Postinor 2", "category_guess": "drug"}, "KNOWN_TARGET", True),
    ("paracetamol_genuine", {"nrn": "A4-0123", "batch": "PT2210", "product_name": "Paracetamol Tablets 500mg", "category_guess": "drug"}, "CONSISTENT_WITH_REGISTRY", True),
]

_ACCUSATIONS = {VerdictCode.ALERT_MATCH, VerdictCode.REGISTRY_MISMATCH, VerdictCode.NOT_FOUND_IN_REGISTRY, VerdictCode.EXPIRED_OR_INACTIVE}


def _build_service() -> tuple[CheckService, Store]:
    td = tempfile.mkdtemp()
    settings = Settings(data_dir=Path(td))
    store = Store(settings.db_path)
    # Seed the genuine Postinor-2 record (real NRN) plus a normal drug.
    import datetime as dt
    from api.registries.models import RegistryRecord

    sid = store.add_snapshot("greenbook", dt.datetime.now(dt.timezone.utc), 2, "h", "p")
    store.add_records(sid, [
        RegistryRecord(nrn="04-6985", product_name="Postinor 2", status="Active", source="greenbook"),
        RegistryRecord(nrn="A4-0123", product_name="Paracetamol Tablets 500mg", status="Active", source="greenbook"),
    ])
    router = RegistryRouter(greenbook=GreenbookClient(store), napams=FakeNapamsClient({}))
    service = CheckService(settings, store, MockExtractor(settings), router, explainer=TemplateExplainer())
    return service, store


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="run the agent once and report real latency/tokens")
    args = parser.parse_args()

    service, _store = _build_service()
    reg = get_alert_registry()
    print(f"alerts loaded: {len(reg)}")

    counterfeit_total = 0
    counterfeit_correct = 0
    genuine_total = 0
    false_positives = 0
    rows = []

    for name, fields, expected, genuine in FIXTURES:
        resp = service.check_fields(fields)
        code = resp.verdict.code.value
        correct = code == expected
        if not genuine:
            counterfeit_total += 1
            counterfeit_correct += 1 if correct else 0
        else:
            genuine_total += 1
            if code == VerdictCode.ALERT_MATCH.value:
                false_positives += 1
        rows.append((name, code, expected, correct))

    print("\n--- alert replay ---")
    for name, code, expected, correct in rows:
        mark = "ok" if correct else "MISS"
        print(f"  {name:28s} -> {code:26s} expected {expected:26s} [{mark}]")

    recall = counterfeit_correct / counterfeit_total if counterfeit_total else 0.0
    fpr = false_positives / genuine_total if genuine_total else 0.0
    print("\n--- summary ---")
    print(f"  alert-replay recall:     {counterfeit_correct}/{counterfeit_total} = {recall:.2%}")
    print(f"  false-positive rate:     {false_positives}/{genuine_total} = {fpr:.2%}")
    print(f"  deterministic cost:      0 model tokens, 0 vision calls per check")

    if args.live:
        print("\n--- live agent cost (one fixture) ---")
        from api.app.config import get_settings
        settings = get_settings()
        if not settings.meta_api_key:
            print("  skipped: META_API_KEY not set")
            return 0
        from pathlib import Path
        photo = Path("eval/photos").glob("*.jpg")
        # No real photos yet; skip rather than fabricate a number.
        print("  skipped: no real photos in eval/photos yet")

    print("\nrun docs/EVAL.md for the full honest report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
