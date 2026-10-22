"""17.3 -- `verify_summary`: every token a summary carries, held to the flags.

A token passes when the text printed in the flag data contains it, and a
failure names the tokens that are missing rather than raising.  The cases below
keep the three questions apart, so a name cannot settle a number and a number
cannot settle a date.
"""

import dataclasses

import pytest

from app import explain
from app.explain import verifier
from app.risk import flag_ids
from app.risk.flags import EvidenceFlag

verify_summary = verifier.verify_summary

#: One flag as the pipeline already prints it: `screening.py` stores
#: `dataclasses.asdict`, so this is the shape a caller hands over unchanged.
FLAG_DATA = [
    {
        "id": "DATE_EXPIRED",
        "tier": 0,
        "label": "Date of expiry is in the past",
        "weight_band": "high",
        "value": 0.87,
        "confidence": 0.91,
        "region": None,
        "expected": "2024-11-02",
        "found": "2023-11-02",
        "reason": "The printed expiry is before the reference date.",
        "source_module": "app.pipeline.tier0.dates",
        "field": "date_of_expiry",
    }
]

#: Prose naming only what the flag above prints -- its id, its date and its
#: value.  Its numbers are the date's own three parts beside the value, so a
#: pass also holds that a printed date settles the digits written inside it.
SUMMARY = "DATE_EXPIRED fired on 2024-11-02 with a value of 0.87."

#: A sentence carrying nothing the verifier can hold to anything, so the three
#: extractors answer no tokens at all and the verdict is about the data.
BARE = "The document was tampered with."


def _flag(**overrides):
    """The flag :data:`FLAG_DATA` prints, as an :class:`EvidenceFlag`."""
    fields = dict(FLAG_DATA[0])
    fields.update(overrides)
    return EvidenceFlag(**fields)


def test_a_summary_naming_only_what_the_flags_print_passes():
    passed, offending = verify_summary(SUMMARY, FLAG_DATA)
    assert passed is True
    assert offending == ()


def test_the_answer_is_a_pass_fail_pair_beside_a_tuple_of_tokens():
    answer = verify_summary(SUMMARY, FLAG_DATA)
    assert isinstance(answer, tuple)
    assert len(answer) == 2
    assert isinstance(answer[0], bool)
    assert isinstance(answer[1], tuple)
    assert all(isinstance(token, str) for token in answer[1])


def test_a_number_the_flags_never_printed_is_offending():
    passed, offending = verify_summary("The measured score was 0.42.", FLAG_DATA)
    assert passed is False
    assert offending == ("0.42",)


def test_a_date_the_flags_never_printed_is_offending():
    passed, offending = verify_summary("It expired on 2029-01-05.", FLAG_DATA)
    assert passed is False
    assert "2029-01-05" in offending


def test_a_date_the_flags_print_settles_the_numbers_written_inside_it():
    assert verify_summary("It expired on 2024-11-02.", FLAG_DATA) == (True, ())


def test_a_missing_date_offends_the_numbers_written_inside_it_as_well():
    _, offending = verify_summary("It expired on 2029-01-05.", FLAG_DATA)
    assert set(offending) == {"2029", "01", "05", "2029-01-05"}


def test_a_field_name_the_flags_never_named_is_offending():
    passed, offending = verify_summary(
        "The field DocumentNumber did not match.", FLAG_DATA
    )
    assert passed is False
    assert offending == ("DocumentNumber",)


def test_a_token_is_matched_by_its_own_characters_and_not_by_the_value_it_stands_for():
    passed, offending = verify_summary("A value of 0.870 is on record.", FLAG_DATA)
    assert passed is False
    assert offending == ("0.870",)


def test_offending_tokens_come_in_the_order_the_summary_writes_them():
    passed, offending = verify_summary(
        "The value 0.42 and the name DocumentNumber and the date 2029-01-05.",
        FLAG_DATA,
    )
    assert passed is False
    # "2029" and "2029-01-05" start together, and the number is asked before
    # the date, so the tie resolves towards the number.
    assert offending == ("0.42", "DocumentNumber", "2029", "2029-01-05", "01", "05")


def test_an_unsupported_token_repeated_is_still_one_offender():
    _, offending = verify_summary("0.42, then 0.42, and 0.42 again.", FLAG_DATA)
    assert offending == ("0.42",)


def test_a_supported_token_repeated_never_becomes_an_offender():
    assert verify_summary("0.87, 0.87 and 2024-11-02.", FLAG_DATA) == (True, ())


@pytest.mark.parametrize("flag_id", flag_ids.ALL_FLAG_IDS)
def test_a_flag_id_named_in_a_summary_passes_against_a_flag_carrying_it(flag_id):
    assert verify_summary("the rule {0} fired".format(flag_id), [{"id": flag_id}]) == (
        True,
        (),
    )


# --- 17.4: the refusal side, written against the two claims a summary can
# make that the flag data does not support -- a number, and a flag id. ---


#: Every id except the one :data:`FLAG_DATA` carries, so each is refused once
#: against flag data that provably does not hold it.
OTHER_FLAG_IDS = tuple(f for f in flag_ids.ALL_FLAG_IDS if f != FLAG_DATA[0]["id"])


def test_a_confidence_the_flags_never_printed_is_rejected():
    passed, offending = verify_summary("The confidence was 0.98.", FLAG_DATA)
    assert passed is False
    assert offending == ("0.98",)


@pytest.mark.parametrize("flag_id", OTHER_FLAG_IDS)
def test_a_flag_id_the_flag_data_does_not_carry_is_rejected(flag_id):
    passed, offending = verify_summary("the rule {0} fired".format(flag_id), FLAG_DATA)
    assert passed is False
    assert offending == (flag_id,)


def test_both_unsupported_tokens_are_named_rather_than_only_the_first():
    passed, offending = verify_summary(
        "FACE_MISMATCH fired with a confidence of 0.98.", FLAG_DATA
    )
    assert passed is False
    assert offending == ("FACE_MISMATCH", "0.98")


def test_a_mapping_key_is_searched_as_well_as_its_leaves():
    assert verify_summary("The Iso8601 rule fired.", {"Iso8601": 0.87}) == (True, ())


def test_nested_flag_data_is_searched_through_to_the_leaves():
    payload = {"band": "high", "flags": [{"contributions": [{"value": 0.42}]}]}
    assert verify_summary("The contribution was 0.42.", payload) == (True, ())


def test_a_flag_is_searched_whether_or_not_it_was_converted_first():
    flag = _flag()
    assert verify_summary(SUMMARY, [flag]) == (True, ())
    assert verify_summary(SUMMARY, [flag]) == verify_summary(
        SUMMARY, [dataclasses.asdict(flag)]
    )


def test_flag_data_holding_nothing_offends_every_token_the_summary_carries():
    passed, offending = verify_summary(SUMMARY, [])
    assert passed is False
    assert set(offending) == {
        "2024",
        "11",
        "02",
        "0.87",
        "2024-11-02",
        "DATE_EXPIRED",
    }


def test_a_summary_carrying_no_token_passes_against_any_flag_data():
    assert verify_summary(BARE, []) == (True, ())
    assert verify_summary(BARE, FLAG_DATA) == (True, ())


def test_the_package_re_exports_nothing_so_there_is_one_import_path():
    assert not hasattr(explain, "verify_summary")
