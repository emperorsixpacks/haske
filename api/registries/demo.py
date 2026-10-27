"""Seed a small demo snapshot so MOCK mode works end to end against the real store path."""

from __future__ import annotations

import datetime as dt

from .models import RegistryCategory, RegistryRecord
from .store import Store

_DEMO_RECORDS = [
    RegistryRecord(
        nrn="A4-0123",
        product_name="Paracetamol Tablets 500mg",
        category=RegistryCategory.DRUG,
        status="Active",
        applicant="Acme Pharma Ltd",
        manufacturer="Acme Pharma Ltd",
        active_ingredients=["Paracetamol"],
        strength="500mg",
        form="Tablet",
        approval_date="2020-01-01",
        expiry_date="2027-01-01",
        source="greenbook",
        source_url="https://greenbook.nafdac.gov.ng",
    ),
    RegistryRecord(
        nrn="A4-9999",
        product_name="Cough Syrup",
        category=RegistryCategory.DRUG,
        status="Active",
        manufacturer="Other Labs",
        strength="100mg/5ml",
        form="Syrup",
        source="greenbook",
        source_url="https://greenbook.nafdac.gov.ng",
    ),
    RegistryRecord(
        nrn="B1-2000",
        product_name="Amoxicillin Capsules 250mg",
        category=RegistryCategory.DRUG,
        status="Expired",
        manufacturer="Beta Labs",
        strength="250mg",
        form="Capsule",
        source="greenbook",
        source_url="https://greenbook.nafdac.gov.ng",
    ),
]


def seed_demo(store: Store) -> None:
    if store.record_count() > 0:
        return
    snapshot_id = store.add_snapshot(
        source="greenbook",
        fetched_at=dt.datetime.now(dt.timezone.utc),
        record_count=len(_DEMO_RECORDS),
        content_hash="demo-seed",
        file_path="demo://seed",
        forced=False,
    )
    store.add_records(snapshot_id, _DEMO_RECORDS)
