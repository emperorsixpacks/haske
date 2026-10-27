from api.registries.nrn import normalise_nrn


def test_normalise_dash_letter_prefix():
    n = normalise_nrn("A4-0123")
    assert n.canonical == "A4-0123"
    assert n.valid


def test_normalise_plain_digits():
    n = normalise_nrn("04-5808")
    assert n.canonical == "04-5808"
    assert n.valid


def test_normalise_case_and_spaces():
    n = normalise_nrn("  a4 0123 ")
    assert n.canonical == "A4-0123"


def test_normalise_no_dash():
    n = normalise_nrn("045808")
    assert n.canonical == "04-5808"


def test_reject_barcode():
    n = normalise_nrn("6157000001234")
    assert n.is_barcode
    assert not n.valid
    assert n.error == "looks_like_barcode"


def test_flag_o_zero_ambiguity_not_guess():
    n = normalise_nrn("A4-O123")
    assert n.ambiguous_o_zero
    # We still normalise, but the flag is set so callers can be cautious.
    assert n.canonical == "A4-0123"


def test_empty_rejected():
    assert not normalise_nrn("").valid
    assert not normalise_nrn(None).valid
    assert not normalise_nrn("   ").valid


def test_unrecognised_rejected():
    n = normalise_nrn("not an nrn at all!!")
    assert not n.valid
    assert n.error == "unrecognised_format"
