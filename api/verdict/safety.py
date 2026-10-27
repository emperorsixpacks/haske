"""Medical-advice guard.

The system must never give dosing, take, or stop advice. This module detects requests for
such advice so the caller can respond with a redirect to a pharmacist instead.
"""

from __future__ import annotations

import re

from .messages import PHARMACIST_REDIRECT

_ADVICE_PATTERNS = [
    r"\bcan i (still )?take\b",
    r"\bshould i (still )?take\b",
    r"\bis it safe to take\b",
    r"\bcan i (still )?use\b",
    r"\bstop taking\b",
    r"\bstart taking\b",
    r"\bdosage\b",
    r"\bdose\b",
    r"\bhow much (should|do) i take\b",
    r"\btake (a|the) pill\b",
    r"\boverdose\b",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in _ADVICE_PATTERNS]


def is_medical_advice_request(text: str | None) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in _compiled)


def redirect_medical_advice() -> str:
    return PHARMACIST_REDIRECT
