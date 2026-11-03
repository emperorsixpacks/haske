"""Deterministic label consistency checks.

Runs after extraction, before the verdict. Each check produces a flag string
that is passed to the verdict engine as evidence signals. None of these checks
change the verdict code by themselves; they appear in the evidence note and
on the result screen under "signals found".

No model calls are made here. All logic is rule-based.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .schemas import ExtractionResult

# Maximum shelf life we consider plausible for a pharmaceutical product (years).
_MAX_SHELF_LIFE_YEARS = 10

# Tolerance when comparing stated shelf life to calculated shelf life (days).
# Accounts for OCR date rounding (e.g. "08/2027" -> last day of month).
_SHELF_LIFE_TOLERANCE_DAYS = 62  # ~2 months


@dataclass
class ConsistencyResult:
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def has_flags(self) -> bool:
        return bool(self.flags)


def check_consistency(extraction: ExtractionResult) -> ConsistencyResult:
    """Run all consistency checks and return aggregated flags and notes.

    Called from CheckService._evaluate after extraction.
    """
    result = ConsistencyResult()
    today = dt.date.today()

    expiry = _parse_date(extraction.expiry_date)
    mfg = _parse_date(extraction.manufacture_date)

    # --- Date range checks ---
    if expiry is not None:
        if expiry < today:
            result.flags.append("EXPIRY_PAST")
            result.notes.append(
                f"Expiry date {extraction.expiry_date} is in the past."
            )
        elif expiry > today.replace(year=today.year + _MAX_SHELF_LIFE_YEARS):
            result.flags.append("EXPIRY_FAR_FUTURE")
            result.notes.append(
                f"Expiry date {extraction.expiry_date} is more than "
                f"{_MAX_SHELF_LIFE_YEARS} years away, which is unusual."
            )

    if mfg is not None and mfg > today:
        result.flags.append("MFG_IN_FUTURE")
        result.notes.append(
            f"Manufacture date {extraction.manufacture_date} is in the future."
        )

    # --- Shelf life cross-check ---
    if (
        extraction.shelf_life_months is not None
        and expiry is not None
        and mfg is not None
        and mfg <= today  # only check if mfg is plausible
    ):
        stated_days = extraction.shelf_life_months * 30.4375  # average days per month
        actual_days = (expiry - mfg).days
        if abs(actual_days - stated_days) > _SHELF_LIFE_TOLERANCE_DAYS:
            result.flags.append("SHELF_LIFE_MISMATCH")
            result.notes.append(
                f"Stated shelf life ({extraction.shelf_life_months} months) does not "
                f"match the gap between manufacture ({extraction.manufacture_date}) "
                f"and expiry ({extraction.expiry_date}) dates."
            )

    # --- Forward model layout flags ---
    # The vision model reported these; include them verbatim as signals.
    for flag in extraction.layout_flags:
        result.flags.append(f"LAYOUT:{flag}")
        result.notes.append(f"Label layout signal: {flag}")

    # --- Batch heuristic (import avoids circular dep with web lib/batch.ts) ---
    if _is_unusual_batch(extraction.batch):
        result.flags.append("BATCH_PATTERN_UNUSUAL")
        result.notes.append(
            f"Batch code '{extraction.batch}' contains an unusual repeated or "
            "sequential pattern."
        )

    return result


# --- Helpers ---

def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%Y"):
        try:
            parsed = dt.datetime.strptime(value[:10], fmt).date()
            return parsed
        except ValueError:
            continue
    return None


def _is_unusual_batch(batch: str | None) -> bool:
    """Mirror of web/src/lib/batch.ts isUnusualBatch, kept in sync manually."""
    if not batch:
        return False
    digits = "".join(c for c in batch if c.isdigit())
    if len(digits) < 4:
        return False
    # All same digit.
    if len(set(digits)) == 1:
        return True
    # Run of 5+ consecutive ascending or descending digits.
    for i in range(len(digits) - 4):
        win = [int(digits[i + j]) for j in range(5)]
        asc = all(win[j] == win[j - 1] + 1 for j in range(1, 5))
        desc = all(win[j] == win[j - 1] - 1 for j in range(1, 5))
        if asc or desc:
            return True
    return False
