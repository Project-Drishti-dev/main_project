"""17.2 -- `extract_dates` and `extract_field_names`: what a summary names.

A date is one of the two spellings the flag data prints, and a field name is an
id the registry knows or a capitalised word shaped like an identifier rather
than the first word of a sentence.  The id cases read ``ALL_FLAG_IDS`` instead
of writing an id out, so an id added tomorrow is held by the same assertion.
"""

import pytest

from app import explain
from app.explain import verifier
from app.risk import flag_ids

extract_dates = verifier.extract_dates
extract_field_names = verifier.extract_field_names

#: Prose of the shape 17.5's fallback writes: two dates and a flag id, beside
#: ordinary sentence capitals that name nothing.
SUMMARY = (
    "DATE_EXPIRED fired: the document expired on 2024-11-02, was valid until "
    "03/12/2026, and its expiry date reads 02/11/2024."
)

#: A name is a word that carries a second signal -- an acronym, a compound, a
#: digit -- so "The" and "A" are words and the extractor leaves them alone.
NAMES = "The MRZ_DOB_CHECK_DIGIT_MISMATCH on DocumentNumber, then MRZ again: MRZ"


def test_the_dates_in_a_summary_are_found():
    assert extract_dates(SUMMARY) == ("2024-11-02", "03/12/2026", "02/11/2024")


def test_the_two_spellings_are_ISO_and_slashes():
    assert extract_dates("1990-03-12") == ("1990-03-12",)
    assert extract_dates("12/04/2027") == ("12/04/2027",)
    assert extract_dates("12/04/27") == ("12/04/27",)


def test_a_date_stands_alone_and_a_timestamp_is_not_one():
    assert extract_dates("2024-01-15T10:30:00Z") == ()
    assert extract_dates("sha256") == ()
    assert extract_dates("256") == ()


def test_no_word_character_sits_directly_beside_a_date():
    assert extract_dates("issued2024-11-02") == ()
    assert extract_dates("2024-11-02Z") == ()
    assert extract_dates("issued 2024-11-02") == ("2024-11-02",)


def test_a_date_is_kept_as_written_and_its_parts_are_not_checked():
    assert extract_dates("2024-99-99") == ("2024-99-99",)


def test_dates_come_in_the_order_written_and_a_repeat_is_kept():
    assert extract_dates("2024-11-02 then 1990-03-12 then 2024-11-02") == (
        "2024-11-02",
        "1990-03-12",
        "2024-11-02",
    )


def test_prose_carrying_no_date_answers_an_empty_tuple():
    assert extract_dates("The document was tampered with.") == ()
    assert extract_dates("") == ()


def test_a_date_answer_is_a_tuple_of_strings():
    answer = extract_dates("2024-11-02")
    assert isinstance(answer, tuple)
    assert all(isinstance(token, str) for token in answer)


@pytest.mark.parametrize("flag_id", flag_ids.ALL_FLAG_IDS)
def test_every_known_flag_id_is_found_without_a_name_written_out(flag_id):
    assert extract_field_names("the rule {0} fired".format(flag_id)) == (flag_id,)


def test_the_names_in_a_summary_are_found():
    assert extract_field_names(NAMES) == (
        "MRZ_DOB_CHECK_DIGIT_MISMATCH",
        "DocumentNumber",
        "MRZ",
        "MRZ",
    )


def test_a_sentence_capital_names_nothing():
    assert extract_field_names("The document was tampered with. I saw A page.") == ()


def test_an_id_inside_a_longer_word_is_not_read_out_of_it():
    assert extract_field_names("MRZ_DOB_CHECK_DIGIT_MISMATCH_EXTRA") == ()


def test_a_digit_bearing_token_names_something():
    assert extract_field_names("Field2 and ISO8601") == ("Field2", "ISO8601")


def test_prose_carrying_no_name_answers_an_empty_tuple():
    assert extract_field_names("The document was tampered with.") == ()
    assert extract_field_names("") == ()


def test_a_name_answer_is_a_tuple_of_strings():
    answer = extract_field_names("MRZ")
    assert isinstance(answer, tuple)
    assert all(isinstance(token, str) for token in answer)


def test_the_package_re_exports_neither_extractor_so_there_is_one_import_path():
    assert not hasattr(explain, "extract_dates")
    assert not hasattr(explain, "extract_field_names")
