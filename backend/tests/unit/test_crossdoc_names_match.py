"""`names_match`: what two printed names are allowed to disagree about.

16.4 names three pairs and their verdicts; the rest of the surface is
pinned here so a later change to it is a decision rather than a drift.
D128.
"""

import dataclasses

import pytest

from app.pipeline.crossdoc import names as names_module
from app.pipeline.crossdoc.names import (
    DEFAULT_TOLERANCE,
    names_match,
    normalise_name,
)
from app.pipeline.tier0.td3 import MrzValueError


def test_the_two_spellings_of_one_digraph_name_match():
    assert names_match("Mueller", "Müller").matched


def test_an_inserted_digraph_matches_the_shorter_spelling():
    assert names_match("Muller", "Mueller").matched


@pytest.mark.parametrize(
    ("printed", "other"),
    [("Mueller", "Müller"), ("Muller", "Mueller"), ("ALPHA", "ALFA")],
)
def test_a_folded_digraph_matches_at_full_similarity(printed, other):
    result = names_match(printed, other)

    assert result.similarity == 1.0
    assert result.differing == ()
    assert result.matched


def test_an_ss_spelling_matches_its_s_spelling():
    assert names_match("HASSAN", "HASAN").matched


def test_a_letter_added_to_a_surname_does_not_match():
    assert not names_match("Rahman", "Rahmani").matched


def test_that_difference_is_measured_at_six_sevenths():
    result = names_match("Rahman", "Rahmani")

    assert result.similarity == pytest.approx(6 / 7)
    assert result.similarity < DEFAULT_TOLERANCE


def test_the_tokens_that_differed_are_named():
    assert names_match("Rahman", "Rahmani").differing == (
        ("RAHMANI", "RAHMAN"),
    )


def test_a_token_with_no_partner_is_named_against_nothing():
    result = names_match("Zeta Omar", "Zeta")

    assert result.similarity == 0.5
    assert result.differing == (("", "OMAR"),)


def test_token_order_is_not_significant():
    assert names_match("Rahman Mohammed", "MOHAMMED RAHMAN").matched


@pytest.mark.parametrize(
    ("printed", "other"),
    [("Smith-Jones", "SMITH JONES"), ("Smith.Jones", "SMITH JONES"),
     ("Smith,Jones", "SMITH JONES")],
)
def test_a_compound_surname_matches_its_parts(printed, other):
    assert names_match(printed, other).similarity == 1.0


def test_an_accented_spelling_matches_its_plain_one():
    assert names_match("Đorđe", "Dorde").similarity == 1.0


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Rahman", "Rahmani"),
        ("Rahman Mohammed", "RAHMAN"),
        ("Mueller", "Müller"),
        ("Zeta Alpha", "Alpha"),
    ],
)
def test_swapping_the_names_answers_alike(a, b):
    assert names_match(a, b) == names_match(b, a)


def test_how_a_name_was_printed_does_not_reach_the_answer():
    assert names_match("Rahman\t Mohammed", "MOHAMMED  Rahman") == names_match(
        "RAHMAN MOHAMMED", "Mohammed Rahman"
    )


def test_a_lower_tolerance_admits_the_spelling_difference():
    assert names_match("Rahman", "Rahmani", 0.8).matched


def test_the_record_remembers_the_tolerance_it_was_asked_for():
    assert names_match("Rahman", "Rahmani", 0.8).tolerance == 0.8


def test_the_digraph_is_folded_in_the_comparison_and_not_in_the_key():
    assert normalise_name("Mueller") == "MUELLER"
    assert normalise_name("Muller") == "MULLER"


@pytest.mark.parametrize("printed", ["", " ", "\t\n"])
@pytest.mark.parametrize("other", ["Rahman", ""])
def test_a_name_with_nothing_in_it_is_refused(printed, other):
    with pytest.raises(MrzValueError):
        names_match(printed, other)


@pytest.mark.parametrize("not_a_name", [None, 42, b"MVller", ["Muller"]])
def test_something_that_is_not_a_string_is_refused(not_a_name):
    with pytest.raises(MrzValueError):
        names_match(not_a_name, "Rahman")


@pytest.mark.parametrize("tolerance", [-0.1, 1.1, 2, -1])
def test_a_tolerance_outside_the_unit_interval_is_refused(tolerance):
    with pytest.raises(MrzValueError):
        names_match("Rahman", "Rahmani", tolerance)


@pytest.mark.parametrize("tolerance", [True, "0.9", None, [0.9], 0.9j])
def test_a_tolerance_that_is_not_a_real_number_is_refused(tolerance):
    with pytest.raises(MrzValueError):
        names_match("Rahman", "Rahmani", tolerance)


@pytest.mark.parametrize("tolerance", [0.0, 0.5, 1, 1.0])
def test_a_tolerance_inside_the_unit_interval_is_accepted(tolerance):
    assert names_match("Rahman", "Rahmani", tolerance).tolerance == tolerance


def test_a_refusal_names_the_type_it_was_given_and_not_the_name():
    with pytest.raises(MrzValueError) as caught:
        names_match(["Müller"], "Rahman")

    assert "list" in str(caught.value)
    assert "Müller" not in str(caught.value)


def test_a_refusal_is_a_value_error():
    assert issubclass(MrzValueError, ValueError)


def test_a_match_cannot_be_edited_after_it_is_answered():
    answered = names_match("Rahman", "Rahmani")

    with pytest.raises(dataclasses.FrozenInstanceError):
        answered.similarity = 1.0


def test_the_module_exports_exactly_three_names():
    assert names_module.__all__ == ["NameMatch", "names_match", "normalise_name"]
