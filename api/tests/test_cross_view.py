"""Tests for the cross-view consistency check."""

from __future__ import annotations

from api.extraction.cross_view import cross_view_check


def test_cross_view_agrees_when_fields_match():
    views = [
        {"product_name": "Postinor 2", "nrn": "04-6985", "manufacturer": "Richter", "strength": "0.75mg"},
        {"product_name": "Postinor 2", "nrn": "04-6985", "manufacturer": "Richter", "strength": "0.75mg"},
    ]
    result = cross_view_check(views)
    assert result.mismatches == []


def test_cross_view_flags_mismatch():
    views = [
        {"product_name": "Postinor 2", "nrn": "04-6985"},
        {"product_name": "Postinor 2", "nrn": "04-6986"},
    ]
    result = cross_view_check(views)
    assert "nrn" in result.mismatches


def test_cross_view_ignores_missing_fields():
    views = [
        {"product_name": "Postinor 2", "nrn": "04-6985"},
        {"product_name": "Postinor 2"},  # no nrn in this view
    ]
    result = cross_view_check(views)
    assert result.mismatches == []
    assert result.per_field["nrn"]["views_with_value"] == 1


def test_cross_view_normalizes_spacing_case():
    views = [
        {"nrn": "04-6985"},
        {"nrn": "04 6985"},
    ]
    result = cross_view_check(views)
    assert result.mismatches == []
