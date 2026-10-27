from api.registries.matcher import MatchOutcome, match
from api.registries.models import RegistryRecord


def _record(name="Paracetamol 500mg", manufacturer="Acme Pharma", strength="500mg"):
    return RegistryRecord(
        nrn="A4-0123",
        product_name=name,
        manufacturer=manufacturer,
        strength=strength,
    )


def test_match_when_name_and_manufacturer_agree():
    label = {"product_name": "Paracetamol 500mg", "manufacturer": "Acme Pharma", "strength": "500 mg"}
    result = match(label, [_record()])
    assert result.outcome == MatchOutcome.MATCH


def test_mismatch_when_name_clearly_different():
    label = {"product_name": "Amoxicillin Capsules", "manufacturer": "Acme Pharma", "strength": "250mg"}
    result = match(label, [_record()])
    assert result.outcome == MatchOutcome.MISMATCH


def test_ambiguous_when_nrn_shared_by_distinct_products():
    records = [_record(name="Paracetamol 500mg"), _record(name="Cough Syrup")]
    label = {"product_name": "Paracetamol 500mg", "manufacturer": "Acme Pharma"}
    result = match(label, records)
    assert result.outcome == MatchOutcome.AMBIGUOUS


def test_unverifiable_when_no_label_fields():
    result = match({"product_name": None, "manufacturer": None, "strength": None}, [_record()])
    assert result.outcome == MatchOutcome.UNVERIFIABLE


def test_unverifiable_when_no_records():
    result = match({"product_name": "X"}, [])
    assert result.outcome == MatchOutcome.UNVERIFIABLE


def test_match_is_fuzzy_on_case_and_whitespace():
    label = {"product_name": "  paracetamol 500 mg ", "manufacturer": "ACME pharma"}
    result = match(label, [_record()])
    assert result.outcome == MatchOutcome.MATCH
