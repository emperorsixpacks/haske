from api.app.config import Settings
from api.registries.fake import FakeNapamsClient, food_record
from api.registries.models import LookupOutcome, LookupResult, RegistryCategory
from api.registries.napams import NapamsClient
from api.registries.router import RegistryRouter


def test_fake_napams_found():
    fake = FakeNapamsClient({"01-2345": LookupResult.found([food_record("01-2345", "Golden Rice")])})
    result = fake.lookup("01-2345", RegistryCategory.FOOD)
    assert result.outcome == LookupOutcome.FOUND
    assert result.records[0].product_name == "Golden Rice"


def test_fake_napams_not_found_is_explicit():
    fake = FakeNapamsClient({})
    result = fake.lookup("01-2345", RegistryCategory.FOOD)
    assert result.outcome == LookupOutcome.SEARCHED_NOT_FOUND


def test_napams_cosmetic_returns_check_incomplete():
    fake = FakeNapamsClient({"A4-0123": LookupResult.found([food_record("A4-0123", "X")])})
    result = fake.lookup("A4-0123", RegistryCategory.COSMETIC)
    assert result.outcome == LookupOutcome.CHECK_INCOMPLETE
    assert result.reason == "no_registry_source"


def test_napams_invalid_nrn_is_incomplete_not_not_found():
    client = NapamsClient(Settings())
    result = client.lookup("!!garbage!!", RegistryCategory.FOOD)
    assert result.outcome == LookupOutcome.CHECK_INCOMPLETE
    assert result.reason.startswith("invalid_nrn")


def test_router_routes_categories():
    fake = FakeNapamsClient({})
    router = RegistryRouter(greenbook=fake, napams=fake)
    assert router.client_for(RegistryCategory.DRUG) is fake
    assert router.client_for(RegistryCategory.FOOD) is fake
    assert router.client_for(RegistryCategory.COSMETIC).name == "no_source"
    assert router.lookup("A4-0123", RegistryCategory.SOAP).reason == "no_registry_source"
