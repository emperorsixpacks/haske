import datetime as dt

import pytest

from api.app.config import Settings
from api.app.service import CheckService, category_from_guess
from api.extraction.mock import MockExtractor
from api.registries.fake import FakeNapamsClient
from api.registries.greenbook import GreenbookClient
from api.registries.models import LookupResult, RegistryCategory
from api.registries.router import RegistryRouter
from api.registries.store import Store
from api.verdict.engine import VerdictCode


@pytest.fixture
def service(tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(settings.db_path)
    router = RegistryRouter(greenbook=GreenbookClient(store), napams=FakeNapamsClient({}))
    return CheckService(settings, store, MockExtractor(settings), router)


def _seed(store, records):
    sid = store.add_snapshot("greenbook", dt.datetime.now(dt.timezone.utc), len(records), "h", "p")
    store.add_records(sid, records)


def test_category_from_guess():
    assert category_from_guess("drug") == RegistryCategory.DRUG
    assert category_from_guess("Food") == RegistryCategory.FOOD
    assert category_from_guess(None) == RegistryCategory.UNKNOWN


def test_check_fields_consistent(tmp_path, service):
    from api.registries.models import RegistryRecord

    rec = RegistryRecord(
        nrn="A4-0123",
        product_name="Paracetamol Tablets 500mg",
        manufacturer="Acme Pharma Ltd",
        strength="500mg",
        status="Active",
        source="greenbook",
        source_url="https://greenbook.nafdac.gov.ng",
    )
    _seed(service.store, [rec])
    resp = service.check_fields(
        {"product_name": "Paracetamol Tablets 500mg", "manufacturer": "Acme Pharma Ltd", "strength": "500mg", "nrn": "A4-0123", "category_guess": "drug"}
    )
    assert resp.verdict.code == VerdictCode.CONSISTENT_WITH_REGISTRY
    assert resp.nrn.canonical == "A4-0123"


def test_check_fields_mismatch(tmp_path, service):
    from api.registries.models import RegistryRecord

    rec = RegistryRecord(
        nrn="A4-0123",
        product_name="Paracetamol Tablets 500mg",
        manufacturer="Acme Pharma Ltd",
        status="Active",
        source="greenbook",
    )
    _seed(service.store, [rec])
    resp = service.check_fields(
        {"product_name": "Ibuprofen", "manufacturer": "Acme", "nrn": "A4-0123", "category_guess": "drug"}
    )
    assert resp.verdict.code == VerdictCode.REGISTRY_MISMATCH


def test_check_fields_not_found(service):
    resp = service.check_fields({"product_name": "X", "nrn": "A4-5555", "category_guess": "drug"})
    assert resp.verdict.code == VerdictCode.NOT_FOUND_IN_REGISTRY


def test_check_fields_barcode_abstains(service):
    resp = service.check_fields({"nrn": "6157000001234", "category_guess": "drug"})
    assert resp.verdict.code == VerdictCode.CANNOT_CONFIRM
    assert resp.nrn.is_barcode


def test_check_image_uses_mock(service, tmp_path):
    _seed_demo_like(service)
    resp = service.check_image(b"fake", "default")
    assert resp.extraction.nrn == "A4-0123"
    assert resp.verdict.code == VerdictCode.CONSISTENT_WITH_REGISTRY


def _seed_demo_like(service):
    from api.registries.models import RegistryRecord

    rec = RegistryRecord(
        nrn="A4-0123",
        product_name="Paracetamol Tablets 500mg",
        manufacturer="Acme Pharma Ltd",
        strength="500mg",
        status="Active",
        source="greenbook",
        source_url="https://greenbook.nafdac.gov.ng",
    )
    _seed(service.store, [rec])
