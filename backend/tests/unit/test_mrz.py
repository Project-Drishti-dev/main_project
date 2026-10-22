import ast
import calendar
import dataclasses
import datetime
import importlib
import inspect
import pathlib
import string

import pytest

from app.pipeline.tier0 import mrz


@pytest.mark.parametrize("value", range(10))
def test_digits_map_to_their_own_value(value):
    char = string.digits[value]

    assert mrz.char_value(char) == value


@pytest.mark.parametrize("offset", range(26))
def test_uppercase_letters_map_to_ten_plus_alphabetical_index(offset):
    char = string.ascii_uppercase[offset]

    assert mrz.char_value(char) == 10 + offset


def test_the_two_ranges_are_contiguous_and_endpoints_are_pinned():
    assert mrz.char_value("0") == 0
    assert mrz.char_value("9") == 9
    assert mrz.char_value("A") == 10
    assert mrz.char_value("Z") == 35


def test_filler_maps_to_zero():
    assert mrz.char_value("<") == 0


def test_filler_is_the_table_entry_and_documented_as_such():
    assert mrz.FILLER == "<"
    assert mrz.CHAR_VALUES[mrz.FILLER] == 0


def test_filler_shares_its_value_with_the_digit_zero():
    assert mrz.char_value("<") == mrz.char_value("0")


def test_table_holds_exactly_the_thirty_seven_mrz_characters():
    assert set(mrz.CHAR_VALUES) == set(string.digits) | set(string.ascii_uppercase) | {"<"}
    assert len(mrz.CHAR_VALUES) == 37


@pytest.mark.parametrize(
    ("label", "char"),
    [
        ("a space", " "),
        # Circled digit one: looks like a number, is not an MRZ digit.
        ("a digit-like symbol", "\u2460"),
        ("a lowercase letter", "z"),
    ],
)
def test_any_other_character_raises_mrz_value_error(label, char):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        mrz.char_value(char)

    assert repr(char) in str(excinfo.value)


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, []),
        (1, [7]),
        (4, [7, 3, 1, 7]),
        # 39 is 13 whole cycles, so it ends exactly on the cycle boundary.
        (39, [7, 3, 1] * 13),
    ],
)
def test_weights_returns_the_cycle_truncated_to_n(n, expected):
    assert mrz.weights(n) == expected


@pytest.mark.parametrize("n", range(0, 46))
def test_weights_is_the_cycle_prefix_of_exactly_n_items(n):
    result = mrz.weights(n)

    assert len(result) == n
    assert set(result) <= set(mrz.WEIGHT_CYCLE)
    assert result == [mrz.WEIGHT_CYCLE[i % len(mrz.WEIGHT_CYCLE)] for i in range(n)]


def test_weights_rejects_a_negative_length():
    with pytest.raises(mrz.MrzValueError) as excinfo:
        mrz.weights(-1)

    assert repr(-1) in str(excinfo.value)


# The first three rows are the known answers: the field values of the specimen
# machine-readable passport line published with ICAO Doc 9303, whose check
# digits are 3, 2 and 9 in the line itself --
# "L898902C<3UTO7408122F1204159..." -- so the expected values here come from
# the standard, not from this implementation.
#
#   "L898902C<"  document number  21*7 8*3 9*1 8*7 9*3 0*1 2*7 12*3 0*1
#                              = 147+24+9+56+27+0+14+36+0 = 313  -> 3
#   "740812"     date of birth   7*7 4*3 0*1 8*7 1*3 2*1
#                              = 49+12+0+56+3+2         = 122  -> 2
#   "120415"     date of expiry  1*7 2*3 0*1 4*7 1*3 5*1
#                              = 7+6+0+28+3+5           = 49   -> 9
#
# The remaining rows are hand-derived discriminators.  They exist because the
# specimen fields cannot catch every plausible mistake on their own: "D" is one
# character, so a cycle that started at 1 or 3 instead of 7 would still pass the
# three specimen rows, and "AB12345" is 7 characters, so padding the cycle
# rather than truncating it -- "L898902C<" and "740812" are 8 and 6, both
# multiples of three -- would also still pass.  "L898902C3" shares eight
# characters with the document-number field, so a one-character slip in the
# value or weight table shows up as a mismatch instead of a coincidence.
@pytest.mark.parametrize(
    ("text", "total", "expected"),
    [
        ("L898902C<", 313, 3),
        ("740812", 122, 2),
        ("120415", 49, 9),
        ("L898902C3", 316, 6),
        ("AB12345", 166, 6),
        ("D", 91, 1),
    ],
)
def test_check_digit_matches_the_known_answer(text, total, expected):
    # ``total`` is the sum of products the standard's rule produces, so
    # asserting on it as well means a later edit cannot quietly change the
    # intermediate arithmetic and leave the final digit coincidentally right.
    assert mrz.check_digit(text) == expected == total % 10


def test_check_digit_rejects_a_character_outside_the_mrz_table():
    with pytest.raises(mrz.MrzValueError) as excinfo:
        mrz.check_digit("L898902C3 ")

    assert repr(" ") in str(excinfo.value)


@pytest.mark.parametrize(
    "field",
    [None, 42, b"L898902C3", 7.5],
    ids=["none", "int", "bytes", "float"],
)
def test_check_digit_rejects_a_field_that_is_not_mrz_text(field):
    # Only bytes has a length, so it gets past the type guard and fails one
    # character at a time; None, int and float have no length at all.  Either
    # way no digit comes back.
    with pytest.raises(mrz.MrzValueError):
        mrz.check_digit(field)


@pytest.mark.parametrize("field", [None, 42], ids=["none", "int"])
def test_check_digit_names_the_field_it_could_not_read(field):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        mrz.check_digit(field)

    assert repr(field) in str(excinfo.value)


# --- Edge cases: fields where every character carries the same value -------
#
# The four cases 1.7 asks for -- the empty field, and fields made only of
# zeros, only of filler, or only of "A" -- all answer 0, but they answer it for
# three different reasons, so they fail differently:
#
#   ""      no products at all, so the sum is the empty sum 0
#   "0..."  digit 0 has value 0, so every product is 0 whatever the weight
#   "<..."  the filler also has value 0 (1.3), so a filler-padded field is
#           arithmetically indistinguishable from a field of zeros -- which is
#           what an unfilled optional field looks like on a real MRZ line
#   "A..."  "A" has value 10, so the sum is 10 * (sum of the weights).  A
#           whole 7,3,1 cycle sums to 11, giving 110 per cycle, but the claim
#           is stronger than that: 10 * anything is a multiple of ten, so this
#           is 0 for *any* weight sequence whatsoever.
#
# That last point is also the limit of these rows.  Because 10 collapses the
# last digit, the "A" rows cannot tell a correct 7,3,1 cycle from a padded
# one, from one starting at 1 or 3, or from no weights at all -- so the totals
# are pinned alongside the digits, and 1.6's known-answer table stays the test
# that pins the cycle order.  What these rows are for is the other class of
# mistake: a degenerate-looking field that gets refused, short-circuited, or
# silently shortened instead of summed.
@pytest.mark.parametrize(
    ("label", "text", "total", "expected"),
    [
        # The empty sum.  A field with nothing in it is still a field.
        ("the empty field", "", 0, 0),
        ("a lone zero", "0", 0, 0),
        ("a zero-padded field", "0" * 9, 0, 0),
        # An optional field the traveller never filled in arrives as filler.
        ("a lone filler", mrz.FILLER, 0, 0),
        ("a filler-padded field", mrz.FILLER * 9, 0, 0),
        # 10*7, then 10*(7+3+1)*3 = 330, then 10*11*13 = 1430 for 39 chars.
        ("a lone A", "A", 70, 0),
        ("three whole A cycles", "A" * 9, 330, 0),
        ("thirteen whole A cycles", "A" * 39, 1430, 0),
    ],
)
def test_check_digit_of_a_field_that_repeats_one_value(label, text, total, expected):
    assert mrz.check_digit(text) == expected == total % 10


def test_the_empty_field_returns_a_digit_without_reaching_for_a_character():
    # Nothing to validate and nothing to weight, so neither char_value nor a
    # table lookup is consulted: an empty field is a legal field, not a gap
    # that has to be refused.
    assert mrz.weights(0) == []
    assert mrz.check_digit("") == 0


def test_a_zero_valued_field_is_zero_without_depending_on_the_weights():
    # Pinned apart from the table because it is the one claim the table cannot
    # make for itself: a zero-valued field is 0 for *every* cycle and *every*
    # length, so it would pass just as happily against a broken weight
    # function.  That makes this a guard on the call path, not on the
    # arithmetic.
    assert mrz.char_value("0") == 0
    assert mrz.char_value(mrz.FILLER) == 0
    assert mrz.check_digit("0" * 39) == 0
    assert mrz.check_digit(mrz.FILLER * 39) == 0


# Zero and filler share a value, so they must share a digit at every length,
# and "A" is a multiple of ten, so it is 0 at every length too.  Lengths 0 to
# 12 cover every phase of the 7,3,1 cycle and four whole cycles over it.
@pytest.mark.parametrize("char", ["0", "<", "A"], ids=["zero", "filler", "A"])
@pytest.mark.parametrize("length", range(0, 13))
def test_a_field_of_identical_characters_checks_to_zero_at_every_length(char, length):
    value = mrz.char_value(char)
    # 0 and the filler make every product zero; "A" makes every product a
    # multiple of ten.  Either way the digit is 0, whatever the weights are.
    assert value in (0, 10)
    assert (value * sum(mrz.weights(length))) % 10 == 0
    assert mrz.check_digit(char * length) == 0


@pytest.mark.parametrize("length", range(0, 13))
def test_zero_and_filler_are_indistinguishable_to_the_check_digit(length):
    # The shared value in the table is what makes them the same, not a
    # coincidence in the arithmetic: if the filler's value ever moved, so
    # would this.
    assert mrz.check_digit("0" * length) == mrz.check_digit(mrz.FILLER * length)


# --- verify_check_digit: a mismatch is a finding, not an exception ---------
#
# A failed check digit is the one result this package exists to produce.  The
# abstract's worked example A is a date-of-birth check digit that does not
# match, and 6.7 has to turn that into a flag carrying "expected 4, found 7"
# and exit to High Risk.  So a mismatch has to come back as a value the caller
# can test and then explain -- if it arrived as an exception instead, every
# call site would have to catch it, and the ordinary "this field is fine" path
# would be the one that had to be protected against a crash.
#
# The match rows below reuse 1.6's known answers, which for the three specimen
# fields are digits printed in the ICAO specimen line itself rather than values
# this implementation produced.  That matters here more than anywhere else:
# a verify function tested only against its own arithmetic agrees with itself
# perfectly, so a test that could not tell a correct implementation from a
# consistently wrong one would be worthless.


def _field_of_length(length):
    """Return MRZ text of exactly ``length`` characters, for the sweep below."""
    alphabet = string.digits + string.ascii_uppercase + mrz.FILLER
    return (alphabet * 2)[:length]


@pytest.mark.parametrize(
    ("text", "printed"),
    [
        ("L898902C<", 3),
        ("740812", 2),
        ("120415", 9),
    ],
)
def test_verify_check_digit_accepts_the_digit_printed_in_the_specimen(text, printed):
    assert mrz.verify_check_digit(text, printed) is True


@pytest.mark.parametrize("wrong", [digit for digit in range(10) if digit != 2])
def test_a_dob_mismatch_answers_false_rather_than_raising(wrong):
    # The task's "does not raise" clause, stated as the property it protects:
    # every one of the nine wrong digits on a real specimen field is answered
    # with a boolean.  Not one of them may be an exception.
    assert mrz.verify_check_digit("740812", wrong) is False


def test_the_abstracts_worked_example_is_a_false_not_an_exception():
    # abstract.txt worked example A: a DOB check digit expected as 4 where 7
    # is found.  The specimen's own digit for this field is 2, so any value
    # other than 2 is the mismatch, and the found digit stays recoverable.
    assert mrz.verify_check_digit("740812", 4) is False
    assert mrz.verify_check_digit("740812", 7) is False
    assert mrz.check_digit("740812") == 2


def test_the_answer_is_a_real_bool_and_not_a_truthy_value():
    # The signature promises bool, and 6.2 stores the result on the document.
    # A truthy 1 or a non-empty string would survive an ``if`` and then be
    # serialised into a screening record as something it is not.
    assert type(mrz.verify_check_digit("740812", 2)) is bool
    assert type(mrz.verify_check_digit("740812", 4)) is bool


def test_the_printed_digit_may_be_the_character_it_appears_as_in_the_line():
    # A parser slices the check digit out of the line as one character, so it
    # arrives as "2", not 2.  Both spellings must mean the same thing, and the
    # filler must not be accepted as a stand-in for a digit: "<" is what an
    # unfilled optional field carries, not what a check digit can be.
    assert mrz.verify_check_digit("740812", "2") is True
    assert mrz.verify_check_digit("740812", "4") is False
    with pytest.raises(mrz.MrzValueError):
        mrz.verify_check_digit("740812", mrz.FILLER)


@pytest.mark.parametrize(
    "expected",
    [None, 10, -1, "", "22", "two", "A", 2.0, True],
    ids=["none", "ten", "negative", "empty", "two-characters", "word", "letter", "float", "bool"],
)
def test_an_expected_that_is_not_a_digit_raises(expected):
    # 2.0 and True both compare equal to 2 in Python, so without a type check
    # they would quietly pass as the digit 2 and hide a parsing bug at the call
    # site instead of naming it here.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        mrz.verify_check_digit("740812", expected)

    assert repr(expected) in str(excinfo.value)


@pytest.mark.parametrize(
    "field",
    [None, 42, b"740812", 7.5],
    ids=["none", "int", "bytes", "float"],
)
def test_a_field_that_cannot_be_read_raises_rather_than_answering_false(field):
    # The deliberate limit of "does not raise": a field that is not readable as
    # MRZ raises, because a field nobody could read is not evidence of
    # tampering.  Answering False would report a mis-OCR'd or truncated field
    # to an officer as a forged-document check-digit failure.
    with pytest.raises(mrz.MrzValueError):
        mrz.verify_check_digit(field, 2)


@pytest.mark.parametrize("char", [" ", "z", "\u2460"])
def test_a_field_with_a_character_outside_the_table_raises(char):
    with pytest.raises(mrz.MrzValueError):
        mrz.verify_check_digit("74081" + char, 2)


@pytest.mark.parametrize("length", range(0, 46))
def test_verify_check_digit_answers_for_every_length_and_every_digit(length):
    # The totality claim: over MRZ text there is no length and no claimed digit
    # for which this raises.  Lengths 0 to 45 cover the empty field, every
    # phase of the 7,3,1 cycle, the 36-character TD3 line, and the 39-
    # character composite, and the three fields per length put a 37-character
    # alphabet, the specimen document number, and filler through all of them.
    for field in (
        _field_of_length(length),
        ("L898902C<" * 5)[:length],
        (mrz.FILLER * 45)[:length],
    ):
        for digit in range(10):
            assert mrz.verify_check_digit(field, digit) is (
                mrz.check_digit(field) == digit
            )


def test_verify_check_digit_is_exported():
    assert "verify_check_digit" in mrz.__all__


# --- check_digit_results: the same answer, kept instead of spent ------------
#
# `verify_check_digit` throws the computed digit away and answers a bool.  That
# is right for one field the caller has already isolated and wrong for a
# document, where the flag schema wants "expected 4, found 7" and the layout
# module wants to hand over a list without doing arithmetic.  So the list keeps
# both halves -- and parts company with `verify_check_digit` in exactly one
# place, which is the whole reason these tests exist.

SPECIMEN_FIELDS = [
    ("document_number", "L898902C<", "3"),
    ("date_of_birth", "740812", "2"),
    ("date_of_expiry", "120415", "9"),
    ("optional_data", "ZE184226B<<<<<", "1"),
]


def test_check_digit_results_agrees_with_verify_check_digit_field_by_field():
    # The strongest available claim that the two cannot drift: over the three
    # specimen fields and all ten digits each, the list says exactly what the
    # single-field function says.  A re-implementation inside the list rather
    # than a call would have to agree 30 times to pass, which is why the
    # comparison is the test rather than a matching of known answers.
    for name, text, printed in SPECIMEN_FIELDS:
        for digit in range(10):
            result = mrz.check_digit_results([(name, text, digit)])[0]

            assert result.field == name
            assert result.expected == digit
            assert result.found == mrz.check_digit(text)
            assert result.passed is mrz.verify_check_digit(text, digit), (name, digit)


def test_check_digit_results_returns_one_row_per_field_in_the_order_given():
    # Order is the caller's, not this function's: it has no opinion about which
    # fields a document format prints, and a caller that listed its fields in
    # printed order must get its rows back that way rather than sorted or
    # grouped by outcome.
    fields = [(name, text, printed) for name, text, printed in reversed(SPECIMEN_FIELDS)]
    results = mrz.check_digit_results(fields)

    assert isinstance(results, tuple)
    assert len(results) == len(SPECIMEN_FIELDS)
    assert [result.field for result in results] == [name for name, _, _ in fields]
    assert all(result.passed is True for result in results)


def test_check_digit_results_accepts_a_generator_and_an_empty_list():
    # A generator, because a caller walking a layout table is the ordinary
    # case; and nothing at all, because a format that prints no check digits is
    # not an error here -- it is a format with none.
    assert len(mrz.check_digit_results(iter(SPECIMEN_FIELDS))) == 4
    assert mrz.check_digit_results([]) == ()


def test_an_unreadable_field_is_reported_rather_than_raising():
    # **The one place this function parts company with
    # `verify_check_digit`, and the difference is the point.**  That function
    # raises, and rightly, for a field a caller has already isolated.  A list
    # cannot: one garbled character among five is the ordinary condition of an
    # OCR'd line, and a list that refused to be built would take the other four
    # verdicts with it.  So the unreadable half is `None` and the verdict is a
    # third answer -- and the readable half is still reported, because that is
    # what a flag needs.
    with pytest.raises(mrz.MrzValueError):
        mrz.verify_check_digit("74 812", 2)

    results = mrz.check_digit_results(
        [("date_of_birth", "74 812", 2), ("date_of_expiry", "120415", "9")]
    )
    unreadable, readable = results

    assert unreadable.field == "date_of_birth"
    assert unreadable.found is None
    assert unreadable.expected == 2
    assert unreadable.readable is False
    assert unreadable.passed is None
    assert (readable.expected, readable.found, readable.passed) == (9, 9, True)


def test_a_printed_claim_that_is_not_a_digit_is_also_reported_rather_than_raising():
    # The other direction, and the reason the two halves are attempted
    # independently: the field was readable, so its computed digit is still
    # worth having even when the character beside it is a letter.  3.2 refused
    # to call this a mismatch and a list has nowhere to refuse *to*, so it
    # becomes `expected is None` -- never a `False`.
    for claim in (mrz.FILLER, "A", "B"):
        with pytest.raises(mrz.MrzValueError):
            mrz.verify_check_digit("740812", claim)

        result = mrz.check_digit_results([("date_of_birth", "740812", claim)])[0]

        assert result.expected is None, claim
        assert result.found == 2, claim
        assert result.passed is None, claim


def test_a_broken_entry_is_a_caller_error_and_still_raises_the_one_type():
    # What did *not* soften: a list built wrong rather than a document that is
    # wrong.  A pair silently unpacked as a triple, or a field named with a
    # position instead of a name, would otherwise hand back a shorter answer
    # than the caller asked for and say nothing.
    for entry in (("name", "740812"), ("name", "740812", 2, "extra"), 7, None):
        with pytest.raises(mrz.MrzValueError):
            mrz.check_digit_results([entry])

    with pytest.raises(mrz.MrzValueError):
        mrz.check_digit_results([(7, "740812", 2)])
    with pytest.raises(mrz.MrzValueError):
        mrz.check_digit_results(42)


def test_a_broken_entry_message_carries_no_part_of_the_field():
    # 2.10's rule, and 2.4's: the text in the second element is the document's
    # own characters and an exception message is the most likely thing in this
    # project to reach a log.  The name may be named, because a name is
    # something this code invented.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        mrz.check_digit_results([("date_of_birth", "740812")])
    with pytest.raises(mrz.MrzValueError) as named:
        mrz.check_digit_results([(7, "740812", 2)])

    assert "740812" not in str(excinfo.value)
    assert "triple" in str(excinfo.value)
    assert "7" in str(named.value)


def test_the_result_record_is_a_frozen_dataclass_of_three_fields():
    assert dataclasses.is_dataclass(mrz.CheckDigitResult)
    assert mrz.CheckDigitResult.__dataclass_params__.frozen is True
    assert [item.name for item in dataclasses.fields(mrz.CheckDigitResult)] == [
        "field",
        "expected",
        "found",
    ]

    result = mrz.CheckDigitResult("date_of_birth", 2, 2)

    assert result.passed is True
    assert result.readable is True
    assert hash(result) == hash(mrz.CheckDigitResult("date_of_birth", 2, 2))
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.found = 7


@pytest.mark.parametrize(
    "result, readable, passed",
    [
        pytest.param(mrz.CheckDigitResult("f", 2, 2), True, True, id="agree"),
        pytest.param(mrz.CheckDigitResult("f", 2, 7), True, False, id="disagree"),
        pytest.param(mrz.CheckDigitResult("f", 2, None), False, None, id="no-found"),
        pytest.param(mrz.CheckDigitResult("f", None, 2), False, None, id="no-expected"),
        pytest.param(mrz.CheckDigitResult("f", None, None), False, None, id="neither"),
    ],
)
def test_the_three_answers_are_exactly_agree_disagree_and_not_checked(
    result, readable, passed
):
    # `passed` is a property of the two digits rather than a fourth field, so
    # it cannot be stored disagreeing with them -- and there are exactly three
    # answers, not two.  A `False` for an unreadable field is 2.14's mistake
    # repeated at the wrong level: a mis-OCR'd character is not evidence of
    # tampering, and reporting it as a failure would put a forged-document
    # claim in front of an officer that the document did not earn.
    assert result.readable is readable
    assert result.passed is passed
    assert result.passed is not False or result.readable


def test_check_digit_results_and_its_record_are_exported():
    assert "check_digit_results" in mrz.__all__
    assert "CheckDigitResult" in mrz.__all__


# --- MrzValueError: the one error type this package raises ------------------

# Every module in the MRZ package, so the pins below keep holding as Part 2 and
# later add parsers next to mrz.py.  Resolved from the package directory rather
# than hard-coded, so a new sibling file is covered without editing this test.
PACKAGE_FILES = sorted(pathlib.Path(mrz.__file__).parent.glob("*.py"))

# The error types the package is allowed to define.  Anything else is a second
# error type, which is exactly what this task forbids.
ALLOWED_ERROR_TYPES = {"MrzValueError": mrz.MrzValueError}

# A raise of any of these leaves the package through a type a caller catching
# MrzValueError would not see.  ``from None`` re-raises are deliberately not
# matched: those carry an MrzValueError, which is the point.
BANNED_RAISES = (
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "RuntimeError",
    "Exception",
)


def test_the_package_has_modules_to_check():
    # A glob that silently matched nothing would make both scan tests below
    # pass for the wrong reason, so the file list is pinned first.
    assert PACKAGE_FILES
    assert mrz.__file__ in [str(path) for path in PACKAGE_FILES]


def test_mrz_value_error_is_a_value_error():
    # The assertion 1.4's note left for this task.  Subclassing is the reason
    # the class exists at all: a caller that already catches ValueError around
    # char_value keeps working without being taught the new name.
    assert issubclass(mrz.MrzValueError, ValueError)


def test_an_except_value_error_clause_catches_the_raised_error():
    # Subclassing is only worth anything if a real raise is caught by it, so
    # the compatibility claim is checked against a raise rather than the
    # class object alone.
    with pytest.raises(ValueError) as excinfo:
        mrz.char_value(" ")

    assert type(excinfo.value) is mrz.MrzValueError


def test_mrz_value_error_is_not_also_a_type_error():
    # A field of the wrong *type* (None, 42, bytes) is reported as the same
    # error, so one `except mrz.MrzValueError` is enough and no caller needs
    # a second clause.  This is why check_digit wrapped len() in 1.6.
    assert not issubclass(mrz.MrzValueError, TypeError)


def test_mrz_value_error_is_exported():
    assert "MrzValueError" in mrz.__all__


@pytest.mark.parametrize(
    "func, args",
    [
        pytest.param(mrz.char_value, (" ",), id="char_value-unknown-character"),
        pytest.param(mrz.char_value, (None,), id="char_value-none"),
        pytest.param(mrz.char_value, (5,), id="char_value-int"),
        pytest.param(mrz.weights, (-1,), id="weights-negative"),
        pytest.param(mrz.weights, (7.5,), id="weights-float"),
        pytest.param(mrz.weights, ("3",), id="weights-string"),
        pytest.param(mrz.weights, (None,), id="weights-none"),
        pytest.param(mrz.check_digit, ("74 812",), id="check_digit-unknown-character"),
        pytest.param(mrz.check_digit, (None,), id="check_digit-none"),
        pytest.param(mrz.check_digit, (42,), id="check_digit-int"),
        pytest.param(mrz.check_digit, (7.5,), id="check_digit-float"),
        pytest.param(mrz.check_digit, (b"740812",), id="check_digit-bytes"),
        pytest.param(
            mrz.verify_check_digit, ("740812", "A"), id="verify-letter-claim"
        ),
        pytest.param(
            mrz.verify_check_digit, ("740812", 2.0), id="verify-float-claim"
        ),
        pytest.param(
            mrz.verify_check_digit, ("740812", True), id="verify-bool-claim"
        ),
        pytest.param(
            mrz.verify_check_digit, (None, 2), id="verify-unreadable-field"
        ),
        pytest.param(mrz.parse_date, ("74081",), id="parse_date-too-short"),
        pytest.param(mrz.parse_date, ("7408123",), id="parse_date-too-long"),
        pytest.param(mrz.parse_date, ("",), id="parse_date-empty"),
        pytest.param(mrz.parse_date, (None,), id="parse_date-none"),
        pytest.param(mrz.parse_date, (7,), id="parse_date-int"),
        pytest.param(mrz.parse_date, (b"740812",), id="parse_date-bytes"),
        pytest.param(
            mrz.infer_birth_year,
            ("740812", "2026-09-30"),
            id="infer-birth-year-string-reference",
        ),
        pytest.param(
            mrz.infer_birth_year, ("740812", 2026), id="infer-birth-year-int-reference"
        ),
        pytest.param(
            mrz.infer_birth_year, ("740812", None), id="infer-birth-year-none-reference"
        ),
        pytest.param(
            mrz.infer_birth_year, ("AAAAAA", "2026-09-30"), id="infer-unreadable-field"
        ),
    ],
)
def test_a_bad_call_raises_mrz_value_error_and_nothing_else(func, args):
    # One call site, one error type: a caller writes `except
    # mrz.MrzValueError` once and has seen every failure this package can
    # report.  Asserting the *exact* type is what stops a second error type
    # from hiding underneath as a subclass.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        func(*args)

    assert type(excinfo.value) is mrz.MrzValueError


def test_mrz_value_error_is_the_only_error_type_the_package_defines():
    for path in PACKAGE_FILES:
        module = importlib.import_module(f"{mrz.__package__}.{path.stem}")
        defined = {
            name: obj
            for name, obj in vars(module).items()
            if isinstance(obj, type) and issubclass(obj, BaseException)
        }

        assert defined in ({}, ALLOWED_ERROR_TYPES), f"{path.name} defines {defined}"


def test_the_package_never_raises_a_builtin_error():
    # The behavioural matrix above can only cover the inputs it thought of, so
    # the single-error-type claim is also pinned on the source: a future
    # `raise ValueError(...)` in a path no test reaches fails here.
    for path in PACKAGE_FILES:
        source = path.read_text(encoding="utf-8")
        for banned in BANNED_RAISES:
            assert f"raise {banned}" not in source, f"{path.name} raises {banned}"


# --- dates: the reading, and the two faults --------------------------------

# 3.11 answers the question every format in this package deferred: what the
# six characters of a date may mean.  The reading and the judgement are two
# functions because they answer two questions, and the split is the point --
# a field nobody could read is not a date that cannot exist, and 2.14's three
# answers become three here as well.


@pytest.mark.parametrize(
    "text, year, month, day",
    [
        pytest.param("740812", 74, 8, 12, id="the-specimen-date-of-birth"),
        pytest.param("120415", 12, 4, 15, id="the-specimen-date-of-expiry"),
        pytest.param("000101", 0, 1, 1, id="the-first-day-of-the-century-unknown"),
        pytest.param("991231", 99, 12, 31, id="new-years-eve"),
        pytest.param("010101", 1, 1, 1, id="a-leading-zero-the-line-did-print"),
    ],
)
def test_a_date_parses_into_the_three_numbers_it_printed(text, year, month, day):
    date = mrz.parse_date(text)

    assert (date.year, date.month, date.day) == (year, month, day)
    # Nothing is tidied in the reading either: "010101" is 1, 1, 1 and comes
    # back as the six characters it came from, because position 7 is a check
    # digit over six characters as printed.
    assert str(date) == text


def test_the_year_is_two_digits_and_no_century():
    # The claim 3.12 and 3.13 are built on, stated so a future task cannot
    # quietly assume it: the record holds what the two characters said, and it
    # holds nothing else -- there is no fourth field a century could hide in.
    assert dataclasses.is_dataclass(mrz.MrzDate)
    assert mrz.MrzDate.__dataclass_params__.frozen is True
    assert [field.name for field in dataclasses.fields(mrz.MrzDate)] == [
        "year",
        "month",
        "day",
    ]
    date = mrz.parse_date("000101")

    assert date.year == 0
    assert mrz.parse_date("991231").year == 99
    with pytest.raises(dataclasses.FrozenInstanceError):
        date.day = 2


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("AAAAAA", id="letters"),
        pytest.param("abcdef", id="lower-case-letters"),
        pytest.param("<<<<<<", id="six-fillers"),
        pytest.param("74 812", id="a-space"),
        pytest.param("74o812", id="a-letter-where-a-digit-goes"),
        pytest.param("7<0812", id="a-filler-inside-the-date"),
        pytest.param("74٠812", id="a-non-ascii-digit"),
        pytest.param("74/812", id="a-slash"),
    ],
)
def test_six_characters_that_are_not_all_digits_are_not_a_date(text):
    # The half of the rule that costs a document rather than catching one.  A
    # filler, a letter, a space and a non-ASCII digit are all `None`, because
    # the character is a misread and the check digit printed beside the date
    # is what reports a misread.  **"٧" is the row that is here for the code
    # rather than for the standard**: `str.isdigit()` answers True for it and
    # `int()` accepts it, so a reading that tested for digits that way would
    # parse an Urdu-Indic zero into a date.
    assert mrz.parse_date(text) is None
    assert mrz.date_fault(text) is None


# The calendar maxima, written out here rather than read from the module.  A
# test that recomputed the expectation from `mrz.MONTH_DAYS` would agree with
# a wrong constant; this copy is the longhand second source 3.8's tables have.
TEST_MONTH_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def test_the_month_maxima_are_the_ones_the_constant_holds():
    assert mrz.MONTH_DAYS == TEST_MONTH_DAYS
    assert len(mrz.MONTH_DAYS) == 12
    # February is the one entry that is a decision rather than the calendar's
    # rule, so it is pinned by name: 29 and not 28, because a date carries two
    # digits of year and cannot say whether *this* February had a 29th.
    assert mrz.MONTH_DAYS[1] == 29


def test_every_month_against_every_day_agrees_with_the_table():
    # The whole rule, measured rather than remembered: all fourteen month
    # values (none, the twelve real ones and one past the end) against every
    # day from 00 to 32, which is 462 cases.  Two things are being claimed, and
    # they are the two halves of the loop -- a month outside 01-12 is "month"
    # whatever the day is, because a month that does not exist makes the day
    # beside it meaningless; and a day is "day" when it is 00 or past that
    # month's own maximum.  The count is asserted so the loop cannot quietly
    # stop covering a month.
    cases = 0
    for month in range(0, 14):
        for day in range(0, 33):
            text = f"74{month:02d}{day:02d}"
            if not 1 <= month <= 12:
                expected = "month"
            elif day == 0 or day > TEST_MONTH_DAYS[month - 1]:
                expected = "day"
            else:
                expected = None

            assert mrz.parse_date(text) is not None, text
            assert mrz.date_fault(text) == expected, text
            cases += 1

    assert cases == 14 * 33


@pytest.mark.parametrize(
    "text, fault",
    [
        pytest.param("993199", "month", id="the-task-value-month-31"),
        pytest.param("013200", "month", id="the-task-value-month-32"),
        pytest.param("740000", "month", id="month-00"),
        pytest.param("740132", "day", id="day-32-in-january"),
        pytest.param("740230", "day", id="day-30-in-february"),
        pytest.param("740232", "day", id="day-32-in-february"),
        pytest.param("740431", "day", id="day-31-in-april"),
    ],
)
def test_the_task_own_two_values_and_their_neighbours_are_faults(text, fault):
    # 3.11 names "993199" and "013200" and refuses both.  Both are refused for
    # the *month*, which is the answer that matters: a message saying the month
    # is impossible is a reading this project can contradict, where a message
    # about the day would be guessing past the fault.
    assert mrz.date_fault(text) == fault


def test_the_month_is_judged_before_the_day():
    # "993199" is wrong in both halves and says so about the first one it
    # reaches, which is the order the six characters are read in.
    assert mrz.parse_date("993199") == mrz.MrzDate(99, 31, 99)
    assert mrz.date_fault("993199") == "month"


@pytest.mark.parametrize(
    "text",
    [
        "740812",
        "120415",
        "000101",
        "991231",
        "020229",
        "010131",
        "741231",
    ],
)
def test_a_date_that_could_be_a_day_has_no_fault(text):
    # "000101" and "020229" are the two the century question is hiding behind:
    # both are accepted, because "00" is a year somebody was born in and a 29th
    # of February is a day in most centuries.  Refusing either here would mean
    # inventing a century to refuse it with, which is 3.12's and 3.13's work.
    # "010131" and "741231" are the two ends of the day range: 01 and 31 are
    # both days, and the fault test's own loop is what proves 31 is not past
    # December's maximum.
    assert mrz.date_fault(text) is None


@pytest.mark.parametrize("text", ["74081", "7408123", "", "740812  ", None, 7])
def test_a_field_the_width_rule_has_not_reached_has_no_fault(text):
    # How wide a date is belongs to the layout table, which is where all three
    # format validators read their width from, so this deliberately passes a
    # wrong width over rather than judging it.  **2.11's technique is what
    # makes that necessary**: a reader that moved a date field in its table and
    # got a five-character field would otherwise be refused by a width rule
    # this package does not own, and the test that proves a reader takes its
    # positions from the layout would fail on something a month cannot be.
    # `parse_date` is the strict one -- a caller holding five characters hears
    # about it -- and this is the one function that does not.
    assert mrz.date_fault(text) is None


def test_every_layout_printing_a_date_prints_six_of_them():
    # The claim that makes DATE_LENGTH the number it is: all three formats
    # read their own width out of their own table and none of them imports
    # this constant, so a table that said a date was five or eight characters
    # wide would make the shared rule skip it rather than misread it.  Resolved
    # from the package rather than hard-coded, so a fourth format is covered
    # by being added.
    widths = {}
    for stem in ("td1", "td2", "td3"):
        module = importlib.import_module(f"{mrz.__package__}.{stem}")
        for name in ("date_of_birth", "date_of_expiry"):
            start, end = getattr(module, f"{stem.upper()}_LINE_2")[name]
            widths[f"{stem}.{name}"] = end - start + 1

    assert len(widths) == 6
    assert set(widths.values()) == {mrz.DATE_LENGTH}


def test_the_date_names_are_exported():
    assert "MrzDate" in mrz.__all__
    assert "parse_date" in mrz.__all__
    assert "date_fault" in mrz.__all__


# --- 3.12: the century a date of birth belongs to ----------------------------

# Two printed digits of year name two candidate years and nothing else, and
# which of them a document meant is a fact about *when* the document is read
# rather than about the six characters.  So the answer is a function beside
# `parse_date` and not a field of the record, it takes the reference date as an
# argument rather than reading the clock, and it is named for the one date it
# is allowed to answer for -- 3.13's expiry reading is a different rule and
# gets its own name rather than a flag on this one.

# The date this section mostly reads against: the reference is injected, so
# the tests state one and the rule has to earn every answer from it.
REFERENCE = datetime.date(2026, 9, 30)


def test_the_specimen_date_of_birth_is_read_in_the_century_before_today():
    # The specimen prints "74" and the holder is fifty-two, not a hundred and
    # fifty-two: this is the ordinary case, and it is decided entirely by the
    # two digits being ahead of the reference's own.
    assert mrz.infer_birth_year("740812", REFERENCE) == 1974
    assert mrz.parse_date("740812").year == 74


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param("250930", 2025, id="last-year"),
        pytest.param("260929", 2026, id="yesterday"),
        pytest.param("260930", 2026, id="today-is-still-a-year-that-has-happened"),
        pytest.param("261001", 1926, id="tomorrow-so-the-century-before"),
        pytest.param("270930", 1927, id="next-year"),
    ],
)
def test_the_year_either_side_of_the_cut_flips_the_century(text, expected):
    # The line the rule turns on, and it is a *date* line rather than a year
    # line: a document printed for the 1st of October and read on the 30th of
    # September is a hundred years back, while one printed for the 30th read
    # on the 30th is today.  Comparing the years alone would get the middle row
    # and the fourth row the same way round.
    assert mrz.infer_birth_year(text, REFERENCE) == expected


def test_the_reference_date_is_what_moves_the_century():
    # The same six characters, read a year apart, and the answer moves with the
    # reference rather than with the clock: 1 January 2006 is a birth date on
    # the day it happens and a century away the day before.
    assert mrz.infer_birth_year("060101", datetime.date(2005, 12, 31)) == 1906
    assert mrz.infer_birth_year("060101", datetime.date(2006, 1, 1)) == 2006


def test_the_120_year_cut_is_a_line_and_not_a_feeling():
    # `MAX_BIRTH_AGE` is a decision about people, not about documents, so it is
    # pinned as a number and then pinned again as an edge: a holder of exactly
    # 120 is admitted on the last day of the window and refused on the first
    # day of the next.  "000229" is the sharp case, because the century it
    # needs is a leap century -- 2000 was, 2100 is not -- so the reference has
    # to be a century past 2000 for the cut to be the thing being tested rather
    # than the leap year.
    assert mrz.MAX_BIRTH_AGE == 120
    assert calendar.isleap(2000)
    assert not calendar.isleap(2100)
    # 2000-02-29 is a real day 120 years before 2120-12-31: admitted.
    assert mrz.infer_birth_year("000229", datetime.date(2120, 12, 31)) == 2000
    # The same document a day later is 121, and there is no third century left
    # to try, so it gets no year at all rather than an invented one.
    assert mrz.infer_birth_year("000229", datetime.date(2121, 1, 1)) is None


@pytest.mark.parametrize(
    "reference, text, expected",
    [
        pytest.param(
            datetime.date(2026, 9, 30), "000229", 2000, id="2000-was-a-leap-year"
        ),
        pytest.param(
            datetime.date(2026, 9, 30), "040229", 2004, id="2004-was-a-leap-year"
        ),
        pytest.param(
            datetime.date(2026, 9, 30),
            "020229",
            None,
            id="neither-2002-nor-1902-had-a-29th",
        ),
        pytest.param(
            datetime.date(2126, 9, 30), "000229", None, id="2100-had-none"
        ),
        pytest.param(
            datetime.date(1900, 1, 1),
            "000229",
            None,
            id="neither-1900-nor-1800-had-a-29th",
        ),
    ],
)
def test_a_29th_of_february_is_read_only_in_a_century_that_had_one(
    reference, text, expected
):
    # The leap-year question 3.11 deferred by putting 29 into February's
    # maximum, asked now.  Every year this function does answer with is a real
    # leap year, which is the claim a tuple of maxima cannot make: `date_fault`
    # accepts all five of these fields without knowing whether *that* February
    # had a 29th, and the century is what turns "29" into a day or into
    # nothing.  **"020229" is the row the whole section exists for**: read in
    # 2026 its two candidates are 2002 and 1902 and neither had a 29th of
    # February, so a field `date_fault` calls perfectly good gets no year.
    assert mrz.infer_birth_year(text, reference) == expected
    if expected is not None:
        assert calendar.isleap(expected)
    assert mrz.date_fault(text) is None
    assert mrz.parse_date(text) is not None


def test_the_same_six_characters_are_a_different_day_in_another_century():
    # The sharpest form of the claim above: one field, two centuries, and the
    # 29th of February exists in one of them and not the other.  A reader that
    # accepted "000229" in 2126 would be asserting a date that never was.
    assert mrz.infer_birth_year("000229", REFERENCE) == 2000
    assert calendar.isleap(2000)
    # In 2126 the same two digits point at 2100 first, which had no 29th of
    # February, and the century before that is 126 years back.
    assert mrz.infer_birth_year("000229", datetime.date(2126, 9, 30)) is None


def _expected_birth_year(two_digits: int, reference: datetime.date) -> int | None:
    """The rule restated here, so a wrong rule cannot agree with itself.

    The most recent year carrying these two digits, no more than 120 years
    before the reference.  The 120 is written out rather than read from
    ``mrz.MAX_BIRTH_AGE`` for the reason ``TEST_MONTH_DAYS`` above exists: a
    test that recomputed the expectation from the constant would agree with a
    wrong constant.  The band's edge is pinned by the dedicated test above, so
    this copy only has to carry the middle of the rule.
    """
    for year in range(reference.year, reference.year - 121, -1):
        if year % 100 == two_digits:
            return year
    return None


#: Reference dates the sweep runs against: a century boundary on each side of
#: the leap-century question, a non-leap century, and today.  The month and day
#: are the reference's own, so the "has it happened yet" test cannot fire on
#: the chosen year and the sweep measures the century choice and the band.
SWEEP_REFERENCES = (
    datetime.date(1900, 9, 30),
    datetime.date(1999, 9, 30),
    datetime.date(2000, 9, 30),
    REFERENCE,
    datetime.date(2099, 9, 30),
    datetime.date(2100, 9, 30),
    datetime.date(2126, 9, 30),
)


@pytest.mark.parametrize("reference", SWEEP_REFERENCES, ids=lambda d: str(d.year))
def test_every_two_digit_year_agrees_with_the_rule_written_out_here(reference):
    # The whole rule, measured rather than remembered: all one hundred printed
    # years against the formula above, seven reference dates, 700 cases.  Each
    # answer is also checked against the three properties the rule claims, so a
    # wrong year that happened to be the longhand copy's wrong year would still
    # have to be a year with these two digits, in the past, and no more than
    # 120 years back.
    cases = 0
    for two_digits in range(100):
        text = f"{two_digits:02d}{reference.month:02d}{reference.day:02d}"
        expected = _expected_birth_year(two_digits, reference)
        found = mrz.infer_birth_year(text, reference)

        assert found == expected, text
        if found is not None:
            assert found % 100 == two_digits, text
            assert found <= reference.year, text
            assert reference.year - found <= 120, text
        cases += 1

    assert cases == 100


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("AAAAAA", id="letters"),
        pytest.param("abcdef", id="lower-case-letters"),
        pytest.param("<<<<<<", id="six-fillers"),
        pytest.param("74o812", id="a-letter-where-a-digit-goes"),
        pytest.param("74Ù 812", id="a-non-ascii-digit"),
        pytest.param("993199", id="the-task-value-month-31"),
        pytest.param("013200", id="the-task-value-month-32"),
        pytest.param("740000", id="month-00"),
        pytest.param("740132", id="day-32-in-january"),
        pytest.param("740230", id="day-30-in-february"),
        pytest.param("74081", id="too-short"),
        pytest.param("7408123", id="too-long"),
        pytest.param("", id="empty"),
        pytest.param(None, id="none"),
        pytest.param(7, id="an-int"),
        pytest.param(b"740812", id="bytes"),
    ],
)
def test_a_date_with_no_century_to_give_returns_none(text):
    # `None` is the answer in every one of these cases and it is the same
    # sentence said three ways -- these characters are not a date, that date
    # cannot exist, or the field is a width this package's layout table has
    # not declared.  **The wrong-width rows are 2.11's technique again**: a
    # reader that moved a date field in its table and got five characters must
    # not be refused by a width rule living here, and must not be given a
    # century either.
    assert mrz.infer_birth_year(text, REFERENCE) is None


def test_a_bad_reference_date_raises_even_where_the_field_is_unreadable():
    # A reference date is never a fact about a document, so a caller who has
    # not injected one is told rather than answered `None`: reporting a
    # screening that went wrong as a document nobody could read is the one
    # confusion this package cannot have.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        mrz.infer_birth_year("AAAAAA", "2026-09-30")

    assert type(excinfo.value) is mrz.MrzValueError


def test_a_datetime_is_a_date_and_does_not_raise():
    # `datetime.datetime` subclasses `datetime.date`, so a caller holding a
    # timestamp is not a caller making that mistake and must not be refused.
    stamp = datetime.datetime(2026, 9, 30, 11, 5, 42)

    assert mrz.infer_birth_year("740812", stamp) == 1974


def test_the_reference_date_is_injected_and_never_taken_from_the_clock():
    # `datetime.now()` inside check logic is banned by `tasks.md`, and the ban
    # is pinned on the signature and on the source rather than on today's date:
    # a default of `date.today()` would pass every behavioural test in this
    # file and still make a screening's answer depend on when it ran.  **The
    # source is walked rather than grepped**, because the module's docstrings
    # name `datetime.now()` in order to say it is not used, and a substring
    # test would have to ban the sentence that documents the rule.
    signature = inspect.signature(mrz.infer_birth_year)

    assert list(signature.parameters) == ["text", "reference"]
    assert signature.parameters["reference"].default is inspect.Parameter.empty
    tree = ast.parse(pathlib.Path(mrz.__file__).read_text(encoding="utf-8"))
    clock_calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        if node.func.attr in {"now", "utcnow", "today", "fromtimestamp"}
    ]

    assert clock_calls == []


def test_the_two_rules_are_separate_functions_and_neither_is_wired_to_a_validator():
    # 3.12 asserted "3.13 has not arrived early", and this task is 3.13, so
    # that claim is retired here rather than deleted -- and what replaces it is
    # the claim worth keeping, which is *stronger* and not weaker.  Where 3.12
    # asserted one absence, this asserts two functions that exist, are not the
    # same function, and that neither has reached a validator.  The handover's
    # reason is the one that matters: the only thing stopping the two rules
    # drifting into each other is that they are two names rather than one name
    # with a flag, and a test that only said "the second does not exist yet"
    # would stop protecting anything the moment the second arrived.
    for stem in ("td1", "td2", "td3"):
        module = importlib.import_module(f"{mrz.__package__}.{stem}")
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")

        # The format modules judge width and range only.  A century is not a
        # range, and 3.11's own note put 3.12 and 3.13 *after* it on purpose.
        #
        # 3.14 turned this from a substring into an AST walk, for the reason
        # this file already gives for walking `mrz.py` rather than reading it:
        # the record's docstring names both functions in order to explain why
        # it carries no century, and a substring test would have had to ban
        # the sentence documenting the decision it is meant to protect.  The
        # claim is unchanged and is now the one worth making -- neither
        # function is *called* from a format module -- and a call is a Name
        # in the code rather than a word in a comment.
        called = {
            node.id if isinstance(node, ast.Name) else node.attr
            for node in ast.walk(ast.parse(source))
            if isinstance(node, (ast.Name, ast.Attribute))
        }
        assert "infer_birth_year" not in called, stem
        assert "infer_expiry_year" not in called, stem
    # Two names, two bodies: an alias or a one-line wrapper around the other
    # would satisfy `hasattr` while being exactly the drift this forbids.
    assert mrz.infer_expiry_year is not mrz.infer_birth_year
    assert inspect.getsource(mrz.infer_expiry_year) != inspect.getsource(
        mrz.infer_birth_year
    )
    for function in (mrz.infer_birth_year, mrz.infer_expiry_year):
        assert list(inspect.signature(function).parameters) == ["text", "reference"]
    # And they genuinely disagree, so neither is the other's answer renamed.
    assert mrz.infer_birth_year("740930", REFERENCE) == 1974
    assert mrz.infer_expiry_year("740930", REFERENCE) == 2074
    # The record still holds no century, and the answer is a plain int beside
    # it rather than a fourth field inside it.
    assert [field.name for field in dataclasses.fields(mrz.MrzDate)] == [
        "year",
        "month",
        "day",
    ]
    assert type(mrz.infer_birth_year("740812", REFERENCE)) is int
    assert type(mrz.infer_expiry_year("740812", REFERENCE)) is int


def test_the_century_names_are_exported():
    assert "MAX_BIRTH_AGE" in mrz.__all__
    assert "infer_birth_year" in mrz.__all__
    assert "infer_expiry_year" in mrz.__all__


# ---------------------------------------------------------------------------
# 3.13 -- the same six characters, read the other way round.
#
# A birth is read *backwards* from the reference and an expiry *forwards*, so
# the two rules differ in which side of the reference a candidate must be on.
# They are two functions rather than one with a flag, and the two things they
# share are named in the module: the two gates (`parse_date`, then
# `date_fault`) and the calendar fact `_is_a_real_day`.  Everything else --
# the direction, the candidate centuries, the absence of a band -- is
# different, and this section measures each difference rather than asserting
# that the docstring mentions it.


def _expected_expiry_year(
    two_digits: int, reference: datetime.date, month: int, day: int
) -> int | None:
    """The expiry rule restated here, so a wrong rule cannot agree with itself.

    The nearest year carrying these two digits that the document has not
    already got past, and that is a day the year had.  **There is no band
    written into this copy**, which is the point: `MAX_BIRTH_AGE` is a fact
    about people and this copy of the rule has no need of it, so a wrong
    constant in `mrz` cannot be laundered through a shared expectation.  The
    hundred-year walk below is what bounds the answer -- two digits repeat
    every hundred years, so the nearest match is at most a century away and
    the rule cannot run past the end of the walk.
    """
    for year in range(reference.year, reference.year + 101):
        if year % 100 != two_digits:
            continue
        if (year, month, day) < (reference.year, reference.month, reference.day):
            continue  # the document had already expired on that day
        if month == 2 and day == 29 and not calendar.isleap(year):
            continue  # a 29th of February in a year that had none
        return year
    return None


#: The same seven references 3.12's sweep used, so the two sweeps are
#: comparable and a century boundary is measured on both rules.  The month and
#: day are each reference's own, which keeps the 29th of February out of the
#: sweep so that what the sweep measures is the century choice and the
#: direction -- the leap question gets its own test below, as it did for a
#: birth.
EXPIRY_SWEEP_REFERENCES = (
    datetime.date(1900, 9, 30),
    datetime.date(1999, 9, 30),
    datetime.date(2000, 9, 30),
    REFERENCE,
    datetime.date(2099, 9, 30),
    datetime.date(2100, 9, 30),
    datetime.date(2126, 9, 30),
)


def test_the_nearest_year_that_has_not_passed_is_the_answer():
    # The ordinary case, and it is the mirror image of 3.12's first test: the
    # same two printed digits on the same reference, and the answers are a
    # century apart, because a holder of 52 is behind the reference and a
    # document with 74 years left on it is ahead of it.
    assert mrz.infer_expiry_year("740930", REFERENCE) == 2074
    assert mrz.infer_birth_year("740930", REFERENCE) == 1974
    assert mrz.parse_date("740930").year == 74


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param("250930", 2125, id="last-year-so-a-century-on"),
        pytest.param("260101", 2126, id="earlier-this-year-so-a-century-on"),
        pytest.param("260929", 2126, id="yesterday-so-a-century-on"),
        pytest.param("260930", 2026, id="today-is-still-valid"),
        pytest.param("261001", 2026, id="tomorrow-is-still-this-year"),
        pytest.param("270930", 2027, id="next-year"),
    ],
)
def test_the_year_either_side_of_the_cut_flips_the_century_forwards(text, expected):
    # **This is the task's boundary test, and it is the exact mirror of 3.12's
    # with the sign flipped on the rows that are not shared.**  A birth turns
    # back a century when the printed date is *ahead* of the reference; an
    # expiry turns forward a century when the printed date is *behind* it.  So
    # "260929" is a birth of today and an expiry that lapsed yesterday, and
    # "261001" is a birth a century back and an expiry still valid this year.
    #
    # The "yesterday" and "today" rows are one day apart and a century apart in
    # the answer, which is the whole content of the rule: a document is valid
    # *through* the day it expires, so today is still this year and yesterday
    # is a hundred years gone.  A reader comparing the years alone would get
    # "260101" and "260930" the same way round, and it is the "260101" row
    # that pins the comparison being on the whole date.
    assert mrz.infer_expiry_year(text, REFERENCE) == expected


def test_today_is_the_one_day_the_two_rules_read_the_same_way():
    # The rows above look like opposites, so this pins the place they are not:
    # **the day itself is on the "has happened" side for a birth and the "has
    # not passed" side for an expiry**, which is why both rules admit it and
    # why the comparison admits the day in each.  Read the day before or the
    # day after and the two part company by a century, which is what the two
    # neighbours here show.
    assert mrz.infer_birth_year("260930", REFERENCE) == 2026
    assert mrz.infer_expiry_year("260930", REFERENCE) == 2026
    # Yesterday, a birth has already happened but the document has expired.
    assert mrz.infer_birth_year("260929", REFERENCE) == 2026
    assert mrz.infer_expiry_year("260929", REFERENCE) == 2126
    # Tomorrow, a birth has not happened yet but the document is still valid.
    assert mrz.infer_birth_year("261001", REFERENCE) == 1926
    assert mrz.infer_expiry_year("261001", REFERENCE) == 2026


@pytest.mark.parametrize(
    "reference, text, expected",
    [
        pytest.param(
            datetime.date(2000, 2, 28), "000229", 2000, id="the-day-before-a-leap-day"
        ),
        pytest.param(
            datetime.date(1999, 9, 30),
            "000229",
            2000,
            id="2000-had-not-come-round-yet",
        ),
        pytest.param(
            datetime.date(2026, 9, 30),
            "040229",
            2104,
            id="2004-has-passed-so-2104-is-the-nearest-leap-century",
        ),
        pytest.param(
            datetime.date(2026, 9, 30),
            "000229",
            None,
            id="2000-has-passed-and-2100-had-none",
        ),
        pytest.param(
            datetime.date(2099, 9, 30),
            "000229",
            None,
            id="the-nearest-century-is-not-a-leap-century-either",
        ),
        pytest.param(
            datetime.date(2400, 1, 1),
            "000229",
            2400,
            id="the-answer-returns-at-the-next-leap-century",
        ),
    ],
)
def test_a_29th_of_february_is_an_expiry_in_a_century_that_had_one(
    reference, text, expected
):
    # The same leap-year question 3.12 asked, asked through the same shared
    # `_is_a_real_day`, and **it bites differently here**: a birth reads the
    # nearest century *backwards* and always has a century in hand, while an
    # expiry reads *forwards* and can run out.  A birth's `None` needs a
    # century that is both too old and not a real day; an expiry's `None` needs
    # only a century that is not a real day, because nothing bounds the far
    # side at all.
    assert mrz.infer_expiry_year(text, reference) == expected
    if expected is not None:
        assert calendar.isleap(expected)
    # Every one of these fields is a date `date_fault` calls perfectly good:
    # the century is the only thing that turns "29" into a day or into nothing.
    assert mrz.date_fault(text) is None
    assert mrz.parse_date(text) is not None


def test_the_leap_day_boundary_is_a_single_day():
    # The one-day pair the leap question turns on, and the sharpest difference
    # between the two rules in the whole package.  On 28 February 2000 the
    # nearest century *is* the leap year 2000 and the field reads forward to it;
    # the very next day 2000 has passed, the next century is 2100, and 2100 is
    # not a leap year -- so the same six characters, read a day later, get no
    # year at all rather than a date that never was.  **A birth reading the
    # same field says 2000 on the second of those days**, because 2000 is in
    # its past and its oldest candidate is a century further back.
    assert mrz.infer_expiry_year("000229", datetime.date(2000, 2, 28)) == 2000
    assert mrz.infer_expiry_year("000229", datetime.date(2000, 3, 1)) is None
    assert mrz.infer_birth_year("000229", datetime.date(2000, 3, 1)) == 2000
    # Read from 2026, where 2000 is behind us, the same field is the one place
    # the two rules give different *kinds* of answer: a birth can still name a
    # century, and an expiry has run out of them.
    assert mrz.infer_birth_year("000229", REFERENCE) == 2000
    assert mrz.infer_expiry_year("000229", REFERENCE) is None


@pytest.mark.parametrize(
    "text, birth, expiry",
    [
        pytest.param("740930", 1974, 2074, id="the-ordinary-case-a-century-apart"),
        pytest.param("260929", 2026, 2126, id="yesterday-is-past-but-has-expired"),
        pytest.param("261001", 1926, 2026, id="tomorrow-is-future-but-still-valid"),
        pytest.param(
            "000229", 2000, None, id="one-can-name-a-century-and-the-other-cannot"
        ),
        pytest.param("990101", 1999, 2099, id="digits-behind-and-ahead-of-todays-own"),
    ],
)
def test_the_two_rules_disagree_where_the_directions_disagree(text, birth, expiry):
    # The claim that makes them two functions rather than one with a flag,
    # measured: for every row here the two rules read the same six characters
    # against the same reference and do not give the same year.  A single
    # function with a `kind=` argument would pass every test above and fail
    # this one, which is exactly the drift the two names exist to stop.
    assert mrz.infer_birth_year(text, REFERENCE) == birth
    assert mrz.infer_expiry_year(text, REFERENCE) == expiry


@pytest.mark.parametrize("reference", EXPIRY_SWEEP_REFERENCES, ids=lambda d: str(d.year))
def test_every_two_digit_year_agrees_with_the_expiry_rule_written_out_here(
    reference,
):
    # The whole rule, measured rather than remembered: all one hundred printed
    # years against the longhand copy above, seven reference dates, 700 cases.
    # Each answer is also checked against the properties the rule claims --
    # these two digits, not already passed, and within a century -- so a wrong
    # year that happened to be the longhand copy's wrong year would still have
    # to satisfy them.
    cases = 0
    unplaceable = 0
    for two_digits in range(100):
        text = f"{two_digits:02d}{reference.month:02d}{reference.day:02d}"
        expected = _expected_expiry_year(two_digits, reference, 9, 30)
        found = mrz.infer_expiry_year(text, reference)

        assert found == expected, text
        if found is None:
            unplaceable += 1
        else:
            assert found % 100 == two_digits, text
            # Not already passed ...
            assert (found, reference.month, reference.day) >= (
                reference.year,
                reference.month,
                reference.day,
            ), text
            # ... and at most a century away, which is arithmetic rather than
            # a band: two digits repeat every hundred years, so the nearest
            # match cannot be further out than that.
            assert 0 <= found - reference.year <= 99, text
        cases += 1

    assert cases == 100
    # **No band means no case is unplaceable.**  This is the count that
    # distinguishes the two sweeps: 3.12's leaves `None`s behind whenever the
    # band runs out, and this one cannot, because there is no band to run out
    # of.  It is the same 700 fields, and not one of them is refused for being
    # too far in the future.
    assert unplaceable == 0


def test_the_answer_is_never_more_than_a_century_out_and_nothing_bounds_it_tighter():
    # The bound, pinned at its own edge rather than averaged.  "25" against a
    # reference whose own year ends in 26 is the furthest the rule can reach:
    # the nearest year carrying "25" that has not passed is 2125, ninety-nine
    # years on, and it is answered rather than refused.  A reader that
    # borrowed a band -- `MAX_BIRTH_AGE`, say -- would refuse nothing here
    # (99 < 120), which is why the sharing is caught by the source test below
    # and not by an edge.
    assert mrz.infer_expiry_year("250101", REFERENCE) == 2125
    assert 2125 - REFERENCE.year == 99
    # The nearest case, for symmetry: the reference's own two digits.
    assert mrz.infer_expiry_year("260101", datetime.date(2026, 1, 1)) == 2026


def test_the_expiry_rule_shares_no_band_with_the_birth_rule():
    # `MAX_BIRTH_AGE` is named for the date it bounds and the reasoning behind
    # it -- nobody is 121 -- is about a person, not a document.  **The check is
    # on the code rather than on the source text**, because the docstring names
    # the constant in order to explain why this rule does not use it, and a
    # substring test would have to ban the sentence that documents the rule.
    # `ast.Name` is what an identifier actually is; a docstring is a
    # `Constant` and cannot appear here.
    tree = ast.parse(pathlib.Path(mrz.__file__).read_text(encoding="utf-8"))
    names = {
        function.name: {
            node.id for node in ast.walk(function) if isinstance(node, ast.Name)
        }
        for function in tree.body
        if isinstance(function, ast.FunctionDef)
        and function.name in {"infer_birth_year", "infer_expiry_year"}
    }

    # Both functions exist, so the comparison is between two real bodies.
    assert set(names) == {"infer_birth_year", "infer_expiry_year"}
    assert "MAX_BIRTH_AGE" in names["infer_birth_year"]
    assert "MAX_BIRTH_AGE" not in names["infer_expiry_year"]
    # And there is no expiry band that could have been borrowed instead.
    assert not [name for name in mrz.__all__ if "AGE" in name and "BIRTH" not in name]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("AAAAAA", id="letters"),
        pytest.param("abcdef", id="lower-case-letters"),
        pytest.param("<<<<<<", id="six-fillers"),
        pytest.param("74o812", id="a-letter-where-a-digit-goes"),
        pytest.param("74١812", id="a-non-ascii-digit"),
        pytest.param("993199", id="month-31"),
        pytest.param("013200", id="month-32"),
        pytest.param("740000", id="month-00"),
        pytest.param("740132", id="day-32-in-january"),
        pytest.param("740230", id="day-30-in-february"),
        pytest.param("74081", id="too-short"),
        pytest.param("7408123", id="too-long"),
        pytest.param("", id="empty"),
        pytest.param(None, id="none"),
        pytest.param(7, id="an-int"),
        pytest.param(b"740812", id="bytes"),
    ],
)
def test_an_expiry_with_no_century_to_give_returns_none(text):
    # The same `None` in the same fifteen cases a birth gives, and **for the
    # same two reasons**: the two gates are one function, so a field this
    # cannot read is a field the birth rule cannot read either.  Asserting
    # them row for row is how this states the sharing rather than describing
    # it in a comment -- what differs between the two is only which century
    # each lands on, which is what the disagreement test above measures.
    assert mrz.infer_expiry_year(text, REFERENCE) is None
    assert mrz.infer_birth_year(text, REFERENCE) is None


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param(datetime.date(2026, 9, 30), id="after-2000"),
        pytest.param(datetime.date(2099, 9, 30), id="before-2100"),
        pytest.param(datetime.date(2100, 1, 1), id="in-a-non-leap-century"),
        pytest.param(datetime.date(2199, 9, 30), id="after-2100"),
    ],
)
def test_an_expiry_the_rule_cannot_place_at_all_returns_none(reference):
    # "This document does not tell us", the third of 3.12's three answers and
    # the same sentence here, reached for a different reason.  `"000229"`
    # needs a leap century that has not passed; between 2000 and 2400 the
    # century starting the reference is either behind the reference or is not a
    # leap century, and 2100 and 2200 and 2300 are all not leap years, so for
    # four reference dates spread across those centuries the rule has nothing
    # real to name.  **A guess would be worse than a gap**, so it says so
    # rather than returning a 29th of February that never was.
    assert not calendar.isleap(2100)
    assert not calendar.isleap(2200)
    assert not calendar.isleap(2300)
    assert mrz.infer_expiry_year("000229", reference) is None


def test_a_bad_reference_date_raises_even_where_the_expiry_is_unreadable():
    # A reference date is never a fact about a document, so a caller who has
    # not injected one is told rather than answered `None`.  The check comes
    # before the field is read, which is why an unreadable field still raises:
    # the two are independent mistakes and neither hides the other.
    with pytest.raises(mrz.MrzValueError) as expiry_excinfo:
        mrz.infer_expiry_year("AAAAAA", "2026-09-30")
    with pytest.raises(mrz.MrzValueError) as birth_excinfo:
        mrz.infer_birth_year("AAAAAA", "2026-09-30")

    assert type(expiry_excinfo.value) is mrz.MrzValueError
    # The same message, because it is the same mistake about the same thing.
    assert str(expiry_excinfo.value) == str(birth_excinfo.value)


def test_a_datetime_is_a_date_for_an_expiry_too():
    # `datetime.datetime` subclasses `datetime.date`, so a caller holding a
    # timestamp is not a caller making that mistake and must not be refused.
    stamp = datetime.datetime(2026, 9, 30, 11, 5, 42)

    assert mrz.infer_expiry_year("740812", stamp) == 2074


def test_both_rules_take_the_reference_from_the_caller_and_never_from_the_clock():
    # `datetime.now()` inside check logic is banned by `tasks.md`, and the ban
    # is pinned on the signature and on the source rather than on today's date:
    # a default of `date.today()` would pass every behavioural test in this
    # file and still make a screening's answer depend on when it ran.  **The
    # source is walked rather than grepped**, because the module's docstrings
    # name `datetime.now()` in order to say it is not used, and a substring
    # test would have to ban the sentence that documents the rule.
    for function in (mrz.infer_birth_year, mrz.infer_expiry_year):
        signature = inspect.signature(function)

        assert list(signature.parameters) == ["text", "reference"]
        assert signature.parameters["reference"].default is inspect.Parameter.empty
    tree = ast.parse(pathlib.Path(mrz.__file__).read_text(encoding="utf-8"))
    clock_calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        if node.func.attr in {"now", "utcnow", "today", "fromtimestamp"}
    ]

    assert clock_calls == []
