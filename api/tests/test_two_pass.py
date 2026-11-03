"""Tests for two-pass reading: crop, agreement metric, and disagreement detection."""

from __future__ import annotations

import io

from PIL import Image

from api.extraction.crop import clamp_box, crop_to_box
from api.extraction.schemas import ExtractionResult, FieldConfidence
from api.extraction.two_pass import field_agreement, two_pass_read


def _jpeg_bytes(w=200, h=200):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="JPEG")
    return buf.getvalue()


class _StubExtractor:
    def __init__(self, pass1: ExtractionResult, crops: dict[str, str | None]):
        self.pass1 = pass1
        self.crops = crops

    def extract(self, image_bytes, filename=None):
        if filename and filename.endswith("_crop"):
            field = filename.split("_crop")[0]
            value = self.crops.get(field)
            return ExtractionResult(
                **{field: value},
                confidence=FieldConfidence(**{field: 0.9 if value else 0.0}),
            )
        return self.pass1


def test_clamp_box_clamps_out_of_range():
    x0, y0, x1, y1 = clamp_box([-1.0, 0.0, 2.0, 1.0], 100, 100)
    assert x0 == 0.0 and x1 == 1.0


def test_crop_to_box_returns_jpeg():
    img = _jpeg_bytes()
    out = crop_to_box(img, [0.0, 0.0, 0.5, 0.5])
    assert out.startswith(b"\xff\xd8")  # JPEG magic


def test_field_agreement_exact_and_fuzzy():
    assert field_agreement("A4-100160", "A4-100160")[0] == 1.0
    assert field_agreement("A4-100160", "A4-100160")[1] == "exact"
    assert field_agreement(None, None)[0] == 1.0
    assert field_agreement("A4-100160", None)[1] == "one_empty"


def test_two_pass_read_agrees_when_values_match():
    pass1 = ExtractionResult(
        nrn="A4-100160", batch="BN2024",
        boxes={"nrn": [0.1, 0.1, 0.4, 0.2], "batch": [0.1, 0.3, 0.4, 0.4]},
    )
    extractor = _StubExtractor(pass1, {"nrn": "A4-100160", "batch": "BN2024"})
    result = two_pass_read(extractor, _jpeg_bytes(), fields=("nrn", "batch"))
    assert result.agreements["nrn"]["agreement"] == 1.0
    assert result.agreements["batch"]["agreement"] == 1.0
    assert result.disagreements == []


def test_two_pass_read_flags_disagreement():
    pass1 = ExtractionResult(
        nrn="A4-100160", batch="BN2024",
        boxes={"nrn": [0.1, 0.1, 0.4, 0.2], "batch": [0.1, 0.3, 0.4, 0.4]},
    )
    extractor = _StubExtractor(pass1, {"nrn": "B9-9999", "batch": "BN2024"})
    result = two_pass_read(extractor, _jpeg_bytes(), fields=("nrn", "batch"))
    assert result.disagreements == ["nrn"]
    assert result.agreements["nrn"]["agreement"] < 0.6


def test_two_pass_read_marks_no_box():
    pass1 = ExtractionResult(nrn="A4-100160", boxes={})
    extractor = _StubExtractor(pass1, {})
    result = two_pass_read(extractor, _jpeg_bytes(), fields=("nrn",))
    assert result.agreements["nrn"]["status"] == "no_box"
