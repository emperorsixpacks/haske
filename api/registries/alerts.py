"""Public-alert registry stub (Milestone 2).

When NAFDAC publishes a public advisory matching a product AND batch, the verdict engine
must return ALERT_MATCH instead of CONSISTENT_WITH_REGISTRY. This module will hold the
parsed alert database and the lookup logic.

Milestone 1 status: STUB. No alert data is loaded. lookup() always returns None.
Milestone 2 tasks:
- Parse NAFDAC public-alert PDFs/HTML into AlertRecord entries.
- Populate a store (SQLite table or JSON file) with alert records.
- Implement lookup() to match NRN + batch against stored alerts.
- Wire the result into verdict/engine.py decide() (see the ALERT_MATCH check there).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AlertRecord:
    """A single NAFDAC public advisory entry."""

    nrn: str
    product_name: str
    batch: str | None = None  # None means the alert applies to all batches
    alert_url: str | None = None
    issued_date: dt.date | None = None
    summary: str | None = None


class AlertRegistry:
    """In-memory alert registry. Milestone 2 will load from a persistent store."""

    def __init__(self, records: list[AlertRecord] | None = None):
        self._records: list[AlertRecord] = records or []

    def add(self, record: AlertRecord) -> None:
        self._records.append(record)

    def lookup(self, nrn: str, batch: str | None = None) -> AlertRecord | None:
        """Return the first alert that matches the NRN and (if present) the batch.

        Matching rules:
        - NRN must match exactly (case-insensitive).
        - If the alert has no batch, it matches all batches.
        - If the alert has a batch, it must match the supplied batch (case-insensitive).
        Returns None if no alert matches (milestone 1: always None).
        """
        nrn_norm = nrn.strip().upper()
        batch_norm = (batch or "").strip().upper()
        for alert in self._records:
            if alert.nrn.strip().upper() != nrn_norm:
                continue
            if alert.batch is None:
                return alert
            if batch_norm and alert.batch.strip().upper() == batch_norm:
                return alert
        return None

    def __len__(self) -> int:
        return len(self._records)


# Module-level singleton. Milestone 2 will populate this from a data source.
_registry = AlertRegistry()


def get_alert_registry() -> AlertRegistry:
    """Return the shared alert registry (always empty in milestone 1)."""
    return _registry
