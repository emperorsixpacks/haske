"""NAPAMS live portal lookup (food, water, veterinary, general products).

Portal: https://registration.nafdac.gov.ng. There is no public API. The "Verify Products"
form is a single form on the home page (anchor #verify) that POSTs to /Home/VerifyProduct.

Verified against the live HTML (fetched 2026-10-27):
- Input: id="CertificateNumber" name="CertificateNumber" (the NAFDAC number).
- Submit button: class "g-recaptcha btn btn-primary" with data-callback="onSubmit".
- The form carries a hidden __RequestVerificationToken (anti-forgery) and a hidden
  captchaToken filled by Google reCAPTCHA v3 (invisible, sitekey 6LcG85gs...).

Because the form is reCAPTCHA-v3 protected and requires a valid token plus an anti-forgery
token, automated submission is not reliably possible. Per the contract below, a captcha is
CHECK_INCOMPLETE, never NOT_FOUND.

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

# Verified against the live home page (see docstring).
_VERIFY_URL = "/"
_CERT_INPUT_SELECTORS = [
    'input[name="CertificateNumber"]',
    "#CertificateNumber",
]
_SUBMIT_SELECTORS = [
    '#verify-form button[type="submit"]',
    "button.g-recaptcha",
    "button:has-text('Verify')",
]
_NOT_FOUND_MARKERS = ["not found", "no record", "no result", "nothing found"]


class NapamsClient(RegistryClient):
    name = "napams"

    def __init__(self, settings: Settings, timeout_ms: int = 15_000):
        self.settings = settings
        self.timeout_ms = timeout_ms

    def lookup(self, nrn: str, category: RegistryCategory | None = None) -> LookupResult:
        if category in (RegistryCategory.COSMETIC, RegistryCategory.SOAP):
            return LookupResult.incomplete("no_registry_source", nrn=nrn, source=self.name, source_url=self.settings.napams_base_url)

        norm = normalise_nrn(nrn)
        if not norm.valid:
            return LookupResult.incomplete(f"invalid_nrn: {norm.error or 'unrecognised'}", nrn=nrn, source=self.name, source_url=self.settings.napams_base_url)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return LookupResult.incomplete("playwright_not_installed", nrn=norm.canonical, source=self.name, source_url=self.settings.napams_base_url)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    page.goto(self.settings.napams_base_url.rstrip("/") + _VERIFY_URL)

                    if self._has_captcha(page):
                        return LookupResult.incomplete("captcha_protected", nrn=norm.canonical, source=self.name, source_url=self.settings.napams_base_url)

                    if not self._fill_and_submit(page, norm.canonical):
                        return LookupResult.incomplete("napams_form_layout_changed", nrn=norm.canonical, source=self.name, source_url=self.settings.napams_base_url)

                    page.wait_for_load_state("networkidle")
                    content = page.content().lower()

                    if any(marker in content for marker in _NOT_FOUND_MARKERS):
                        return LookupResult.not_found(nrn=norm.canonical, source=self.name, source_url=self.settings.napams_base_url)

                    record = self._parse_record(page)
                    if record is None:
                        return LookupResult.incomplete("napams_result_unparseable", nrn=norm.canonical, source=self.name, source_url=self.settings.napams_base_url)
                    record.nrn = norm.canonical
                    return LookupResult.found([record], nrn=norm.canonical, source=self.name, source_url=self.settings.napams_base_url)
                finally:
                    browser.close()
        except Exception as exc:  # noqa: BLE001 - any failure is CHECK_INCOMPLETE
            return LookupResult.incomplete(f"napams_lookup_error: {type(exc).__name__}", nrn=norm.canonical, source=self.name, source_url=self.settings.napams_base_url)

    def _has_captcha(self, page) -> bool:
        """Detect the reCAPTCHA-v3 guard: a g-recaptcha button or a data-sitekey input."""
        if page.locator("button.g-recaptcha").count() > 0:
            return True
        if page.locator("[data-sitekey]").count() > 0:
            return True
        return "grecaptcha" in page.content().lower()

    def _fill_and_submit(self, page, nrn: str) -> bool:
        for selector in _CERT_INPUT_SELECTORS:
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
        # Result layout is UNKNOWN (the form is captcha-protected, so this path is not
        # reachable in practice). Best-effort generic scrape.
        try:
            title = page.locator("h1, h2, .product-name").first.inner_text(timeout=5_000)
        except Exception:  # noqa: BLE001
            return None
        title = title.strip()
        if not title:
            return None
        body = page.inner_text("body")
        return RegistryRecord(
            nrn="",
            product_name=title,
            category=RegistryCategory.GENERAL,
            source="napams",
            source_url=self.settings.napams_base_url,
            retrieved_at=dt.datetime.now(dt.timezone.utc),
            raw={"body_snippet": body[:2000]},
        )
