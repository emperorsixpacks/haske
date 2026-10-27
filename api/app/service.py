"""Orchestration: extraction -> NRN -> lookup -> match -> verdict."""

from __future__ import annotations

import datetime as dt

from ..extraction.schemas import ExtractionResult
from ..extraction.vision import Extractor
from ..registries.matcher import match
from ..registries.models import LookupResult, RegistryCategory
from ..registries.nrn import normalise_nrn
from ..registries.router import RegistryRouter
from ..registries.store import Store
from ..verdict.engine import decide
from .config import Settings
from .schemas import CheckResponse, NrnInfo

_GUESS_TO_CATEGORY = {
    "drug": RegistryCategory.DRUG,
    "medicine": RegistryCategory.DRUG,
    "pharmaceutical": RegistryCategory.DRUG,
    "vaccine": RegistryCategory.VACCINE,
    "device": RegistryCategory.DEVICE,
    "veterinary": RegistryCategory.VETERINARY,
    "vet": RegistryCategory.VETERINARY,
    "herbal": RegistryCategory.HERBAL,
    "food": RegistryCategory.FOOD,
    "water": RegistryCategory.WATER,
    "general": RegistryCategory.GENERAL,
    "cosmetic": RegistryCategory.COSMETIC,
    "soap": RegistryCategory.SOAP,
}


def category_from_guess(guess: str | None) -> RegistryCategory:
    return _GUESS_TO_CATEGORY.get((guess or "").strip().lower(), RegistryCategory.UNKNOWN)


class CheckService:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        extractor: Extractor,
        router: RegistryRouter,
    ):
        self.settings = settings
        self.store = store
        self.extractor = extractor
        self.router = router

    def check_image(self, image_bytes: bytes, filename: str | None = None) -> CheckResponse:
        extraction = self.extractor.extract(image_bytes, filename)
        return self._evaluate(extraction)

    def check_fields(self, fields: dict) -> CheckResponse:
        extraction = ExtractionResult(
            product_name=fields.get("product_name"),
            nrn=fields.get("nrn"),
            batch=fields.get("batch"),
            manufacture_date=fields.get("manufacture_date"),
            expiry_date=fields.get("expiry_date"),
            manufacturer=fields.get("manufacturer"),
            strength=fields.get("strength"),
            category_guess=fields.get("category_guess"),
        )
        return self._evaluate(extraction)

    def _evaluate(self, extraction: ExtractionResult) -> CheckResponse:
        category = category_from_guess(extraction.category_guess)
        nrn = normalise_nrn(extraction.nrn)
        retrieved_at = self._snapshot_time()

        if not nrn.valid:
            lookup = LookupResult.incomplete(
                nrn.error or "invalid_nrn",
                nrn=nrn.canonical,
                source=self.router.client_for(category).name,
            )
        else:
            lookup = self.router.lookup(nrn.canonical, category)

        match_result = match(extraction.as_label_dict(), lookup.records)
        verdict = decide(lookup, match_result, category, retrieved_at)

        return CheckResponse(
            extraction=extraction,
            nrn=NrnInfo(
                raw=nrn.raw,
                canonical=nrn.canonical,
                is_barcode=nrn.is_barcode,
                ambiguous_o_zero=nrn.ambiguous_o_zero,
                error=nrn.error,
                valid=nrn.valid,
            ),
            match_outcome=match_result.outcome.value,
            verdict=verdict,
        )

    def _snapshot_time(self) -> dt.datetime | None:
        snap = self.store.latest_snapshot()
        if snap:
            return dt.datetime.fromisoformat(snap["fetched_at"])
        return None
