"""Finish-report validation and sanitization.

The model drafts the finish report. Code validates it: any URL, NRN, batch, or alert number
that the tools did not actually return is stripped. This closes the "invented fact" hole.
"""

from __future__ import annotations

import re

from .tools import AllowedFacts

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_ALERT_NO_RE = re.compile(r"\b\d{3}/\d{4}\b")
# NRN-like: letter(s) + digits + dash + digits, e.g. A4-0123 or 02-3457.
_NRN_RE = re.compile(r"\b[A-Z]{0,3}\d{1,2}-\d{3,6}\b")
# Words the model must never put in a finish report: neither accuse nor certify.
_BANNED_WORDS_RE = re.compile(
    r"\b(fake|counterfeit|counterfeited|counterfeiting|genuine|authentic|certified|guaranteed)\b",
    re.IGNORECASE,
)


def _redact_text(text: str, allowed: AllowedFacts) -> tuple[str, list[str]]:
    violations: list[str] = []

    def url_repl(m):
        if m.group(0).rstrip(".") not in allowed.urls:
            violations.append(f"url:{m.group(0)}")
            return "[removed]"
        return m.group(0)

    text = _URL_RE.sub(url_repl, text)

    def nrn_repl(m):
        norm = m.group(0).upper()
        if norm not in {n.upper() for n in allowed.nrns}:
            violations.append(f"nrn:{m.group(0)}")
            return "[removed]"
        return m.group(0)

    text = _NRN_RE.sub(nrn_repl, text)

    def alert_repl(m):
        if m.group(0) not in allowed.alert_nos:
            violations.append(f"alert_no:{m.group(0)}")
            return "[removed]"
        return m.group(0)

    text = _ALERT_NO_RE.sub(alert_repl, text)

    # Language guard: the report must neither accuse (fake/counterfeit) nor certify
    # (genuine/authentic/certified). Strip these and record them as violations.
    def word_repl(m):
        violations.append(f"word:{m.group(0).lower()}")
        return "[removed]"

    text = _BANNED_WORDS_RE.sub(word_repl, text)

    return text, violations


def validate_report(report: dict | None, allowed: AllowedFacts) -> tuple[dict, list[str]]:
    """Return a sanitized report plus any violations that were stripped."""
    if not isinstance(report, dict):
        return {}, ["report_not_object"]
    violations: list[str] = []
    cleaned: dict = {}

    for key, value in report.items():
        if isinstance(value, str):
            new_value, v = _redact_text(value, allowed)
            violations.extend(v)
            cleaned[key] = new_value
        elif isinstance(value, list):
            new_list: list = []
            for item in value:
                if isinstance(item, str):
                    new_item, v = _redact_text(item, allowed)
                    violations.extend(v)
                    new_list.append(new_item)
                else:
                    new_list.append(item)
            cleaned[key] = new_list
        elif isinstance(value, dict):
            nested, v = validate_report(value, allowed)
            violations.extend(v)
            cleaned[key] = nested
        else:
            cleaned[key] = value

    return cleaned, violations
