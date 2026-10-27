"""NRN (NAFDAC Registration Number) normalisation.

Formats in the wild include "A4-0123" and "04-5808", with case, spacing, and dash
variants. We normalise to a canonical two-group, dash-joined form ("A4-0123"), flag (never
guess) the O vs 0 ambiguity, and reject 12-13 digit strings as barcodes rather than NRNs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Characters treated as group separators in a written NRN.
_SEPARATORS = re.compile(r"[\s\-_/]+")

# A valid first group is a letter-or-digit followed by one or two digits, e.g. "A4", "04".
_GROUP1_RE = re.compile(r"^[A-Z0-9][0-9]{1,2}$")
# A valid second group is a run of digits.
_GROUP2_RE = re.compile(r"^[0-9]{2,5}$")


@dataclass(frozen=True)
class NormalisedNRN:
    raw: str
    canonical: str | None
    is_barcode: bool = False
    ambiguous_o_zero: bool = False
    error: str | None = None

    @property
    def valid(self) -> bool:
        return self.canonical is not None and not self.is_barcode


def normalise_nrn(value: str | None) -> NormalisedNRN:
    """Return a canonical NRN or a rejected/ambiguous result.

    We never guess between the letter O and the digit 0; if the letter O appears we flag
    it and still attempt the normalised form, so callers can decide whether to trust it.
    """
    if value is None:
        return NormalisedNRN(raw="", canonical=None, error="empty")
    raw = value.strip()
    if not raw:
        return NormalisedNRN(raw=raw, canonical=None, error="empty")

    # 12-13 digit strings (ignoring separators) are barcodes (EAN/UPC), not NRNs.
    compact = re.sub(r"[\s\-_/]", "", raw).upper()
    if re.fullmatch(r"[0-9]{12,13}", compact):
        return NormalisedNRN(raw=raw, canonical=None, is_barcode=True, error="looks_like_barcode")

    ambiguous = "O" in compact
    norm = compact.replace("O", "0")

    if _SEPARATORS.search(raw):
        groups = [g for g in _SEPARATORS.split(raw.upper()) if g]
        groups = [g.replace("O", "0") for g in groups]
        if len(groups) == 2 and _GROUP1_RE.fullmatch(groups[0]) and _GROUP2_RE.fullmatch(groups[1]):
            return NormalisedNRN(raw=raw, canonical=f"{groups[0]}-{groups[1]}", ambiguous_o_zero=ambiguous)
        return NormalisedNRN(raw=raw, canonical=None, ambiguous_o_zero=ambiguous, error="unrecognised_format")

    # No separator: split into a 2-char first group and the remaining digits.
    if len(norm) >= 4:
        group1, group2 = norm[:2], norm[2:]
        if _GROUP1_RE.fullmatch(group1) and _GROUP2_RE.fullmatch(group2):
            return NormalisedNRN(raw=raw, canonical=f"{group1}-{group2}", ambiguous_o_zero=ambiguous)
    return NormalisedNRN(raw=raw, canonical=None, ambiguous_o_zero=ambiguous, error="unrecognised_format")
