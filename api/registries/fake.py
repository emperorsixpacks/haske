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
        return self.results.get(nrn, LookupResult.not_found(nrn=nrn, source=self.name))


class BlockedNapamsClient(RegistryClient):
    """Mimics the live NAPAMS portal being reCAPTCHA-blocked for automated lookups."""

    name = "napams_blocked"

    def lookup(self, nrn: str, category: RegistryCategory | None = None) -> LookupResult:
        return LookupResult.incomplete("recaptcha_blocked", nrn=nrn, source=self.name)


def food_record(nrn: str, name: str, manufacturer: str | None = None) -> RegistryRecord:
    return RegistryRecord(
        nrn=nrn,
        product_name=name,
        category=RegistryCategory.FOOD,
        manufacturer=manufacturer,
        source="napams",
        source_url="https://registration.nafdac.gov.ng",
    )
