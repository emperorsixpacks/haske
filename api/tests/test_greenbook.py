import datetime as dt
import json

import httpx
import pytest

from api.app.config import Settings
from api.registries.greenbook import GreenbookError, GreenbookSnapshotter
from api.registries.models import RegistryCategory
from api.registries.store import Store

# A representative DataTables-shaped response (UNVERIFIED against the live site).
def _datatables_payload(rows, total=None):
    total = total if total is not None else len(rows)
    return {"draw": 1, "recordsTotal": total, "recordsFiltered": total, "data": rows}


def _row(reg_no="A4-0123", name="Paracetamol 500mg", **extra):
    base = {
        "NAFDAC": reg_no,
        "product_name": name,
        "category_name": "Drugs",
        "status": "Active",
        "applicant_name": "Acme Pharma Ltd",
        "manufacturer_name": "Acme Pharma",
        "ingredient_name": "Paracetamol",
        "strength": "500mg",
        "form_name": "Tablet",
        "approval_date": "2020-01-01",
        "expiry_date": "2025-01-01",
        "applicant_email": "secret@example.com",
        "phone": "+2348000000000",
        "address": "1 Hidden Road",
    }
    base.update(extra)
    return base


def _snapper(rows, total=None, settings=None, tmp_path=None):
    settings = settings or Settings(data_dir=tmp_path or "/tmp/haske_test")
    store = Store(settings.db_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(200, text="User-agent: *\nDisallow:\n")
        return httpx.Response(200, json=_datatables_payload(rows, total))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GreenbookSnapshotter(settings, store, transport=httpx.MockTransport(handler)), store


def test_probe_prints_shape(tmp_path):
    snapper, store = _snapper([_row(), _row("A4-9999", "Cough Syrup"), _row()], total=9000, tmp_path=tmp_path)
    info = snapper.probe()
    store.close()
    assert info["row_count"] == 3
    assert info["recordsTotal"] == 9000
    assert "NAFDAC" in info["first_row"]


def test_probe_fails_loudly_on_bad_shape(tmp_path):
    snapper, store = _snapper([], tmp_path=tmp_path)
    with pytest.raises(GreenbookError):
        snapper.probe()
    store.close()


def test_normalise_strips_contact_fields(tmp_path):
    snapper, store = _snapper([_row()], tmp_path=tmp_path)
    rec = snapper.normalise(_row())
    store.close()
    assert rec is not None
    assert rec.category == RegistryCategory.DRUG
    for key in rec.raw:
        assert "email" not in key.lower()
        assert "phone" not in key.lower()
        assert "address" not in key.lower()


def test_normalise_strips_decorative_chars_from_name(tmp_path):
    snapper, store = _snapper([], tmp_path=tmp_path)
    rec = snapper.normalise(_row(name="Paracetamol##"))
    store.close()
    assert rec is not None
    assert rec.product_name == "Paracetamol"


def test_normalise_maps_verified_fields(tmp_path):
    snapper, store = _snapper([], tmp_path=tmp_path)
    rec = snapper.normalise(_row())
    store.close()
    assert rec is not None
    assert rec.nrn == "A4-0123"
    assert rec.applicant == "Acme Pharma Ltd"
    assert rec.active_ingredients == ["Paracetamol"]
    assert rec.form == "Tablet"
    assert rec.expiry_date == "2025-01-01"


def test_normalise_drops_rows_without_nrn_or_name(tmp_path):
    snapper, store = _snapper([], tmp_path=tmp_path)
    assert snapper.normalise({"Product Name": "No NRN here"}) is None
    assert snapper.normalise({"Registration No": "A4-0001"}) is None
    store.close()


def test_fetch_saves_snapshot_with_hash(tmp_path):
    rows = [_row(), _row("A4-9999", "Cough Syrup")]
    snapper, store = _snapper(rows, total=2, tmp_path=tmp_path)
    result = snapper.fetch()
    latest = store.latest_snapshot()
    store.close()
    assert result["rows"] == 2
    assert result["normalised"] == 2
    assert len(result["content_hash"]) == 64
    assert latest["record_count"] == 2


def test_fetch_refuses_suspiciously_small(tmp_path):
    settings = Settings(data_dir=tmp_path)
    # Seed a previous snapshot of 100 rows.
    snapper, store = _snapper([_row()], total=1, settings=settings)
    store.add_snapshot("greenbook", dt.datetime.now(dt.timezone.utc), 100, "x" * 64, "/tmp/prev.json")
    # Now fetch a tiny snapshot (1 row) which is well under 80% of 100.
    with pytest.raises(GreenbookError):
        snapper.fetch()
    store.close()


def test_fetch_forced_bypasses_small_check(tmp_path):
    settings = Settings(data_dir=tmp_path)
    snapper, store = _snapper([_row()], total=1, settings=settings)
    store.add_snapshot("greenbook", dt.datetime.now(dt.timezone.utc), 100, "x" * 64, "/tmp/prev.json")
    result = snapper.fetch(force=True)
    store.close()
    assert result["rows"] == 1
