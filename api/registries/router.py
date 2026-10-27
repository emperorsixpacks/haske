"""Registry routing: pick the correct client for a product category."""

from __future__ import annotations

from .client import NoSourceClient, RegistryClient
from .models import LookupResult, RegistryCategory


class RegistryRouter:
    """Route a category to the client that can look it up."""

    def __init__(
        self,
        greenbook: RegistryClient,
        napams: RegistryClient,
        no_source: RegistryClient | None = None,
    ):
        self.greenbook = greenbook
        self.napams = napams
        self.no_source = no_source or NoSourceClient()

    def client_for(self, category: RegistryCategory) -> RegistryClient:
        if category in (
            RegistryCategory.FOOD,
            RegistryCategory.WATER,
            RegistryCategory.VETERINARY,
            RegistryCategory.GENERAL,
            RegistryCategory.COSMETIC,
            RegistryCategory.SOAP,
        ):
            return self.napams
        return self.greenbook

    def lookup(self, nrn: str, category: RegistryCategory) -> LookupResult:
        return self.client_for(category).lookup(nrn, category)
