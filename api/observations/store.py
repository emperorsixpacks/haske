"""Observation ledger: stores anonymised extracted fields for batch conflict detection.

Privacy rules:
- No photos are stored.
- Location is coarse (state/LGA) and opt-in only; defaults to null.
- device_hash is a one-way hash of a device ID for rate limiting only.
- Observations are append-only; no user profile is built.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sqlite3
import threading
import uuid
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id           TEXT PRIMARY KEY,
    nrn          TEXT NOT NULL,
    batch        TEXT NOT NULL,
    mfg_date     TEXT,
    expiry_date  TEXT,
    manufacturer TEXT,
    pack_size    TEXT,
    region       TEXT,
    source       TEXT NOT NULL DEFAULT 'user',
    ts           TEXT NOT NULL,
    device_hash  TEXT
);
CREATE INDEX IF NOT EXISTS obs_nrn_batch ON observations (nrn, batch);
CREATE INDEX IF NOT EXISTS obs_device_ts  ON observations (device_hash, ts);
"""

# Rate limits per device_hash (sliding window).
_RATE_LIMIT_HOURLY = 10
_RATE_LIMIT_DAILY = 50

# Minimum number of observations (excluding synthetic) before a conflict fires.
_MIN_OBS_FOR_CONFLICT = 5

# Tolerance when comparing dates (days). Accounts for OCR rounding.
_DATE_TOLERANCE_DAYS = 3


class ObservationStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        with self._lock:
            con = self._connect()
            con.executescript(_SCHEMA)
            con.commit()
            con.close()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self._db_path), check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        nrn: str,
        batch: str,
        mfg_date: str | None,
        expiry_date: str | None,
        manufacturer: str | None = None,
        pack_size: str | None = None,
        region: str | None = None,
        source: str = "user",
        device_id: str | None = None,
    ) -> str:
        """Insert one observation. Returns the new observation id.

        Raises RateLimitExceeded if the device has hit hourly or daily limits.
        """
        device_hash = _hash_device(device_id) if device_id else None

        with self._lock:
            con = self._connect()
            try:
                if device_hash and source == "user":
                    _check_rate_limit(con, device_hash)
                obs_id = str(uuid.uuid4())
                now = dt.datetime.now(dt.timezone.utc).isoformat()
                con.execute(
                    """
                    INSERT INTO observations
                        (id, nrn, batch, mfg_date, expiry_date, manufacturer,
                         pack_size, region, source, ts, device_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (obs_id, nrn, batch, mfg_date, expiry_date, manufacturer,
                     pack_size, region, source, now, device_hash),
                )
                con.commit()
                return obs_id
            finally:
                con.close()

    def conflict_check(self, nrn: str, batch: str, expiry_date: str | None) -> "ConflictResult":
        """Check whether this (nrn, batch, expiry) conflicts with prior observations.

        Only fires if there are at least _MIN_OBS_FOR_CONFLICT non-synthetic
        observations for the same (nrn, batch). Synthetic observations set the
        expected baseline but are never used as evidence of a conflict.
        """
        with self._lock:
            con = self._connect()
            try:
                rows = con.execute(
                    """
                    SELECT expiry_date, mfg_date, source, ts
                    FROM observations
                    WHERE nrn = ? AND batch = ?
                    ORDER BY ts ASC
                    """,
                    (nrn, batch),
                ).fetchall()
            finally:
                con.close()

        non_synthetic = [r for r in rows if r["source"] != "synthetic"]
        if len(non_synthetic) < _MIN_OBS_FOR_CONFLICT:
            return ConflictResult(conflict=False, observation_count=len(non_synthetic))

        if not expiry_date:
            return ConflictResult(conflict=False, observation_count=len(non_synthetic))

        # Find the most common expiry among non-synthetic observations.
        from collections import Counter
        counts: Counter[str] = Counter(
            r["expiry_date"] for r in non_synthetic if r["expiry_date"]
        )
        if not counts:
            return ConflictResult(conflict=False, observation_count=len(non_synthetic))

        dominant_expiry, _ = counts.most_common(1)[0]
        diff = _date_diff_days(expiry_date, dominant_expiry)
        if diff is None:
            return ConflictResult(conflict=False, observation_count=len(non_synthetic))

        if diff > _DATE_TOLERANCE_DAYS:
            first_seen = non_synthetic[0]["ts"][:10]
            return ConflictResult(
                conflict=True,
                observation_count=len(non_synthetic),
                dominant_expiry=dominant_expiry,
                new_expiry=expiry_date,
                first_seen=first_seen,
            )

        return ConflictResult(conflict=False, observation_count=len(non_synthetic))

    def seed(
        self,
        rows: list[dict],
        source: str = "seed",
    ) -> int:
        """Bulk-insert trusted observations (from pharmacies or manufacturers).

        Each row is a dict with keys: nrn, batch, mfg_date, expiry_date,
        manufacturer, pack_size, region.

        Returns the number of rows inserted.
        """
        inserted = 0
        with self._lock:
            con = self._connect()
            try:
                now = dt.datetime.now(dt.timezone.utc).isoformat()
                for row in rows:
                    con.execute(
                        """
                        INSERT OR IGNORE INTO observations
                            (id, nrn, batch, mfg_date, expiry_date, manufacturer,
                             pack_size, region, source, ts, device_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                        """,
                        (
                            str(uuid.uuid4()),
                            row["nrn"],
                            row["batch"],
                            row.get("mfg_date"),
                            row.get("expiry_date"),
                            row.get("manufacturer"),
                            row.get("pack_size"),
                            row.get("region"),
                            source,
                            now,
                        ),
                    )
                    inserted += 1
                con.commit()
            finally:
                con.close()
        return inserted

    def count(self, nrn: str | None = None, batch: str | None = None) -> int:
        """Return number of observations, optionally filtered by nrn and/or batch."""
        with self._lock:
            con = self._connect()
            try:
                if nrn and batch:
                    return con.execute(
                        "SELECT COUNT(*) FROM observations WHERE nrn = ? AND batch = ?",
                        (nrn, batch),
                    ).fetchone()[0]
                elif nrn:
                    return con.execute(
                        "SELECT COUNT(*) FROM observations WHERE nrn = ?", (nrn,)
                    ).fetchone()[0]
                else:
                    return con.execute(
                        "SELECT COUNT(*) FROM observations"
                    ).fetchone()[0]
            finally:
                con.close()


# ------------------------------------------------------------------
# Result type
# ------------------------------------------------------------------


class ConflictResult:
    def __init__(
        self,
        conflict: bool,
        observation_count: int = 0,
        dominant_expiry: str | None = None,
        new_expiry: str | None = None,
        first_seen: str | None = None,
    ) -> None:
        self.conflict = conflict
        self.observation_count = observation_count
        self.dominant_expiry = dominant_expiry
        self.new_expiry = new_expiry
        self.first_seen = first_seen

    def to_note(self) -> str | None:
        """Return a human-readable note for the evidence field, or None."""
        if not self.conflict:
            return None
        return (
            f"batch_conflict: expiry date '{self.new_expiry}' differs from "
            f"{self.observation_count} prior observations of this batch "
            f"(most common: '{self.dominant_expiry}', first seen {self.first_seen})"
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


class RateLimitExceeded(Exception):
    pass


def _hash_device(device_id: str) -> str:
    return hashlib.sha256(device_id.encode()).hexdigest()


def _check_rate_limit(con: sqlite3.Connection, device_hash: str) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    hour_ago = (now - dt.timedelta(hours=1)).isoformat()
    day_ago = (now - dt.timedelta(days=1)).isoformat()

    hourly = con.execute(
        "SELECT COUNT(*) FROM observations WHERE device_hash = ? AND ts > ? AND source = 'user'",
        (device_hash, hour_ago),
    ).fetchone()[0]
    if hourly >= _RATE_LIMIT_HOURLY:
        raise RateLimitExceeded(f"hourly limit ({_RATE_LIMIT_HOURLY}) reached")

    daily = con.execute(
        "SELECT COUNT(*) FROM observations WHERE device_hash = ? AND ts > ? AND source = 'user'",
        (device_hash, day_ago),
    ).fetchone()[0]
    if daily >= _RATE_LIMIT_DAILY:
        raise RateLimitExceeded(f"daily limit ({_RATE_LIMIT_DAILY}) reached")


def _date_diff_days(a: str, b: str) -> int | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            da = dt.datetime.strptime(a[:10], fmt).date()
            db = dt.datetime.strptime(b[:10], fmt).date()
            return abs((da - db).days)
        except ValueError:
            continue
    return None
