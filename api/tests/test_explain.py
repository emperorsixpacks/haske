"""Tests for the LLM explanation layer."""

import json

import httpx
import pytest

from api.app.config import Settings
from api.extraction.explain import LLMExplainer, TemplateExplainer, get_explainer


def test_template_explainer_returns_string_for_all_codes():
    exp = TemplateExplainer()
    for code in [
        "CONSISTENT_WITH_REGISTRY",
        "REGISTRY_MISMATCH",
        "NOT_FOUND_IN_REGISTRY",
        "EXPIRED_OR_INACTIVE",
        "ALERT_MATCH",
        "CANNOT_CONFIRM",
    ]:
        result = exp.explain(
            verdict_code=code,
            product_name="Test Product",
            nrn="A4-0123",
            category="drug",
            evidence_note="nrn=A4-0123 product=Test Product",
        )
        assert isinstance(result, str), f"TemplateExplainer returned None for {code}"
        assert len(result) > 0


def test_template_explainer_never_says_fake_or_counterfeit():
    exp = TemplateExplainer()
    for code in TemplateExplainer._MESSAGES:
        text = exp.explain(code, None, None, None, None) or ""
        assert "fake" not in text.lower()
        assert "counterfeit" not in text.lower()


def test_get_explainer_returns_template_in_mock_mode():
    settings = Settings()  # no META_API_KEY -> mock_mode
    exp = get_explainer(settings)
    assert isinstance(exp, TemplateExplainer)


def test_get_explainer_returns_template_even_with_key():
    # Token-frugal default: the explanation is deterministic and never calls the model.
    settings = Settings(meta_api_key="test-key")
    exp = get_explainer(settings)
    assert isinstance(exp, TemplateExplainer)


def test_llm_explainer_calls_chat_completions():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        assert "CONSISTENT_WITH_REGISTRY" in body["messages"][1]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "The label matches the registry."}}]},
        )

    settings = Settings(meta_api_key="test-key")
    exp = LLMExplainer(settings, transport=httpx.MockTransport(handler))
    result = exp.explain(
        verdict_code="CONSISTENT_WITH_REGISTRY",
        product_name="Paracetamol",
        nrn="A4-0123",
        category="drug",
        evidence_note="nrn=A4-0123 product=Paracetamol Tablets",
    )
    assert result == "The label matches the registry."


def test_llm_explainer_returns_none_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    settings = Settings(meta_api_key="test-key")
    exp = LLMExplainer(settings, transport=httpx.MockTransport(handler))
    result = exp.explain("CANNOT_CONFIRM", None, None, None, None)
    assert result is None


def test_service_populates_explanation(tmp_path):
    """End-to-end: service._evaluate fills verdict.explanation from the explainer."""
    import datetime as dt

    from api.app.service import CheckService
    from api.extraction.explain import TemplateExplainer
    from api.extraction.mock import MockExtractor
    from api.registries.fake import FakeNapamsClient
    from api.registries.greenbook import GreenbookClient
    from api.registries.models import RegistryCategory, RegistryRecord
    from api.registries.router import RegistryRouter
    from api.registries.store import Store

    settings = Settings(data_dir=tmp_path)
    store = Store(settings.db_path)
    rec = RegistryRecord(
        nrn="A4-0123",
        product_name="Paracetamol Tablets 500mg",
        manufacturer="Acme Pharma Ltd",
        strength="500mg",
        status="Active",
        source="greenbook",
        source_url="https://greenbook.nafdac.gov.ng",
    )
    sid = store.add_snapshot("greenbook", dt.datetime.now(dt.timezone.utc), 1, "h", "p")
    store.add_records(sid, [rec])

    service = CheckService(
        settings=settings,
        store=store,
        extractor=MockExtractor(settings),
        router=RegistryRouter(greenbook=GreenbookClient(store), napams=FakeNapamsClient({})),
        explainer=TemplateExplainer(),
    )
    resp = service.check_fields(
        {"product_name": "Paracetamol Tablets 500mg", "nrn": "A4-0123", "category_guess": "drug"}
    )
    assert resp.verdict.explanation is not None
    assert len(resp.verdict.explanation) > 0
