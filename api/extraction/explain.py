"""LLM explanation layer.

The verdict code is decided by deterministic code in api/verdict/engine.py. This module
asks the model to write a short plain-language explanation of that verdict for the user.
The model never picks the verdict; it only expands a code + evidence into readable prose.

Rules enforced in the prompt (mirrors messages.py):
- Say "indicators found" and "the register shows"; never write "fake" or "counterfeit".
- Never certify a product as genuine; the best positive is "consistent with the registry,
  which does not prove authenticity".
- No dosing or take/stop advice; if the product is a medicine, direct the user to a
  pharmacist.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

import httpx

from ..app.config import Settings

_SYSTEM_PROMPT = (
    "You are a product-safety assistant for Nigeria. "
    "A deterministic code has already decided the verdict for a NAFDAC check. "
    "Your only job is to write a clear, calm, one-to-two sentence explanation "
    "of that verdict in plain English for a non-expert user. "
    "Rules you must follow: "
    "(1) Never write 'fake' or 'counterfeit'; say 'indicators found' or 'the register shows'. "
    "(2) Never certify a product as genuine; the best positive result is 'consistent with the "
    "registry, which does not prove authenticity'. "
    "(3) Never give dosing, take, or stop advice. "
    "(4) If the product category is drug, vaccine, herbal, or device, end with: "
    "'If you have concerns, ask a pharmacist.' "
    "(5) Return only the explanation text, no JSON, no headers."
)


class Explainer(ABC):
    @abstractmethod
    def explain(
        self,
        verdict_code: str,
        product_name: str | None,
        nrn: str | None,
        category: str | None,
        evidence_note: str | None,
    ) -> str | None:
        """Return a plain-language explanation string, or None if unavailable."""
        raise NotImplementedError


class LLMExplainer(Explainer):
    """Calls the Meta Model API to generate a verdict explanation."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._transport = transport

    def explain(
        self,
        verdict_code: str,
        product_name: str | None,
        nrn: str | None,
        category: str | None,
        evidence_note: str | None,
    ) -> str | None:
        context_parts = [f"Verdict code: {verdict_code}"]
        if product_name:
            context_parts.append(f"Product: {product_name}")
        if nrn:
            context_parts.append(f"Registration number: {nrn}")
        if category:
            context_parts.append(f"Category: {category}")
        if evidence_note:
            context_parts.append(f"Evidence note: {evidence_note}")

        user_message = "\n".join(context_parts)

        payload = {
            "model": self.settings.meta_vision_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "max_tokens": 120,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.meta_api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=15, transport=self._transport) as client:
                resp = client.post(
                    self.settings.meta_api_base_url.rstrip("/") + "/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"]
                return text.strip() if text else None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None


class MockExplainer(Explainer):
    """Returns a static explanation. Used in MOCK mode and tests."""

    _MESSAGES: dict[str, str] = {
        "CONSISTENT_WITH_REGISTRY": (
            "The details on the label are consistent with the registry, "
            "which does not prove authenticity."
        ),
        "REGISTRY_MISMATCH": (
            "Indicators found: the registration number exists, but the register shows "
            "it belongs to a different product."
        ),
        "NOT_FOUND_IN_REGISTRY": (
            "The registration number was not found in the registry. "
            "It may be invalid or the product is not listed in the sources we can check."
        ),
        "EXPIRED_OR_INACTIVE": (
            "The register shows this registration is expired or inactive."
        ),
        "ALERT_MATCH": (
            "This product matches a cited official alert. See the evidence for details."
        ),
        "CANNOT_CONFIRM": (
            "There is not enough evidence to confirm whether this product matches the registry."
        ),
    }

    def explain(
        self,
        verdict_code: str,
        product_name: str | None,
        nrn: str | None,
        category: str | None,
        evidence_note: str | None,
    ) -> str | None:
        return self._MESSAGES.get(verdict_code)


def get_explainer(settings: Settings) -> Explainer:
    if settings.mock_mode:
        return MockExplainer()
    return LLMExplainer(settings)
