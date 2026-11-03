"""Tests for api/observations/store.py."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import pytest

from api.observations.store import ObservationStore, RateLimitExceeded


@pytest.fixture
def store(tmp_path):
    return ObservationStore(tmp_path / "obs.db")


# --- Basic record + count ---

def test_record_and_count(store):
    store.record(nrn="A4-100160", batch="PAN2024A", mfg_date="2024-01-01", expiry_date="2026-01-31")
    assert store.count(nrn="A4-100160", batch="PAN2024A") == 1


def test_count_all(store):
    store.record(nrn="A4-100160", batch="PAN2024A", mfg_date=None, expiry_date="2026-01-31")
    store.record(nrn="B2-0451", batch="X99", mfg_date=None, expiry_date="2027-06-30")
    assert store.count() == 2


# --- No conflict below floor ---

def test_no_conflict_below_minimum_observations(store):
    # Only 3 prior observations (below the floor of 5)
    for _ in range(3):
        store.record(nrn="A4-100160", batch="PAN2024A", mfg_date="2024-01-01", expiry_date="2026-01-31")
    result = store.conflict_check("A4-100160", "PAN2024A", "2028-01-31")
    assert not result.conflict


# --- Conflict fires above floor ---

def test_conflict_fires_above_floor(store):
    # 5 observations all with expiry 2026-01-31
    for _ in range(5):
        store.record(nrn="A4-100160", batch="PAN2024A", mfg_date="2024-01-01", expiry_date="2026-01-31")
    # New scan claims expiry 2028-06-30 (more than 3 days different)
    result = store.conflict_check("A4-100160", "PAN2024A", "2028-06-30")
    assert result.conflict
    assert result.observation_count == 5
    assert result.dominant_expiry == "2026-01-31"


def test_no_conflict_when_dates_agree(store):
    for _ in range(5):
        store.record(nrn="A4-100160", batch="PAN2024A", mfg_date="2024-01-01", expiry_date="2026-01-31")
    result = store.conflict_check("A4-100160", "PAN2024A", "2026-01-31")
    assert not result.conflict


def test_no_conflict_within_tolerance(store):
    # 3-day tolerance: 2026-01-31 vs 2026-02-02 = 2 days
    for _ in range(5):
        store.record(nrn="A4-100160", batch="PAN2024A", mfg_date="2024-01-01", expiry_date="2026-01-31")
    result = store.conflict_check("A4-100160", "PAN2024A", "2026-02-02")
    assert not result.conflict


# --- Synthetic observations count toward floor but not conflict evidence ---

def test_synthetic_sets_floor_but_not_conflict(store):
    # 5 synthetic observations
    store.seed([
        {"nrn": "A4-100160", "batch": "PAN2024A", "mfg_date": "2024-01-01", "expiry_date": "2026-01-31"}
        for _ in range(5)
    ], source="synthetic")
    # No non-synthetic observations -> below floor
    result = store.conflict_check("A4-100160", "PAN2024A", "2028-06-30")
    assert not result.conflict


def test_mixed_seed_and_user_triggers_conflict(store):
    # 3 synthetic + 5 real user observations with consistent expiry
    store.seed([
        {"nrn": "A4-100160", "batch": "PAN2024A", "mfg_date": "2024-01-01", "expiry_date": "2026-01-31"}
        for _ in range(3)
    ], source="synthetic")
    for _ in range(5):
        store.record(nrn="A4-100160", batch="PAN2024A", mfg_date="2024-01-01", expiry_date="2026-01-31")
    result = store.conflict_check("A4-100160", "PAN2024A", "2028-06-30")
    assert result.conflict


# --- ConflictResult.to_note ---

def test_to_note_returns_none_when_no_conflict(store):
    for _ in range(5):
        store.record(nrn="A4-100160", batch="PAN2024A", mfg_date="2024-01-01", expiry_date="2026-01-31")
    result = store.conflict_check("A4-100160", "PAN2024A", "2026-01-31")
    assert result.to_note() is None


def test_to_note_contains_key_info(store):
    for _ in range(5):
        store.record(nrn="A4-100160", batch="PAN2024A", mfg_date="2024-01-01", expiry_date="2026-01-31")
    result = store.conflict_check("A4-100160", "PAN2024A", "2028-06-30")
    note = result.to_note()
    assert note is not None
    assert "batch_conflict" in note
    assert "2028-06-30" in note
    assert "2026-01-31" in note


# --- Rate limiting ---

def test_rate_limit_hourly(store):
    device = "device-001"
    # Insert up to the hourly limit
    for i in range(10):
        store.record(
            nrn=f"A4-{i:06d}", batch="BATCH", mfg_date=None, expiry_date=None,
            device_id=device
        )
    # The 11th should be rejected
    with pytest.raises(RateLimitExceeded):
        store.record(nrn="A4-999999", batch="BATCH", mfg_date=None, expiry_date=None, device_id=device)


# --- Seed ---

def test_seed_inserts_rows(store):
    rows = [
        {"nrn": "A4-100160", "batch": "PAN2024A", "mfg_date": "2024-01-01", "expiry_date": "2026-01-31"},
        {"nrn": "B2-0451",   "batch": "X99",       "mfg_date": "2023-06-01", "expiry_date": "2025-05-31"},
    ]
    inserted = store.seed(rows)
    assert inserted == 2
    assert store.count() == 2
