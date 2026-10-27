"""SQLite repository for Greenbook snapshots and normalised records.

SQL is written to be Postgres-compatible: no sqlite-specific pragmas or types in the
statements themselves. sqlite3 is used for milestone 1; the layer can be swapped for a
Postgres driver without changing the queries.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
from pathlib import Path

from .models import RegistryRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    forced INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS greenbook_records (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    nrn TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT,
    status TEXT,
    applicant TEXT,
    manufacturer TEXT,
    active_ingredients TEXT,
    strength TEXT,
    form TEXT,
    approval_date TEXT,
    expiry_date TEXT,
    raw TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_greenbook_nrn ON greenbook_records (nrn);
"""


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def add_snapshot(
        self,
        source: str,
        fetched_at: dt.datetime,
        record_count: int,
        content_hash: str,
        file_path: str,
        forced: bool = False,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO snapshots (source, fetched_at, record_count, content_hash, file_path, forced) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source, fetched_at.isoformat(), record_count, content_hash, file_path, 1 if forced else 0),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def add_records(self, snapshot_id: int, records: list[RegistryRecord]) -> int:
        rows = [
            (
                snapshot_id,
                r.nrn,
                r.product_name,
                r.category.value,
                r.status,
                r.applicant,
                r.manufacturer,
                json.dumps(r.active_ingredients),
                r.strength,
                r.form,
                r.approval_date,
                r.expiry_date,
                json.dumps(r.raw, default=str),
            )
            for r in records
        ]
        with self._lock:
            self._conn.executemany(
                "INSERT INTO greenbook_records "
                "(snapshot_id, nrn, product_name, category, status, applicant, manufacturer, "
                "active_ingredients, strength, form, approval_date, expiry_date, raw) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()
            return len(rows)

    def lookup(self, nrn: str) -> list[RegistryRecord]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM greenbook_records WHERE nrn = ?", (nrn,)
            )
            rows = cur.fetchall()
        return [_row_to_record(row) for row in rows]

    def latest_snapshot(self) -> dict | None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM snapshots ORDER BY fetched_at DESC LIMIT 1"
            )
            row = cur.fetchone()
        if row is None:
            return None
        return dict(row)

    def record_count(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) AS c FROM greenbook_records")
            row = cur.fetchone()
            return int(row["c"])


def _row_to_record(row: sqlite3.Row) -> RegistryRecord:
    raw = json.loads(row["raw"]) if row["raw"] else {}
    ingredients = json.loads(row["active_ingredients"]) if row["active_ingredients"] else []
    return RegistryRecord(
        nrn=row["nrn"],
        product_name=row["product_name"],
        category=row["category"] or "unknown",
        status=row["status"],
        applicant=row["applicant"],
        manufacturer=row["manufacturer"],
        active_ingredients=ingredients,
        strength=row["strength"],
        form=row["form"],
        approval_date=row["approval_date"],
        expiry_date=row["expiry_date"],
        raw=raw,
    )
