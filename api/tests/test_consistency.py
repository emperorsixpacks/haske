"""Tests for api/extraction/consistency.py."""

from __future__ import annotations

import datetime as dt

import pytest

from api.extraction.consistency import check_consistency, ConsistencyResult
from api.extraction.schemas import ExtractionResult, FieldConfidence


def _extraction(**kwargs) -> ExtractionResult:
    defaults = dict(
        product_name="Paracetamol 500mg",
        nrn="A4-100160",
        batch="PAN2024A",
        manufacture_date=None,
        expiry_date=None,
        manufacturer="Sterling",
        strength="500mg",
        category_guess="drug",
        shelf_life_months=None,
        confidence=FieldConfidence(),
        legibility_notes=[],
        layout_flags=[],
    )
    defaults.update(kwargs)
    return ExtractionResult(**defaults)


# --- Expiry checks ---

def test_expiry_past():
    e = _extraction(expiry_date="2020-01-01")
    r = check_consistency(e)
    assert "EXPIRY_PAST" in r.flags


def test_expiry_far_future():
    far = (dt.date.today().replace(year=dt.date.today().year + 12)).isoformat()
    e = _extraction(expiry_date=far)
    r = check_consistency(e)
    assert "EXPIRY_FAR_FUTURE" in r.flags


def test_expiry_normal_no_flag():
    future = (dt.date.today().replace(year=dt.date.today().year + 2)).isoformat()
    e = _extraction(expiry_date=future)
    r = check_consistency(e)
    assert "EXPIRY_PAST" not in r.flags
    assert "EXPIRY_FAR_FUTURE" not in r.flags


# --- Manufacture date checks ---

def test_mfg_in_future():
    future = (dt.date.today().replace(year=dt.date.today().year + 1)).isoformat()
    e = _extraction(manufacture_date=future)
    r = check_consistency(e)
    assert "MFG_IN_FUTURE" in r.flags


def test_mfg_in_past_no_flag():
    e = _extraction(manufacture_date="2023-01-01")
    r = check_consistency(e)
    assert "MFG_IN_FUTURE" not in r.flags


# --- Shelf life mismatch ---

def test_shelf_life_mismatch():
    # 24 months from 2023-01-01 = ~2024-12-31; use 2026-06-01 as expiry (too far)
    e = _extraction(
        manufacture_date="2023-01-01",
        expiry_date="2026-06-01",
        shelf_life_months=24,
    )
    r = check_consistency(e)
    assert "SHELF_LIFE_MISMATCH" in r.flags


def test_shelf_life_consistent():
    # 24 months from 2023-01-01 -> 2024-12-31 is within tolerance
    e = _extraction(
        manufacture_date="2023-01-01",
        expiry_date="2024-12-31",
        shelf_life_months=24,
    )
    r = check_consistency(e)
    assert "SHELF_LIFE_MISMATCH" not in r.flags


def test_shelf_life_no_dates_no_flag():
    e = _extraction(shelf_life_months=24)
    r = check_consistency(e)
    assert "SHELF_LIFE_MISMATCH" not in r.flags


# --- Layout flags forwarded ---

def test_layout_flags_forwarded():
    e = _extraction(layout_flags=["SPELLING_ERROR:Mangufacturer", "LOGO_QUALITY_LOW"])
    r = check_consistency(e)
    assert any("SPELLING_ERROR:Mangufacturer" in f for f in r.flags)
    assert any("LOGO_QUALITY_LOW" in f for f in r.flags)


def test_no_layout_flags_clean():
    e = _extraction(layout_flags=[])
    r = check_consistency(e)
    assert not any(f.startswith("LAYOUT:") for f in r.flags)


# --- Batch pattern heuristic ---

def test_batch_all_same_digit():
    e = _extraction(batch="00000")
    r = check_consistency(e)
    assert "BATCH_PATTERN_UNUSUAL" in r.flags


def test_batch_sequential():
    e = _extraction(batch="LOT12345")
    r = check_consistency(e)
    assert "BATCH_PATTERN_UNUSUAL" in r.flags


def test_batch_normal():
    e = _extraction(batch="PAN2024A")
    r = check_consistency(e)
    assert "BATCH_PATTERN_UNUSUAL" not in r.flags


def test_batch_none_no_flag():
    e = _extraction(batch=None)
    r = check_consistency(e)
    assert "BATCH_PATTERN_UNUSUAL" not in r.flags


# --- No flags when everything is clean ---

def test_clean_extraction_no_flags():
    future = (dt.date.today().replace(year=dt.date.today().year + 2)).isoformat()
    e = _extraction(
        manufacture_date="2024-01-01",
        expiry_date=future,
        shelf_life_months=None,
        layout_flags=[],
        batch="PAN2024A",
    )
    r = check_consistency(e)
    assert not r.has_flags
