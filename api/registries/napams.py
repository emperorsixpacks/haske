"""NAPAMS live portal lookup (food, water, veterinary, general products).

Portal: https://registration.nafdac.gov.ng. There is no API; the public "verify a product"
forms are scraped with Playwright. The DOM, selectors, and flow are UNKNOWN and must be
re-tuned against the live portal (see NOTES.md). The contract that must hold regardless:

- Every lookup returns exactly one of FOUND / SEARCHED_NOT_FOUND / CHECK_INCOMPLETE.
- Network errors, captchas, layout changes, and timeouts are CHECK_INCOMPLETE, never
  NOT_FOUND. NOT_FOUND is reserved for a completed search that found nothing.
- Cosmetics and soaps have no confirmed path: CHECK_INCOMPLETE("no_registry_source").
"""

from __future__ import annotations

import datetime as dt

from ..app.config import Settings
from .client import RegistryClient
from .models import LookupResult, RegistryCategory, RegistryRecord
from .nrn import normalise_nrn

# Placeholder selectors; re-tune against the live portal. Each is tried in order.
_VERIFY_URL = "/verify"
_NRN_INPUT_SELECTORS = [
    'input[name="nrn"]',
    'input[name="registration_number"]',
    'input[id*="reg"]',
]
_SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
]
_NOT_FOUND_MARKERS = ["not found", "no record", "no result", "nothing found", "invalid"]


class NapamsClient(RegistryClient):
    name = "napams"

    def __init__(self, settings: Settings, timeout_ms: int = 15_000):
        self.settings = settings
        self.timeout_ms = timeout_ms

    def lookup(self, nrn: str, category: RegistryCategory | None = None) -> LookupResult:
        if category in (RegistryCategory.COSMETIC, RegistryCategory.SOAP):
            return LookupResult.incomplete("no_registry_source")

        norm = normalise_nrn(nrn)
        if not norm.valid:
            return LookupResult.incomplete(f"invalid_nrn: {norm.error or 'unrecognised'}")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return LookupResult.incomplete("playwright_not_installed")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    page.goto(self.settings.napams_base_url.rstrip("/") + _VERIFY_URL)

                    if not self._fill_and_submit(page, norm.canonical):
                        return LookupResult.incomplete("napams_form_layout_changed")

                    page.wait_for_load_state("networkidle")
                    content = page.content().lower()

                    if any(marker in content for marker in _NOT_FOUND_MARKERS):
                        return LookupResult.not_found()

                    record = self._parse_record(page)
                    if record is None:
                        return LookupResult.incomplete("napams_result_unparseable")
                    return LookupResult.found([record])
                finally:
                    browser.close()
        except Exception as exc:  # noqa: BLE001 - any failure is CHECK_INCOMPLETE
            return LookupResult.incomplete(f"napams_lookup_error: {type(exc).__name__}")

    def _fill_and_submit(self, page, nrn: str) -> bool:
        for selector in _NRN_INPUT_SELECTORS:
            locator = page.locator(selector)
            if locator.count() > 0:
                locator.first.fill(nrn)
                for submit in _SUBMIT_SELECTORS:
                    btn = page.locator(submit)
                    if btn.count() > 0:
                        btn.first.click()
                        return True
        return False

    def _parse_record(self, page) -> RegistryRecord | None:
        # Unknown result layout; attempt a generic table/definition scrape.
        try:
            title = page.locator("h1, h2, .product-name").first.inner_text(timeout=5_000)
        except Exception:  # noqa: BLE001
            return None
        title = title.strip()
        if not title:
            return None
        body = page.inner_text("body")
        return RegistryRecord(
            nrn="",  # filled below is impossible; leave raw
            product_name=title,
            category=RegistryCategory.GENERAL,
            source="napams",
            source_url=self.settings.napams_base_url,
            retrieved_at=dt.datetime.now(dt.timezone.utc),
            raw={"body_snippet": body[:2000]},
        )
