"""Fixture-backed registry clients for tests and MOCK demos."""

from __future__ import annotations

from .client import RegistryClient
from .models import LookupResult, RegistryCategory, RegistryRecord


class FakeNapamsClient(RegistryClient):
    """Deterministic NAPAMS stand-in keyed by NRN."""

    name = "napams_fake"

    def __init__(self, results: dict[str, LookupResult] | None = None):
        self.results = results or {}

    def lookup(self, nrn: str, category: RegistryCategory | None = None) -> LookupResult:
        if category in (RegistryCategory.COSMETIC, RegistryCategory.SOAP):
            return LookupResult.incomplete("no_registry_source")
        return self.results.get(nrn, LookupResult.not_found())


def food_record(nrn: str, name: str, manufacturer: str | None = None) -> RegistryRecord:
    return RegistryRecord(
        nrn=nrn,
        product_name=name,
        category=RegistryCategory.FOOD,
        manufacturer=manufacturer,
        source="napams",
        source_url="https://registration.nafdac.gov.ng",
    )
