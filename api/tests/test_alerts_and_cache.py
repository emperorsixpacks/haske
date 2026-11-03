"""Tests for the NAPAMS cache workaround."""

import json

from api.registries.fake import BlockedNapamsClient, FakeNapamsClient, food_record
from api.registries.models import LookupOutcome, LookupResult, RegistryCategory
from api.registries.napams import NapamsCacheClient, load_napams_cache


# ---------------------------------------------------------------------------
# NapamsCacheClient (task 4)
# ---------------------------------------------------------------------------

def test_cache_hit_returns_without_hitting_live(tmp_path):
    cache_file = tmp_path / "napams_cache.json"
    cache_file.write_text(json.dumps({
        "02-4139": {
            "product_name": "Nivea Roll-on",
            "category": "cosmetic",
            "manufacturer": "BEIERSDORF",
            "expiry_date": "2029-02-27",
        }
    }))
    cache = load_napams_cache(cache_file)
    # Wrap a blocked live client to confirm it is never called on a cache hit.
    client = NapamsCacheClient(BlockedNapamsClient(), cache)
    result = client.lookup("02-4139", RegistryCategory.COSMETIC)
    assert result.outcome == LookupOutcome.FOUND
    assert result.records[0].product_name == "Nivea Roll-on"
    assert result.records[0].source == "napams_cache"


def test_cache_miss_falls_through_to_live():
    cache: dict = {}
    live = FakeNapamsClient({"01-9999": LookupResult.found([food_record("01-9999", "Golden Rice")])})
    client = NapamsCacheClient(live, cache)
    result = client.lookup("01-9999", RegistryCategory.FOOD)
    assert result.outcome == LookupOutcome.FOUND
    assert result.records[0].product_name == "Golden Rice"


def test_cache_miss_blocked_returns_incomplete():
    cache: dict = {}
    client = NapamsCacheClient(BlockedNapamsClient(), cache)
    result = client.lookup("02-9999", RegistryCategory.COSMETIC)
    assert result.outcome == LookupOutcome.CHECK_INCOMPLETE
    assert result.reason == "recaptcha_blocked"


def test_load_napams_cache_missing_file(tmp_path):
    result = load_napams_cache(tmp_path / "nonexistent.json")
    assert result == {}


def test_load_napams_cache_bad_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json at all")
    result = load_napams_cache(bad)
    assert result == {}


def test_load_napams_cache_skips_malformed_entries(tmp_path):
    cache_file = tmp_path / "mixed.json"
    cache_file.write_text(json.dumps({
        "01-0001": {"product_name": "Good Product"},
        "bad-entry": "this is not a dict",
    }))
    result = load_napams_cache(cache_file)
    assert "01-0001" in result
    assert "bad-entry" not in result


# Alert registry tests live in api/tests/test_alerts.py (Evidence-First).
