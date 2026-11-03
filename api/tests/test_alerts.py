"""Tests for the NAFDAC public-alert registry (Evidence-First).

The seed data in api/registries/alert_seed.json is real: each alert carries its source_url
and date. These tests replay the Postinor-2 and BPPL alerts and assert the deterministic
ALERT_MATCH / KNOWN_TARGET outcomes, plus the genuine-reference negative.
"""

from __future__ import annotations

import datetime as dt

from api.app.service import CheckService
from api.extraction.explain import TemplateExplainer
from api.extraction.mock import MockExtractor
from api.registries.alerts import (
    AlertFinding,
    AlertRecord,
    AlertRegistry,
    BatchExample,
    confusable,
    edit_distance,
    get_alert_registry,
    normalize,
)
from api.registries.fake import FakeNapamsClient
from api.registries.greenbook import GreenbookClient
from api.registries.matcher import MatchOutcome, MatchResult
from api.registries.models import LookupResult, RegistryCategory, RegistryRecord
from api.registries.router import RegistryRouter
from api.registries.store import Store
from api.verdict.engine import VerdictCode, decide
from api.app.config import Settings


# --- Normalization and matching primitives ----------------------------------

def test_normalize_strips_spaces_and_hyphens():
    assert normalize("A4-0123") == "A40123"
    assert normalize(" 04 6985 ") == "046985"
    assert normalize(None) == ""


def test_confusable_maps_o_to_zero_i_to_one():
    assert confusable("A4O") == "A40"
    assert confusable("1I") == "11"


def test_edit_distance():
    assert edit_distance("ABC", "ABC") == 0
    assert edit_distance("ABC", "ABD") == 1
    assert edit_distance("ABC", "XYZ") == 3


# --- Registry lookup against the real seed ----------------------------------

def test_seed_loaded():
    reg = get_alert_registry()
    assert len(reg) >= 2


def test_postinor_counterfeit_type1_matches():
    f = get_alert_registry().lookup("04-6985", "T36184B")
    assert f is not None
    assert f.kind == "ALERT_MATCH"
    assert f.alert.alert_no == "027/2025"
    assert f.fuzzy is False


def test_postinor_counterfeit_type2_matches():
    f = get_alert_registry().lookup("04-6985", "332")
    assert f is not None
    assert f.kind == "ALERT_MATCH"


def test_postinor_genuine_reference_does_not_match():
    assert get_alert_registry().lookup("04-6985", "T32458H") is None


def test_postinor_unknown_batch_is_known_target():
    f = get_alert_registry().lookup("04-6985", "T99999X")
    assert f is not None
    assert f.kind == "KNOWN_TARGET"


def test_postinor_no_batch_is_known_target():
    f = get_alert_registry().lookup("04-6985")
    assert f is not None
    assert f.kind == "KNOWN_TARGET"


def test_unrelated_nrn_not_found():
    assert get_alert_registry().lookup("A4-0123", "T36184B") is None


def test_fuzzy_batch_edit_distance_one():
    f = get_alert_registry().lookup("04-6985", "T36184D")  # one character off
    assert f is not None
    assert f.kind == "ALERT_MATCH"
    assert f.fuzzy is True


def test_confusable_batch_o_zero():
    reg = AlertRegistry([
        AlertRecord(
            id="x", alert_no="001/2026", date=None, product="P",
            nrn="A4-0123", counterfeit_examples=(BatchExample(batch="BN0OI"),),
        )
    ])
    f = reg.lookup("A4-0123", "BN001")
    assert f is not None
    assert f.kind == "ALERT_MATCH"
    assert f.fuzzy is True


# --- decide() integration ---------------------------------------------------

def _record(nrn, name):
    return RegistryRecord(nrn=nrn, product_name=name, status="Active", source="greenbook")


def test_decide_alert_match_overrides_not_found():
    # BPPL's NRN is marked fake in the alert, so it is not in the registry.
    lookup = LookupResult.not_found(nrn="02-3457", source="greenbook")
    finding = get_alert_registry().lookup("02-3457", "BP5203")
    verdict = decide(lookup, MatchResult(outcome=MatchOutcome.UNVERIFIABLE), RegistryCategory.DRUG, alert_finding=finding)
    assert verdict.code == VerdictCode.ALERT_MATCH


def test_decide_known_target():
    rec = _record("04-6985", "Postinor 2")
    lookup = LookupResult.found([rec], nrn="04-6985")
    finding = get_alert_registry().lookup("04-6985", "T99999X")
    verdict = decide(lookup, MatchResult(outcome=MatchOutcome.MATCH, matched_record=rec), RegistryCategory.DRUG, alert_finding=finding)
    assert verdict.code == VerdictCode.KNOWN_TARGET


def test_decide_genuine_reference_is_consistent():
    rec = _record("04-6985", "Postinor 2")
    lookup = LookupResult.found([rec], nrn="04-6985")
    finding = get_alert_registry().lookup("04-6985", "T32458H")
    assert finding is None
    verdict = decide(lookup, MatchResult(outcome=MatchOutcome.MATCH, matched_record=rec), RegistryCategory.DRUG, alert_finding=None)
    assert verdict.code == VerdictCode.CONSISTENT_WITH_REGISTRY


# --- Service-level replay (acceptance criteria) -----------------------------

def _service(tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = Store(settings.db_path)
    # Greenbook carries no manufacturer name, only manufacturer_id, so the record
    # leaves manufacturer None (mirrors real data).
    rec = RegistryRecord(
        nrn="04-6985", product_name="Postinor 2", status="Active",
        manufacturer=None, strength=None, source="greenbook",
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
    return service


def test_replay_postinor_counterfeit_returns_alert_match(tmp_path):
    service = _service(tmp_path)
    resp = service.check_fields({
        "nrn": "04-6985", "batch": "T36184B", "product_name": "Postinor 2",
        "category_guess": "drug",
    })
    assert resp.verdict.code == VerdictCode.ALERT_MATCH
    assert resp.alert is not None
    assert resp.alert.kind == "ALERT_MATCH"
    assert resp.alert.alert_no == "027/2025"
    assert resp.alert.source_url is not None
    assert resp.alert.matched_batch == "T36184B"


def test_replay_postinor_counterfeit_type2(tmp_path):
    service = _service(tmp_path)
    resp = service.check_fields({"nrn": "04-6985", "batch": "332", "product_name": "Postinor 2", "category_guess": "drug"})
    assert resp.verdict.code == VerdictCode.ALERT_MATCH


def test_replay_postinor_genuine_reference_not_alert(tmp_path):
    service = _service(tmp_path)
    resp = service.check_fields({"nrn": "04-6985", "batch": "T32458H", "product_name": "Postinor 2", "category_guess": "drug"})
    assert resp.verdict.code != VerdictCode.ALERT_MATCH
    assert resp.alert is None
    assert resp.verdict.code == VerdictCode.CONSISTENT_WITH_REGISTRY


def test_replay_postinor_unknown_batch_is_known_target(tmp_path):
    service = _service(tmp_path)
    resp = service.check_fields({"nrn": "04-6985", "batch": "T99999X", "product_name": "Postinor 2", "category_guess": "drug"})
    assert resp.verdict.code == VerdictCode.KNOWN_TARGET
    assert resp.alert is not None
    assert resp.alert.kind == "KNOWN_TARGET"


# --- Date consistency must NOT flag the Postinor-2 counterfeits -------------

def test_postinor_counterfeit_dates_not_flagged():
    from api.extraction.consistency import check_consistency
    from api.extraction.schemas import ExtractionResult

    date_flags = {"EXPIRY_PAST", "EXPIRY_FAR_FUTURE", "MFG_IN_FUTURE", "SHELF_LIFE_MISMATCH"}
    for batch, mfg, exp in [("T36184B", "08/2024", "08/2028"), ("332", "03/2023", "02/2027")]:
        ext = ExtractionResult(nrn="04-6985", batch=batch, manufacture_date=mfg, expiry_date=exp)
        res = check_consistency(ext)
        assert not (date_flags & set(res.flags)), f"unexpected date flag for {batch}: {res.flags}"
