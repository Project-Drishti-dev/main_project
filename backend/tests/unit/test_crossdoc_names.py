"""`normalise_name` keys: casing, diacritics, digraphs and whitespace.

16.3 names two spellings and one behaviour; the rest of the surface is pinned
here so a later change to it is a decision rather than a drift.  D127.
"""

import unicodedata

import pytest

from app.pipeline.crossdoc import names as names_module
from app.pipeline.crossdoc.names import normalise_name
from app.pipeline.tier0.td3 import MrzValueError


def test_muller_and_uc_muller_produce_the_same_key():
    assert normalise_name("Müller") == normalise_name("MÜLLER") == "MULLER"


@pytest.mark.parametrize(
    "printed",
    ["müller", "Müller", "MÜLLER", "mÜlLeR"],
)
def test_casing_is_upper(printed):
    assert normalise_name(printed) == "MULLER"


def test_a_decomposed_spelling_gives_the_same_key_as_a_precomposed_one():
    decomposed = unicodedata.normalize("NFD", "Müller")

    assert len(decomposed) > len("Müller")
    assert normalise_name(decomposed) == normalise_name("Müller")


def test_a_digraph_is_left_exactly_as_it_was_printed():
    assert normalise_name("Mueller") == "MUELLER"
    assert normalise_name("Muller") == "MULLER"
    assert normalise_name("Mueller") != normalise_name("Müller")


@pytest.mark.parametrize(
    "printed",
    ["Müller  Müller", "Müller\t\tMüller", "Müller\nMüller", "Müller \t\n Müller"],
)
def test_a_run_of_whitespace_collapses_to_one_space(printed):
    assert normalise_name(printed) == "MULLER MULLER"


@pytest.mark.parametrize(
    ("printed", "expected"),
    [("  Müller  ", "MULLER"), ("\tMüller\n", "MULLER")],
)
def test_whitespace_at_either_end_is_stripped(printed, expected):
    assert normalise_name(printed) == expected


@pytest.mark.parametrize(
    ("printed", "expected"),
    [("ø", "O"), ("Łukasz", "LUKASZ"), ("Đorđe", "DORDE"), ("Ø", "O")],
)
def test_a_character_unicode_will_not_decompose_is_transliterated(
    printed, expected
):
    assert normalise_name(printed) == expected


def test_the_sharp_s_reaches_the_key_as_two_letters():
    assert normalise_name("weiß") == "WEISS"


def test_a_character_outside_the_map_is_carried_through_unchanged():
    assert normalise_name("æther") == "ÆTHER"


@pytest.mark.parametrize("printed", ["", " ", "\t\n"])
def test_a_name_with_nothing_in_it_keys_to_the_empty_string(printed):
    assert normalise_name(printed) == ""


@pytest.mark.parametrize(
    "printed", ["Müller", "Đorđe", "weiß", "æther", "Müller  Müller"]
)
def test_normalising_a_key_changes_nothing_about_it(printed):
    once = normalise_name(printed)

    assert normalise_name(once) == once


@pytest.mark.parametrize("not_a_name", [None, 42, b"MVller", ["Muller"]])
def test_something_that_is_not_a_string_is_refused(not_a_name):
    with pytest.raises(MrzValueError):
        normalise_name(not_a_name)


def test_a_refusal_names_the_type_it_was_given_and_not_the_name():
    with pytest.raises(MrzValueError) as caught:
        normalise_name(None)

    assert "NoneType" in str(caught.value)


def test_a_refusal_never_prints_the_name_it_was_holding():
    with pytest.raises(MrzValueError) as caught:
        normalise_name(["Müller"])

    assert "Müller" not in str(caught.value)


def test_a_refusal_is_a_value_error():
    assert issubclass(MrzValueError, ValueError)


def test_the_module_exports_only_the_key():
    assert "normalise_name" in names_module.__all__
