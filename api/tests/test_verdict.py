import datetime as dt

from api.registries.matcher import MatchOutcome, MatchResult
from api.registries.models import (
    LookupOutcome,
    LookupResult,
    RegistryCategory,
    RegistryRecord,
)
from api.verdict.engine import VerdictCode, decide
from api.verdict.safety import is_medical_advice_request, redirect_medical_advice


def _record(status=None, expiry_date=None, product_name="Paracetamol 500mg"):
    return RegistryRecord(
        nrn="A4-0123",
        product_name=product_name,
        manufacturer="Acme Pharma",
        status=status,
        expiry_date=expiry_date,
        source="greenbook",
        source_url="https://greenbook.nafdac.gov.ng",
    )


def _match(outcome, record=None):
    return MatchResult(outcome=outcome, matched_record=record)


def test_consistent_when_match_and_active():
    v = decide(
        LookupResult.found([_record(status="Active")]),
        _match(MatchOutcome.MATCH, _record(status="Active")),
        RegistryCategory.DRUG,
    )
    assert v.code == VerdictCode.CONSISTENT_WITH_REGISTRY
    assert "does not prove authenticity" in v.message
    assert "fake" not in v.message and "counterfeit" not in v.message
    assert v.footer is not None and "pharmacist" in v.footer


def test_not_found_when_searched_not_found():
    v = decide(LookupResult.not_found(), _match(MatchOutcome.UNVERIFIABLE), RegistryCategory.DRUG)
    assert v.code == VerdictCode.NOT_FOUND_IN_REGISTRY


def test_mismatch_verdict():
    v = decide(
        LookupResult.found([_record()]),
        _match(MatchOutcome.MISMATCH, _record()),
        RegistryCategory.DRUG,
    )
    assert v.code == VerdictCode.REGISTRY_MISMATCH
    assert "fake" not in v.message and "counterfeit" not in v.message


def test_expired_or_inactive():
    v = decide(
        LookupResult.found([_record(status="Expired")]),
        _match(MatchOutcome.MATCH, _record(status="Expired")),
        RegistryCategory.DRUG,
    )
    assert v.code == VerdictCode.EXPIRED_OR_INACTIVE


def test_check_incomplete_is_cannot_confirm_not_not_found():
    v = decide(
        LookupResult.incomplete("captcha_detected"),
        _match(MatchOutcome.UNVERIFIABLE),
        RegistryCategory.DRUG,
    )
    assert v.code == VerdictCode.CANNOT_CONFIRM
    assert v.abstained


def test_ambiguous_abstains():
    v = decide(
        LookupResult.found([_record(), _record(product_name="Cough Syrup")]),
        _match(MatchOutcome.AMBIGUOUS),
        RegistryCategory.DRUG,
    )
    assert v.code == VerdictCode.CANNOT_CONFIRM
    assert v.abstained


def test_food_has_no_medicines_footer():
    v = decide(
        LookupResult.found([_record(status="Active")]),
        _match(MatchOutcome.MATCH, _record(status="Active")),
        RegistryCategory.FOOD,
    )
    assert v.footer is None


def test_medical_advice_detected():
    assert is_medical_advice_request("can I still take it?")
    assert is_medical_advice_request("should I stop taking my pills")
    assert is_medical_advice_request("what is the dosage")
    assert not is_medical_advice_request("is this product registered")


def test_redirect_never_gives_dose_advice():
    text = redirect_medical_advice()
    assert "pharmacist" in text
    assert "take" not in text.lower() or "whether to take" in text.lower()
    for word in ["mg", "dose", "milligrams"]:
        assert word not in text.lower()
