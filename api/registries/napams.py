"""NAPAMS live portal lookup (food, water, veterinary, general, cosmetics, soaps).

Portal: https://registration.nafdac.gov.ng. There is no public API. The "Verify Products"
form on the home page (`#verify`) POSTs to /Home/VerifyProduct.

Verified against the live HTML and a real verify response (fetched 2026-10-27):
- Input: id="CertificateNumber" name="CertificateNumber" (the NAFDAC number).
- Submit: a button carrying class "g-recaptcha" with data-sitekey/data-callback, guarded by
  an invisible reCAPTCHA, plus a hidden __RequestVerificationToken and captchaToken.
- On success the response page contains labeled fields: "Product Name", "Product Category",
  "Product Source", "Manufacturer", "Date Approved", "Expiry Date", "NAFDAC No", and
  "Active Ingredient". The product name may repeat a trailing "(NN-NNNN)" many times.

The critical rule: network errors, captchas, layout changes and timeouts are CHECK_INCOMPLETE,
never NOT_FOUND. An invisible reCAPTCHA may auto-pass (form submits) or raise a challenge;
a challenge is CHECK_INCOMPLETE, not a "not found".
"""

from __future__ import annotations

import datetime as dt
import re

from ..app.config import Settings
from .client import RegistryClient
from .models import LookupResult, RegistryCategory, RegistryRecord
from .nrn import normalise_nrn

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
_SUCCESS_MARKERS = ["product found"]
_NOT_FOUND_MARKERS = ["not found", "no record", "no result", "nothing found"]

# NAPAMS product category labels (from "Product Category" in the verify response).
_CATEGORY_MAP: dict[str, RegistryCategory] = {
    "cosmetic": RegistryCategory.COSMETIC,
    "soap": RegistryCategory.SOAP,
    "food": RegistryCategory.FOOD,
    "water": RegistryCategory.WATER,
    "drug": RegistryCategory.DRUG,
    "medicine": RegistryCategory.DRUG,
    "veterinary": RegistryCategory.VETERINARY,
    "herbal": RegistryCategory.HERBAL,
    "vaccine": RegistryCategory.VACCINE,
    "device": RegistryCategory.DEVICE,
}


class NapamsClient(RegistryClient):
    name = "napams"

    def __init__(self, settings: Settings, timeout_ms: int = 15_000):
        self.settings = settings
        self.timeout_ms = timeout_ms

    def lookup(self, nrn: str, category: RegistryCategory | None = None) -> LookupResult:
        norm = normalise_nrn(nrn)
        if not norm.valid:
            return LookupResult.incomplete(
                f"invalid_nrn: {norm.error or 'unrecognised'}",
                nrn=nrn, source=self.name, source_url=self.settings.napams_base_url,
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return LookupResult.incomplete(
                "playwright_not_installed", nrn=norm.canonical, source=self.name,
                source_url=self.settings.napams_base_url,
            )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    page.goto(self.settings.napams_base_url.rstrip("/") + _VERIFY_URL, wait_until="domcontentloaded")

                    if not self._fill_and_submit(page, norm.canonical):
                        return LookupResult.incomplete(
                            "napams_form_layout_changed", nrn=norm.canonical,
                            source=self.name, source_url=self.settings.napams_base_url,
                        )

                    # On a real browser the invisible reCAPTCHA auto-passes and the form
                    # submits (navigating to /Home/VerifyProduct). From a headless/datacenter
                    # IP reCAPTCHA silently does nothing. Wait, bounded, then classify.
                    try:
                        page.wait_for_url("**/Home/VerifyProduct", timeout=8_000)
                        navigated = True
                    except Exception:  # noqa: BLE001
                        navigated = False

                    if navigated:
                        text = page.inner_text("body")
                        record = parse_verify_text(text)
                        if record is not None:
                            record.nrn = norm.canonical
                            return LookupResult.found(
                                [record], nrn=norm.canonical,
                                source=self.name, source_url=self.settings.napams_base_url,
                            )
                        lowered = text.lower()
                        if any(marker in lowered for marker in _NOT_FOUND_MARKERS):
                            return LookupResult.not_found(
                                nrn=norm.canonical, source=self.name,
                                source_url=self.settings.napams_base_url,
                            )
                        return LookupResult.incomplete(
                            "napams_result_unparseable", nrn=norm.canonical,
                            source=self.name, source_url=self.settings.napams_base_url,
                        )

                    if self._recaptcha_challenge_visible(page):
                        return LookupResult.incomplete(
                            "captcha_challenge", nrn=norm.canonical,
                            source=self.name, source_url=self.settings.napams_base_url,
                        )
                    return LookupResult.incomplete(
                        "recaptcha_blocked", nrn=norm.canonical,
                        source=self.name, source_url=self.settings.napams_base_url,
                    )
                finally:
                    browser.close()
        except Exception as exc:  # noqa: BLE001 - any failure is CHECK_INCOMPLETE
            return LookupResult.incomplete(
                f"napams_lookup_error: {type(exc).__name__}", nrn=norm.canonical,
                source=self.name, source_url=self.settings.napams_base_url,
            )

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

    def _recaptcha_challenge_visible(self, page) -> bool:
        # A visible challenge shows the image grid or the checkbox, not just the badge.
        for selector in [
            'iframe[src*="recaptcha/api2/bframe"]',
            'iframe[src*="recaptcha/api2/anchor"]',
            "#rc-imageselect",
            ".rc-imageselect",
        ]:
            locator = page.locator(selector)
            if locator.count() > 0:
                return True
        return False


def parse_verify_text(text: str) -> RegistryRecord | None:
    """Parse a NAPAMS verify response (rendered text) into a RegistryRecord.

    Returns None if the text does not look like a successful "Product found" page.
    """
    if not text:
        return None
    lowered = text.lower()
    if not any(marker in lowered for marker in _SUCCESS_MARKERS):
        return None

    def field(label: str) -> str | None:
        m = re.search(rf"{label}\s*[:：]\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    name = field("Product Name")
    nrn = field("NAFDAC No")
    category_raw = field("Product Category")
    if not name or not nrn:
        return None

    name = _clean_name(name, nrn)
    ingredients = field("Active Ingredient")
    return RegistryRecord(
        nrn=nrn,
        product_name=name,
        category=_map_category(category_raw),
        manufacturer=field("Manufacturer"),
        active_ingredients=_split_ingredients(ingredients),
        approval_date=field("Date Approved"),
        expiry_date=field("Expiry Date"),
        source="napams",
        source_url="https://registration.nafdac.gov.ng",
        retrieved_at=dt.datetime.now(dt.timezone.utc),
        raw={"product_source": field("Product Source")},
    )


def _clean_name(name: str, nrn: str) -> str:
    """Strip the repeated trailing "(NN-NNNN)" the NAPAMS page appends to the name."""
    token = f"({nrn})"
    cleaned = re.sub(rf"\s*{re.escape(token)}", " ", name)
    return " ".join(cleaned.split())


def _map_category(raw: str | None) -> RegistryCategory:
    if not raw:
        return RegistryCategory.GENERAL
    raw_l = raw.lower()
    for key, category in _CATEGORY_MAP.items():
        if key in raw_l:
            return category
    return RegistryCategory.GENERAL


def _split_ingredients(value: str | None) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in re.split(r"[,;|]", value) if p.strip()]
