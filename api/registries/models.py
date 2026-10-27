"""Shared registry data models: records, lookup outcomes, and categories."""

from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, Field


class RegistryCategory(str, Enum):
    DRUG = "drug"
    VACCINE = "vaccine"
    DEVICE = "device"
    VETERINARY = "veterinary"
    HERBAL = "herbal"
    FOOD = "food"
    WATER = "water"
    GENERAL = "general"
    COSMETIC = "cosmetic"
    SOAP = "soap"
    UNKNOWN = "unknown"


# Categories served by the Greenbook snapshot.
GREENBOOK_CATEGORIES = {
    RegistryCategory.DRUG,
    RegistryCategory.VACCINE,
    RegistryCategory.DEVICE,
    RegistryCategory.VETERINARY,
    RegistryCategory.HERBAL,
}

# Categories served by the NAPAMS live portal lookup.
NAPAMS_CATEGORIES = {
    RegistryCategory.FOOD,
    RegistryCategory.WATER,
    RegistryCategory.VETERINARY,
    RegistryCategory.GENERAL,
}

# Categories with no confirmed lookup path yet.
NO_SOURCE_CATEGORIES = {RegistryCategory.COSMETIC, RegistryCategory.SOAP}


class RegistryRecord(BaseModel):
    """A normalised registry product record."""

    nrn: str
    product_name: str
    category: RegistryCategory = RegistryCategory.UNKNOWN
    status: str | None = None
    applicant: str | None = None
    manufacturer: str | None = None
    active_ingredients: list[str] = Field(default_factory=list)
    strength: str | None = None
    form: str | None = None
    approval_date: str | None = None
    expiry_date: str | None = None
    source: str = "greenbook"
    source_url: str | None = None
    retrieved_at: dt.datetime | None = None
    raw: dict = Field(default_factory=dict)


class LookupOutcome(str, Enum):
    FOUND = "FOUND"
    SEARCHED_NOT_FOUND = "SEARCHED_NOT_FOUND"
    CHECK_INCOMPLETE = "CHECK_INCOMPLETE"


class LookupResult(BaseModel):
    outcome: LookupOutcome
    records: list[RegistryRecord] = Field(default_factory=list)
    reason: str | None = None
    nrn: str | None = None
    source: str | None = None
    source_url: str | None = None

    @property
    def found(self) -> bool:
        return self.outcome == LookupOutcome.FOUND

    @classmethod
    def found(cls, records: list[RegistryRecord], nrn: str | None = None, source: str | None = None, source_url: str | None = None) -> "LookupResult":
        return cls(outcome=LookupOutcome.FOUND, records=records, nrn=nrn, source=source, source_url=source_url)

    @classmethod
    def not_found(cls, nrn: str | None = None, source: str | None = None, source_url: str | None = None) -> "LookupResult":
        return cls(outcome=LookupOutcome.SEARCHED_NOT_FOUND, nrn=nrn, source=source, source_url=source_url)

    @classmethod
    def incomplete(cls, reason: str, nrn: str | None = None, source: str | None = None, source_url: str | None = None) -> "LookupResult":
        return cls(outcome=LookupOutcome.CHECK_INCOMPLETE, reason=reason, nrn=nrn, source=source, source_url=source_url)
