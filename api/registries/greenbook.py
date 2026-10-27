"""Greenbook snapshotter.

Source: https://greenbook.nafdac.gov.ng (drugs, vaccines, devices, veterinary, herbals,
disinfectants; NOT cosmetics or soaps). There is no official API, but the public search table
is a Laravel server-side DataTables feed: a GET to the site root with `X-Requested-With:
XMLHttpRequest` and DataTables paging params (`start`, `length`, `draw`) returns JSON with
`recordsTotal`, `recordsFiltered` and a `data` array of object rows. This shape is VERIFIED
against the live site (fetched 2026-10-27); the exact row keys are below.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path

import httpx

from ..app.config import Settings
from .models import LookupResult, RegistryCategory, RegistryRecord
from .store import Store

# Contact fields must never be persisted, even inside the raw record.
_CONTACT_KEY_RE = re.compile(r"(email|phone|tel|mobile|fax|address|contact)", re.IGNORECASE)

# Verified exact row keys (Laravel flattens the eager-loaded relationships into both nested
# objects and *_name / *_id fields). The NAFDAC number is the "NAFDAC" key. Manufacturer is
# only available as manufacturer_id in this feed, not a name.
_FIELD_KEYS: dict[str, list[str]] = {
    "nrn": ["NAFDAC", "nrn"],
    "product_name": ["product_name"],
    "category": ["category_name", "product_category_name"],
    "status": ["status"],
    "applicant": ["applicant_name"],
    "manufacturer": ["manufacturer_name"],
    "active_ingredients": ["ingredient_name", "composition"],
    "strength": ["strength"],
    "form": ["form_name"],
    "approval_date": ["approval_date"],
    "expiry_date": ["expiry_date"],
}


class GreenbookError(RuntimeError):
    """Raised when the Greenbook response cannot be trusted or parsed."""


class GreenbookClient:
    """RegistryClient-style lookup against the Greenbook snapshot store."""

    name = "greenbook"
    source_url = "https://greenbook.nafdac.gov.ng"

    def __init__(self, store: Store):
        self.store = store

    def lookup(self, nrn: str, category=None) -> "LookupResult":
        records = self.store.lookup(nrn)
        if records:
            return LookupResult.found(records, nrn=nrn, source="greenbook", source_url=self.source_url)
        return LookupResult.not_found(nrn=nrn, source="greenbook", source_url=self.source_url)


class GreenbookSnapshotter:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        transport: httpx.BaseTransport | None = None,
    ):
        self.settings = settings
        self.store = store
        self._transport = transport

    def _http(self) -> httpx.Client:
        headers = {
            "User-Agent": self.settings.user_agent,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        }
        return httpx.Client(
            transport=self._transport,
            headers=headers,
            timeout=self.settings.request_timeout_seconds,
        )

    def robots_ok(self) -> tuple[bool, str]:
        """Check robots.txt and return (allowed, reason)."""
        with self._http() as client:
            try:
                resp = client.get(self.settings.greenbook_base_url.rstrip("/") + "/robots.txt")
                if resp.status_code != 200:
                    return True, "robots.txt not found, proceeding"
                text = resp.text
            except httpx.HTTPError as exc:
                return False, f"robots.txt unavailable: {exc}"
        # Parse Disallow lines; a blanket "Disallow: /" blocks everything.
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path in ("/", "*"):
                    return False, f"robots.txt disallows {path}"
        return True, "robots.txt allows"

    def _request_page(self, client: httpx.Client, start: int, length: int, draw: int) -> dict:
        url = self.settings.greenbook_base_url.rstrip("/") + "/"
        params = {"start": start, "length": length, "draw": draw}
        resp = client.get(url, params=params)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise GreenbookError(f"server returned {resp.status_code}, backing off")
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            raise GreenbookError(f"non-JSON response: {exc}") from exc

    def _extract_rows(self, payload: dict) -> list[dict]:
        """Extract row dicts from a DataTables-style payload (UNVERIFIED shape)."""
        if not isinstance(payload, dict):
            raise GreenbookError(f"expected a JSON object, got {type(payload).__name__}")
        data = payload.get("data")
        if data is None:
            # Some endpoints return a bare list.
            if isinstance(payload, dict) and all(k.isdigit() for k in payload.keys()):
                data = list(payload.values())
            else:
                raise GreenbookError(f"no 'data' key in payload; keys={list(payload.keys())}")
        if not isinstance(data, list):
            raise GreenbookError(f"'data' is {type(data).__name__}, expected list")
        rows: list[dict] = []
        for item in data:
            if isinstance(item, dict):
                rows.append(item)
            elif isinstance(item, list):
                rows.append({"__row__": item})
            else:
                raise GreenbookError(f"unexpected row type {type(item).__name__}")
        return rows

    def _column_value(self, row: dict, field: str) -> str | None:
        """Return a normalised string value for a field from a raw row dict."""
        if "__row__" in row:
            return None
        keys = _FIELD_KEYS.get(field, [])
        for key in keys:
            if key in row:
                return _to_text(row.get(key))
        # Fallback: fuzzy substring match on normalised keys (underscore -> space).
        norm_keys = {str(k).lower().replace("_", " "): v for k, v in row.items() if k is not None}
        for key in keys:
            wanted = key.lower().replace("_", " ")
            for norm_key, value in norm_keys.items():
                if wanted and wanted in norm_key:
                    return _to_text(value)
        return None

    def normalise(self, row: dict) -> RegistryRecord | None:
        """Normalise a raw row into a RegistryRecord, stripping contact fields."""
        raw = {k: v for k, v in row.items() if k != "__row__" and not _CONTACT_KEY_RE.search(str(k))}
        nrn = self._column_value(row, "nrn")
        product_name = self._column_value(row, "product_name")
        if not nrn or not product_name:
            return None
        # The frontend strips decorative '#'/'*' from names; mirror that.
        product_name = product_name.replace("#", "").replace("*", "").strip()
        ingredients = self._column_value(row, "active_ingredients")
        category_raw = (self._column_value(row, "category") or "").lower()
        category = _guess_category(category_raw)
        return RegistryRecord(
            nrn=nrn,
            product_name=product_name,
            category=category,
            status=self._column_value(row, "status"),
            applicant=self._column_value(row, "applicant"),
            manufacturer=self._column_value(row, "manufacturer"),
            active_ingredients=_split_ingredients(ingredients),
            strength=self._column_value(row, "strength"),
            form=self._column_value(row, "form"),
            approval_date=self._column_value(row, "approval_date"),
            expiry_date=self._column_value(row, "expiry_date"),
            source="greenbook",
            source_url=self.settings.greenbook_base_url,
            raw=raw,
        )

    def probe(self) -> dict:
        """Fetch 3 rows and return diagnostic info; raise if the shape is unexpected."""
        allowed, reason = self.robots_ok()
        if not allowed:
            raise GreenbookError(f"blocked by robots.txt: {reason}")
        with self._http() as client:
            payload = self._request_page(client, start=0, length=3, draw=1)
        rows = self._extract_rows(payload)
        if not rows:
            raise GreenbookError("fetched 3 rows but got 0; the DataTables shape may have changed")
        return {
            "top_level_keys": list(payload.keys()),
            "recordsTotal": payload.get("recordsTotal"),
            "recordsFiltered": payload.get("recordsFiltered"),
            "row_count": len(rows),
            "first_row": rows[0],
        }

    def fetch(self, force: bool = False, page_size: int = 500) -> dict:
        """Page the full table into a dated snapshot with a content hash."""
        allowed, reason = self.robots_ok()
        if not allowed and not force:
            raise GreenbookError(f"blocked by robots.txt: {reason}")

        fetched_at = dt.datetime.now(dt.timezone.utc)
        all_rows: list[dict] = []
        with self._http() as client:
            first = self._request_page(client, start=0, length=1, draw=1)
            total = int(first.get("recordsTotal") or first.get("recordsFiltered") or 0)
            if total <= 0:
                raise GreenbookError("recordsTotal is 0; cannot page")
            draw = 2
            start = 0
            while start < total:
                payload = self._request_page(client, start=start, length=page_size, draw=draw)
                rows = self._extract_rows(payload)
                if not rows:
                    raise GreenbookError(f"empty page at start={start}; aborting")
                all_rows.extend(rows)
                start += len(rows)
                draw += 1
                if start < total:
                    time.sleep(self.settings.request_delay_seconds)

        if not all_rows:
            raise GreenbookError("no rows fetched")

        prev = self.store.latest_snapshot()
        if prev and not force:
            floor = int(prev["record_count"] * self.settings.snapshot_min_ratio)
            if len(all_rows) < floor:
                raise GreenbookError(
                    f"fetched {len(all_rows)} rows, under 80% of previous snapshot "
                    f"({prev['record_count']}); use --force to save anyway"
                )

        records = [r for r in (self.normalise(row) for row in all_rows) if r is not None]
        raw_bytes = json.dumps(all_rows, default=str, ensure_ascii=False).encode("utf-8")
        content_hash = hashlib.sha256(raw_bytes).hexdigest()

        self.settings.snapshots_dir.mkdir(parents=True, exist_ok=True)
        fname = f"greenbook_{fetched_at:%Y%m%dT%H%M%SZ}_{content_hash[:12]}.json"
        file_path = self.settings.snapshots_dir / fname
        file_path.write_bytes(raw_bytes)

        snapshot_id = self.store.add_snapshot(
            source="greenbook",
            fetched_at=fetched_at,
            record_count=len(all_rows),
            content_hash=content_hash,
            file_path=str(file_path),
            forced=force,
        )
        self.store.add_records(snapshot_id, records)

        return {
            "snapshot_id": snapshot_id,
            "fetched_at": fetched_at.isoformat(),
            "rows": len(all_rows),
            "normalised": len(records),
            "content_hash": content_hash,
            "file": str(file_path),
        }


def _to_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=str)
    text = str(value).strip()
    return text or None


def _split_ingredients(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[,;|/]", value)
    return [p.strip() for p in parts if p.strip()]


def _guess_category(raw: str) -> RegistryCategory:
    raw_l = raw.lower()
    if "vaccine" in raw_l:
        return RegistryCategory.VACCINE
    if "device" in raw_l or "medical device" in raw_l:
        return RegistryCategory.DEVICE
    if "veterinary" in raw_l or "vet" in raw_l:
        return RegistryCategory.VETERINARY
    if "herbal" in raw_l:
        return RegistryCategory.HERBAL
    if "disinfectant" in raw_l:
        return RegistryCategory.DEVICE
    if "drug" in raw_l or "medicine" in raw_l or "pharmaceutical" in raw_l:
        return RegistryCategory.DRUG
    if "cosmetic" in raw_l:
        return RegistryCategory.COSMETIC
    if "soap" in raw_l:
        return RegistryCategory.SOAP
    return RegistryCategory.DRUG
