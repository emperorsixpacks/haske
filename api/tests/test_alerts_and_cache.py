"""Tests for NAPAMS cache workaround (task 4) and alert registry stub (task 6)."""

import json
import datetime as dt

import pytest

from api.registries.alerts import AlertRecord, AlertRegistry
from api.registries.fake import BlockedNapamsClient, FakeNapamsClient, food_record
from api.registries.models import LookupOutcome, LookupResult, RegistryCategory
from api.registries.napams import NapamsCacheClient, NapamsClient, load_napams_cache
from api.app.config import Settings


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


# ---------------------------------------------------------------------------
# AlertRegistry stub (task 6)
# ---------------------------------------------------------------------------

def test_alert_registry_empty_by_default():
    reg = AlertRegistry()
    assert reg.lookup("A4-0123") is None
    assert len(reg) == 0


def test_alert_registry_lookup_by_nrn():
    reg = AlertRegistry()
    alert = AlertRecord(nrn="A4-0123", product_name="Fake Paracetamol")
    reg.add(alert)
    assert reg.lookup("A4-0123") is alert
    assert reg.lookup("A4-9999") is None


def test_alert_registry_batch_specific_match():
    reg = AlertRegistry()
    alert = AlertRecord(nrn="A4-0123", product_name="Fake Drug", batch="BN001")
    reg.add(alert)
    assert reg.lookup("A4-0123", "BN001") is alert
    assert reg.lookup("A4-0123", "BN002") is None


def test_alert_registry_no_batch_matches_all():
    reg = AlertRegistry()
    alert = AlertRecord(nrn="A4-0123", product_name="Recalled Drug", batch=None)
    reg.add(alert)
    assert reg.lookup("A4-0123", "BN001") is alert
    assert reg.lookup("A4-0123", None) is alert


def test_alert_registry_case_insensitive():
    reg = AlertRegistry()
    alert = AlertRecord(nrn="a4-0123", product_name="Product")
    reg.add(alert)
    assert reg.lookup("A4-0123") is alert


def test_alert_match_verdict_when_registry_has_entry():
    """When the alert registry has a match, decide() returns ALERT_MATCH."""
    from api.registries.alerts import AlertRegistry, AlertRecord
    from api.registries.matcher import MatchOutcome, MatchResult
    from api.registries.models import LookupResult, RegistryRecord
    from api.verdict.engine import VerdictCode, decide
    import api.registries.alerts as alerts_module

    # Temporarily populate the global registry.
    original = alerts_module._registry
    try:
        alerts_module._registry = AlertRegistry([
            AlertRecord(nrn="A4-0123", product_name="Fake Paracetamol")
        ])
        record = RegistryRecord(
            nrn="A4-0123", product_name="Paracetamol 500mg", status="Active", source="greenbook"
        )
        verdict = decide(
            LookupResult.found([record], nrn="A4-0123"),
            MatchResult(outcome=MatchOutcome.MATCH, matched_record=record),
            RegistryCategory.DRUG,
        )
        assert verdict.code == VerdictCode.ALERT_MATCH
        assert "fake" not in verdict.message.lower()
        assert "counterfeit" not in verdict.message.lower()
    finally:
        alerts_module._registry = original
