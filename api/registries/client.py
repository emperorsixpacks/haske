"""RegistryClient interface.

Every registry source implements the same interface: given a normalised NRN, return a
LookupResult that is exactly one of FOUND / SEARCHED_NOT_FOUND / CHECK_INCOMPLETE. The
critical rule: network errors, captchas, layout changes and timeouts are CHECK_INCOMPLETE,
never NOT_FOUND. NOT_FOUND is reserved for a completed search that genuinely found nothing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import LookupResult, RegistryCategory


class RegistryClient(ABC):
    """A source of registry records for a product NRN."""

    name: str = "registry"

    @abstractmethod
    def lookup(self, nrn: str, category: RegistryCategory | None = None) -> LookupResult:
        raise NotImplementedError


class NoSourceClient(RegistryClient):
    """A category with no confirmed lookup path yet (cosmetics, soaps)."""

    name = "no_source"

    def lookup(self, nrn: str, category: RegistryCategory | None = None) -> LookupResult:
        return LookupResult.incomplete("no_registry_source")
