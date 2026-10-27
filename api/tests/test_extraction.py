import json

import httpx

from api.app.config import Settings
from api.extraction.mock import MockExtractor
from api.extraction.schemas import ExtractionResult
from api.extraction.vision import VisionExtractor, _parse_json, _validated
from api.extraction.preprocess import preprocess


def test_preprocess_is_noop():
    data = b"\xff\xd8\xff\xe0fakejpeg"
    assert preprocess(data) == data


def test_mock_extractor_returns_canned(tmp_path):
    ext = MockExtractor(Settings())
    result = ext.extract(b"anything", "default")
    assert result.nrn == "A4-0123"
    assert result.product_name == "Paracetamol Tablets 500mg"
    assert result.confidence.nrn > 0.9


def test_mock_extractor_falls_back_to_default(tmp_path):
    ext = MockExtractor(Settings())
    result = ext.extract(b"anything", "does_not_exist.jpg")
    assert result.nrn == "A4-0123"


def test_parse_json_extracts_from_fenced_text():
    assert _parse_json('```json\n{"product_name": "X"}\n```')["product_name"] == "X"
    assert _parse_json("not json at all") is None


def test_validated_accepts_schema():
    parsed = {
        "product_name": "X",
        "nrn": "A4-0123",
        "confidence": {"nrn": 0.9},
        "legibility_notes": ["ok"],
    }
    result = _validated(parsed)
    assert result.product_name == "X"
    assert result.confidence.nrn == 0.9


def test_vision_extractor_hits_openai_compatible_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["Authorization"].startswith("Bearer ")
        body = json.loads(request.content)
        assert body["model"] == "muse-spark-1.3"
        content = body["messages"][0]["content"]
        assert any(part.get("type") == "image_url" for part in content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"product_name": "X", "confidence": {}}'}}]},
        )

    settings = Settings(meta_api_key="test-key")
    transport = httpx.MockTransport(handler)
    ext = VisionExtractor(settings, transport=transport)
    result = ext.extract(b"\xff\xd8fake", "x.jpg")
    assert isinstance(result, ExtractionResult)
    assert result.product_name == "X"


def test_vision_extractor_retries_then_marks_unreadable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    settings = Settings(meta_api_key="test-key")
    ext = VisionExtractor(settings, transport=httpx.MockTransport(handler))
    result = ext.extract(b"\xff\xd8fake", "x.jpg")
    assert result.product_name is None
    assert any("unreadable" in n for n in result.legibility_notes)
