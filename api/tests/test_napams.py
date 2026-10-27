from api.app.config import Settings
from api.registries.fake import FakeNapamsClient, food_record
from api.registries.models import LookupOutcome, LookupResult, RegistryCategory
from api.registries.napams import NapamsClient, parse_verify_text
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


def test_fake_napams_cosmetics_route_to_napams():
    fake = FakeNapamsClient({"02-4139": LookupResult.found([food_record("02-4139", "Nivea Roll-on")])})
    result = fake.lookup("02-4139", RegistryCategory.COSMETIC)
    assert result.outcome == LookupOutcome.FOUND
    assert result.records[0].product_name == "Nivea Roll-on"


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
    assert router.client_for(RegistryCategory.COSMETIC) is fake
    assert router.client_for(RegistryCategory.SOAP) is fake


# Real NAPAMS verify response (text), supplied by the user.
NIVEA_RESPONSE = """Success, Product found, Nivea Dry Comfort Anti-perspirant Roll on (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139)
Product Name: Nivea Dry Comfort Anti-perspirant Roll on (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139) (02-4139)
Product Category: Cosmetics
Product Source: Nigerian Products
Manufacturer: BEIERSDORF NIVEA CONSUMER PRODUCT NIGERIA LIMITED
Date Approved: 2024-02-28
Expiry Date: 2029-02-27
NAFDAC No: 02-4139
Active Ingredient: AQUA, ALUMINUM CHLOROHYDRATE, PPG-15 STEARYL ETHER, STEARETH-2
"""


def test_parse_verify_text_extracts_fields():
    record = parse_verify_text(NIVEA_RESPONSE)
    assert record is not None
    assert record.nrn == "02-4139"
    assert record.product_name == "Nivea Dry Comfort Anti-perspirant Roll on"
    assert record.category == RegistryCategory.COSMETIC
    assert record.manufacturer == "BEIERSDORF NIVEA CONSUMER PRODUCT NIGERIA LIMITED"
    assert record.approval_date == "2024-02-28"
    assert record.expiry_date == "2029-02-27"
    assert record.active_ingredients == [
        "AQUA",
        "ALUMINUM CHLOROHYDRATE",
        "PPG-15 STEARYL ETHER",
        "STEARETH-2",
    ]
    assert record.raw["product_source"] == "Nigerian Products"


def test_parse_verify_text_rejects_non_success():
    assert parse_verify_text("Product not found") is None
    assert parse_verify_text("") is None


def test_recaptcha_challenge_detection():
    client = NapamsClient(Settings())

    class Loc:
        def __init__(self, count):
            self._count = count

        def count(self):
            return self._count

    class Page:
        def locator(self, selector):
            if selector in ('iframe[src*="recaptcha/api2/bframe"]', "#rc-imageselect"):
                return Loc(1)
            return Loc(0)

    assert client._recaptcha_challenge_visible(Page())
